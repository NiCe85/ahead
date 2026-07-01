import os
import json
from datetime import datetime
import pandas as pd
from mcp.server.fastmcp import FastMCP

from src.data.generator import SeededLedgerGenerator
from src.utils.pii_redactor import PIIRedactor
from src.forecaster.engine import ForecastEngine

# Initialize FastMCP Server
mcp = FastMCP("Ahead")

# Define the ledger data file path
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_PATH = os.path.join(WORKSPACE_DIR, "data", "ledger.json")

def load_or_generate_ledger():
    """
    Helper to load existing ledger data or generate a new seeded one if missing.
    """
    # Ensure directories exist
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, 'r') as f:
            return json.load(f)
            
    # Generate new seeded ledger
    generator = SeededLedgerGenerator(seed=42)
    ledger_data = generator.generate(days=180, end_date_str="2026-06-20", starting_balance=1800.00)
    
    with open(LEDGER_PATH, 'w') as f:
        json.dump(ledger_data, f, indent=2)
        
    return ledger_data

def get_fixed_transaction_ids(transactions: list) -> set:
    """
    Identifies fixed transaction IDs to filter from discretionary spending.
    """
    fixed_substrs = ["RENT", "ELECTRIC", "INTERNET", "NETFLIX", "PAYROLL"]
    fixed_ids = set()
    for tx in transactions:
        desc = tx.get("description", "").upper()
        for sub in fixed_substrs:
            if sub in desc:
                fixed_ids.add(tx["transaction_id"])
    return fixed_ids

@mcp.tool()
def get_accounts() -> str:
    """
    Returns checking accounts list with redacted/masked PII.
    """
    ledger = load_or_generate_ledger()
    redacted_account = PIIRedactor.redact_account(ledger["account"])
    return json.dumps([redacted_account], indent=2)

@mcp.tool()
def get_transactions(start_date: str = None, end_date: str = None) -> str:
    """
    Returns the list of historical transactions within a date range, with PII redacted.
    Parameters:
    - start_date: str (YYYY-MM-DD), optional start filter
    - end_date: str (YYYY-MM-DD), optional end filter
    """
    ledger = load_or_generate_ledger()
    txs = ledger["transactions"]
    
    filtered_txs = []
    for tx in txs:
        tx_date = tx["date"]
        if start_date and tx_date < start_date:
            continue
        if end_date and tx_date > end_date:
            continue
        filtered_txs.append(PIIRedactor.redact_transaction(tx))
        
    return json.dumps(filtered_txs, indent=2)

@mcp.tool()
def get_recurring_bills() -> str:
    """
    Returns detected monthly recurring bill payment patterns.
    """
    # Hardcoded/rule-based detection on our ledger patterns for demo simplicity
    bills = [
        {"amount": 1200.00, "day_of_month": 1, "description": "APARTMENTS RENT PAYMENT", "category": "Housing"},
        {"amount": 85.00, "day_of_month": 10, "description": "CITY POWER ELECTRIC", "category": "Utilities"},
        {"amount": 60.00, "day_of_month": 18, "description": "COMCAST INTERNET SERVICE", "category": "Utilities"},
        {"amount": 15.00, "day_of_month": 5, "description": "NETFLIX STREAMING", "category": "Entertainment"}
    ]
    return json.dumps(bills, indent=2)

@mcp.tool()
def get_income_sources() -> str:
    """
    Returns detected recurring paycheck payroll sources.
    """
    # Hardcoded/rule-based detection matching generator payroll structure
    income = [
        {
            "amount": -1100.00, 
            "frequency_days": 14, 
            "next_date": "2026-06-26", 
            "description": "ACME CORP PAYROLL", 
            "category": "Income"
        }
    ]
    return json.dumps(income, indent=2)

@mcp.tool()
def get_forecast_inputs() -> str:
    """
    Returns parameters for Monte Carlo simulation: the current balance and the 
    historical daily discretionary spend distribution pool.
    """
    ledger = load_or_generate_ledger()
    transactions = ledger["transactions"]
    balance = ledger["account"]["balances"]["current"]
    
    fixed_ids = get_fixed_transaction_ids(transactions)
    spend_pool = ForecastEngine.extract_daily_discretionary_spend(transactions, fixed_ids)
    
    return json.dumps({
        "current_balance": balance,
        "discretionary_spend_pool_size": len(spend_pool),
        "discretionary_spend_pool": spend_pool
    }, indent=2)

@mcp.tool()
def simulate_transaction_impact(amount: float, date: str) -> str:
    """
    Simulates a hypothetical future transaction of a specified amount on a target date,
    returning the resulting overdraft probability.
    Parameters:
    - amount: float, the dollar value of the simulated purchase
    - date: str (YYYY-MM-DD), the target date of the simulated purchase
    """
    ledger = load_or_generate_ledger()
    transactions = ledger["transactions"]
    balance = ledger["account"]["balances"]["current"]
    
    fixed_ids = get_fixed_transaction_ids(transactions)
    spend_pool = ForecastEngine.extract_daily_discretionary_spend(transactions, fixed_ids)
    
    # Load upcoming bills/income lists
    bills = json.loads(get_recurring_bills())
    income = json.loads(get_income_sources())
    
    # Run the Monte Carlo simulation
    res = ForecastEngine.simulate_paths(
        current_balance=balance,
        daily_discretionary_spend_pool=spend_pool,
        fixed_bills=bills,
        income_sources=income,
        start_date_str="2026-06-20", # Current simulated date
        simulation_days=14,
        num_paths=10000,
        simulated_purchase={"amount": amount, "date": date}
    )
    
    runway = ForecastEngine.calculate_runway(balance, transactions, bills, income)
    
    return json.dumps({
        "simulated_purchase": {"amount": amount, "date": date},
        "probability_of_overdraft": res["probability_of_overdraft"],
        "long_term_runway_months": runway
    }, indent=2)

@mcp.tool()
def get_live_price_index(category: str) -> str:
    """
    Retrieves or estimates current price change multipliers for 'gas' or 'groceries'.
    Returns a JSON string containing category, multiplier, and warning message.
    """
    cat = category.lower()
    if "gas" in cat or "fuel" in cat:
        return json.dumps({
            "category": "Travel",
            "multiplier": 1.18,
            "message": "AAA index indicates local gas prices have spiked by 18%."
        })
    elif "grocery" in cat or "groceries" in cat or "food" in cat:
        return json.dumps({
            "category": "Food and Drink",
            "multiplier": 1.07,
            "message": "Regional CPI indicators show food prices have risen by 7%."
        })
    return json.dumps({
        "category": "Discretionary",
        "multiplier": 1.03,
        "message": "General consumer price index shows a 3% baseline inflation."
    })

if __name__ == "__main__":
    mcp.run()
