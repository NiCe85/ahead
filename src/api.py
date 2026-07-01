import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.mcp_server import load_or_generate_ledger, LEDGER_PATH, get_fixed_transaction_ids
from src.utils.pii_redactor import PIIRedactor
from src.forecaster.engine import ForecastEngine
from src.agents.orchestrator import OrchestratorAgent

from contextlib import asynccontextmanager
from src.mcp_client import MCPClient

mcp_client = MCPClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_client.connect()
    yield
    await mcp_client.disconnect()

app = FastAPI(title="Ahead API", lifespan=lifespan)

def generate_human_fallback_message(persona, overdraft_prob, runway, purchase=None, refuel_warning=""):
    prob_percent = overdraft_prob * 100
    inflation_msg = f"\n\n- Note: {refuel_warning}" if refuel_warning else ""
    
    if not purchase:
        if persona == "strict":
            if prob_percent >= 15:
                return (
                    f"Warning: Cashflow runway is critical. High risk of overdraft before payday ({prob_percent:.1f}% probability). "
                    f"Freeze all non-essential purchases immediately to preserve cushion.{inflation_msg}\n\n"
                    f"This is a cashflow awareness message, not formal financial advice."
                )
            else:
                return (
                    f"Checking is stable. Overdraft risk is low ({prob_percent:.1f}% probability). "
                    f"Maintain spending limits and do not add unnecessary expenses to stay safe.{inflation_msg}\n\n"
                    f"This is a cashflow awareness message, not formal financial advice."
                )
        elif persona == "analyst":
            if prob_percent >= 15:
                return (
                    f"Model indicates high probability of overdraft before payday ({prob_percent:.1f}% probability). "
                    f"Current discretionary spending pace exceeds safety limits. Action required.{inflation_msg}\n\n"
                    f"This is a cashflow awareness message, not formal financial advice."
                )
            else:
                return (
                    f"Cashflow trajectory modeled at P(overdraft) < 1% ({prob_percent:.3f}%). Runway is stable. "
                    f"Median balance remains well above baseline threshold.{inflation_msg}\n\n"
                    f"This is a cashflow awareness message, not formal financial advice."
                )
        else: # gentle / empathetic (default)
            if prob_percent >= 15:
                return (
                    f"Hey, let's take a look at things. We might hit a tight spot with a potential overdraft before payday "
                    f"({prob_percent:.1f}% chance). Don't stress—we can get ahead of it by holding off on extra spending this week.{inflation_msg}\n\n"
                    f"This is a cashflow awareness message, not formal financial advice."
                )
            else:
                return (
                    f"Hey! I've run the numbers on your cashflow and you're in a great spot. There's virtually zero risk of an "
                    f"overdraft before payday ({prob_percent:.1f}% chance). Keep doing what you're doing!{inflation_msg}\n\n"
                    f"This is a cashflow awareness message, not formal financial advice."
                )

    amt = purchase["amount"]
    if persona == "strict":
        if prob_percent >= 15:
            return (
                f"Don't do it. Spending ${amt:.2f} right now pushes overdraft risk to {prob_percent:.1f}% "
                f"and will lead to balance depletion. Wait for payday on June 26th.{inflation_msg}\n\n"
                f"This is a cashflow awareness message, not formal financial advice."
            )
        else:
            return (
                f"Approved. The ${amt:.2f} purchase won't break you. Projected low is safe, leaving you clear of overdraft. "
                f"Keep it disciplined.{inflation_msg}\n\n"
                f"This is a cashflow awareness message, not formal financial advice."
            )
    elif persona == "analyst":
        if prob_percent >= 15:
            return (
                f"Simulation: Adding ${amt:.2f} raises P(overdraft) to {prob_percent:.1f}%. "
                f"The P10 path dips negative, suggesting high sensitivity to this outflow.{inflation_msg}\n\n"
                f"This is a cashflow awareness message, not formal financial advice."
            )
        else:
            return (
                f"Simulation: Adding ${amt:.2f} keeps P(overdraft) at a safe {prob_percent:.1f}%. "
                f"Median trough remains within acceptable bounds.{inflation_msg}\n\n"
                f"This is a cashflow awareness message, not formal financial advice."
            )
    else: # gentle / empathetic (default)
        if prob_percent >= 15:
            return (
                f"Let's pause on the ${amt:.2f} purchase for a moment. Right now, it looks like it would push the overdraft "
                f"probability to {prob_percent:.1f}%. If it can wait until after payday, your cushion will thank you!{inflation_msg}\n\n"
                f"This is a cashflow awareness message, not formal financial advice."
            )
        else:
            return (
                f"You're good to go! The ${amt:.2f} purchase keeps you clear of overdraft risk "
                f"(projected risk is only {prob_percent:.1f}%). Nicely managed!{inflation_msg}\n\n"
                f"This is a cashflow awareness message, not formal financial advice."
            )

# Enable CORS for the Vite React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimulationRequest(BaseModel):
    amount: float
    date: str
    persona: str = "gentle"

class AskRequest(BaseModel):
    query: str
    persona: str = "gentle"

class TransactionRequest(BaseModel):
    amount: float
    description: str
    category: str
    date: str

@app.get("/api/ledger")
async def get_ledger(persona: str = "gentle"):
    """
    Returns the current balance, redacted transactions, recurring bills, and income sources.
    """
    ledger = load_or_generate_ledger()
    redacted_account = PIIRedactor.redact_account(ledger["account"])
    redacted_txs = [PIIRedactor.redact_transaction(tx) for tx in ledger["transactions"]]
    
    # We can calculate the runway directly
    fixed_ids = get_fixed_transaction_ids(ledger["transactions"])
    # Proactively apply the default index multipliers in fallback to match the orchestrator
    category_multipliers = {"Travel": 1.18, "Food and Drink": 1.07}
    spend_pool = ForecastEngine.extract_daily_discretionary_spend(
        ledger["transactions"], fixed_ids, category_multipliers=category_multipliers
    )
    
    # Using the standard bills and income list
    # Monthly Rent: $1200, Electric: $85, Internet: $60, Netflix: $15
    bills = [
        {"amount": 1200.00, "day_of_month": 1, "description": "APARTMENTS RENT PAYMENT", "category": "Housing"},
        {"amount": 85.00, "day_of_month": 10, "description": "CITY POWER ELECTRIC", "category": "Utilities"},
        {"amount": 60.00, "day_of_month": 18, "description": "COMCAST INTERNET SERVICE", "category": "Utilities"},
        {"amount": 15.00, "day_of_month": 5, "description": "NETFLIX STREAMING", "category": "Entertainment"}
    ]
    income = [
        {
            "amount": -1100.00, 
            "frequency_days": 14, 
            "next_date": "2026-06-26", 
            "description": "ACME CORP PAYROLL", 
            "category": "Income"
        }
    ]
    
    runway = ForecastEngine.calculate_runway(
        ledger["account"]["balances"]["current"],
        ledger["transactions"],
        bills,
        income
    )
    
    orchestrator = None
    if os.getenv("GEMINI_API_KEY"):
        try:
            orchestrator = OrchestratorAgent()
        except Exception:
            pass

    base_coaching_msg = ""
    base_overdraft_prob = 0.0
    base_trajectory = []
    
    if orchestrator:
        try:
            res_dict = await orchestrator.process_query_to_dict("baseline", ledger, persona=persona, mcp_client=mcp_client)
            base_coaching_msg = res_dict["coaching_message"]
            base_overdraft_prob = res_dict["probability_of_overdraft"]
            base_trajectory = res_dict["trajectory"]
        except Exception:
            orchestrator = None
            
    if not orchestrator:
        # Fallback path if orchestrator isn't set up or errors out
        # We must still calculate predicted refuels to align numbers
        injected_refuels, refuel_warning = ForecastEngine.predict_upcoming_refuels(ledger["transactions"], "2026-06-20", forecast_days=14)
        combined_fixed_bills = bills.copy()
        if injected_refuels:
            combined_fixed_bills.extend(injected_refuels)
            
        base_forecast = ForecastEngine.simulate_paths(
            current_balance=ledger["account"]["balances"]["current"],
            daily_discretionary_spend_pool=spend_pool,
            fixed_bills=combined_fixed_bills,
            income_sources=income,
            start_date_str="2026-06-20",
            simulation_days=14,
            num_paths=5000
        )
        base_overdraft_prob = base_forecast["probability_of_overdraft"]
        base_trajectory = base_forecast["median_trajectory"]
        
        inflation_warnings = [
            "AAA index indicates local gas prices spiked 18%",
            "Regional CPI indicators show food prices rose 7%"
        ]
        combined_warnings = [refuel_warning] if refuel_warning else []
        combined_warnings.extend(inflation_warnings)
        combined_warning_str = " | ".join(combined_warnings)
        base_coaching_msg = generate_human_fallback_message(persona, base_overdraft_prob, runway, refuel_warning=combined_warning_str)
        
    return {
        "account": redacted_account,
        "transactions": redacted_txs[:30], # Limit to recent 30 for UI density
        "recurring_bills": bills,
        "income_sources": income,
        "runway_months": runway,
        "base_overdraft_probability": base_overdraft_prob,
        "base_trajectory": base_trajectory,
        "base_coaching_message": base_coaching_msg
    }

@app.post("/api/transactions")
def add_transaction(req: TransactionRequest):
    """
    Permanently appends a transaction to the ledger, updates the balance, and saves.
    """
    ledger = load_or_generate_ledger()
    
    # Generate unique transaction ID
    tx_count = len(ledger["transactions"]) + 1
    new_tx = {
        "transaction_id": f"tx_user_{tx_count}_{int(datetime.now().timestamp())}",
        "date": req.date,
        "amount": req.amount,
        "description": req.description,
        "category": req.category,
        "pending": False
    }
    
    # Update current account balance
    # Plaid standard: positive amount represents outflow (decreases balance), negative represents inflow
    ledger["account"]["balances"]["current"] = round(
        ledger["account"]["balances"]["current"] - req.amount, 2
    )
    ledger["account"]["balances"]["available"] = ledger["account"]["balances"]["current"]
    
    # Insert at the beginning of the list (standard reverse-chronological order)
    ledger["transactions"].insert(0, new_tx)
    
    # Save back to file
    with open(LEDGER_PATH, 'w') as f:
        json.dump(ledger, f, indent=2)
        
    return {
        "status": "success",
        "new_transaction": PIIRedactor.redact_transaction(new_tx),
        "updated_balance": ledger["account"]["balances"]["current"]
    }

@app.post("/api/simulate")
def simulate_purchase(req: SimulationRequest):
    """
    Simulates a purchase and fetches the Coach Agent's recommendations.
    """
    ledger = load_or_generate_ledger()
    
    # Run the orchestrator on the simulation request
    # If GEMINI_API_KEY is not configured, we'll fall back to standard text advising
    orchestrator = None
    if os.getenv("GEMINI_API_KEY"):
        try:
            orchestrator = OrchestratorAgent()
        except Exception:
            pass
            
    # Load forecast inputs
    transactions = ledger["transactions"]
    balance = ledger["account"]["balances"]["current"]
    fixed_ids = get_fixed_transaction_ids(transactions)
    spend_pool = ForecastEngine.extract_daily_discretionary_spend(transactions, fixed_ids)
    
    # Recurring lists
    bills = [
        {"amount": 1200.00, "day_of_month": 1, "description": "APARTMENTS RENT PAYMENT", "category": "Housing"},
        {"amount": 85.00, "day_of_month": 10, "description": "CITY POWER ELECTRIC", "category": "Utilities"},
        {"amount": 60.00, "day_of_month": 18, "description": "COMCAST INTERNET SERVICE", "category": "Utilities"},
        {"amount": 15.00, "day_of_month": 5, "description": "NETFLIX STREAMING", "category": "Entertainment"}
    ]
    income = [
        {
            "amount": -1100.00, 
            "frequency_days": 14, 
            "next_date": "2026-06-26", 
            "description": "ACME CORP PAYROLL", 
            "category": "Income"
        }
    ]
    
    sim = {"amount": req.amount, "date": req.date}
    
    # Check for proactive refuels in simulation
    injected_refuels, refuel_warning = ForecastEngine.predict_upcoming_refuels(transactions, "2026-06-20", forecast_days=14)
    combined_bills = bills.copy()
    if injected_refuels:
        combined_bills.extend(injected_refuels)
        
    res = ForecastEngine.simulate_paths(
        current_balance=balance,
        daily_discretionary_spend_pool=spend_pool,
        fixed_bills=combined_bills,
        income_sources=income,
        start_date_str="2026-06-20",
        simulation_days=14,
        num_paths=5000,
        simulated_purchase=sim
    )
    
    runway = ForecastEngine.calculate_runway(balance, transactions, bills, income)
    
    advice = ""
    if orchestrator:
        advice = orchestrator.coach_agent.generate_message(
            current_balance=balance,
            overdraft_prob=res["probability_of_overdraft"],
            runway_months=runway,
            simulated_purchase=sim,
            persona=req.persona,
            inflation_context=refuel_warning
        )
    else:
        advice = generate_human_fallback_message(req.persona, res["probability_of_overdraft"], runway, purchase=sim, refuel_warning=refuel_warning)
        
    return {
        "probability_of_overdraft": res["probability_of_overdraft"],
        "trajectory": res["median_trajectory"],
        "long_term_runway_months": runway,
        "coaching_message": advice
    }

@app.post("/api/ask")
async def ask_ahead(req: AskRequest):
    """
    Ingests a natural language user query, redacts PII, extracts simulation parameters (if any),
    runs the Monte Carlo engine, and returns tone-calibrated recommendations.
    """
    ledger = load_or_generate_ledger()
    
    orchestrator = None
    if os.getenv("GEMINI_API_KEY"):
        try:
            orchestrator = OrchestratorAgent()
        except Exception:
            pass
            
    if not orchestrator:
        cleaned_query = PIIRedactor.redact_text(req.query)
        import re
        amount_match = re.search(r"\$(\d+(?:\.\d{2})?)|\b(\d+(?:\.\d{2})?)\b", cleaned_query)
        amount = 100.0
        if amount_match:
            amount = float(amount_match.group(1) or amount_match.group(2))
            
        sim = {"amount": amount, "date": "2026-06-21"}
        balance = ledger["account"]["balances"]["current"]
        transactions = ledger["transactions"]
        fixed_ids = get_fixed_transaction_ids(transactions)
        
        # Proactively apply the default index multipliers in fallback to match the orchestrator
        category_multipliers = {"Travel": 1.18, "Food and Drink": 1.07}
        inflation_msg = "AAA index indicates local gas prices spiked 18% | CPI food prices rose 7%"
            
        spend_pool = ForecastEngine.extract_daily_discretionary_spend(
            transactions, fixed_ids, category_multipliers=category_multipliers
        )
        
        bills = [
            {"amount": 1200.00, "day_of_month": 1, "description": "APARTMENTS RENT PAYMENT", "category": "Housing"},
            {"amount": 85.00, "day_of_month": 10, "description": "CITY POWER ELECTRIC", "category": "Utilities"},
            {"amount": 60.00, "day_of_month": 18, "description": "COMCAST INTERNET SERVICE", "category": "Utilities"},
            {"amount": 15.00, "day_of_month": 5, "description": "NETFLIX STREAMING", "category": "Entertainment"}
        ]
        income = [
            {
                "amount": -1100.00, 
                "frequency_days": 14, 
                "next_date": "2026-06-26", 
                "description": "ACME CORP PAYROLL", 
                "category": "Income"
            }
        ]
        
        res = ForecastEngine.simulate_paths(
            current_balance=balance,
            daily_discretionary_spend_pool=spend_pool,
            fixed_bills=bills,
            income_sources=income,
            start_date_str="2026-06-20",
            simulation_days=14,
            num_paths=5000,
            simulated_purchase=sim
        )
        
        runway = ForecastEngine.calculate_runway(balance, transactions, bills, income)
        
        advice = generate_human_fallback_message(req.persona, res["probability_of_overdraft"], runway, purchase=sim, refuel_warning=inflation_msg.strip(" []"))
        
        return {
            "original_query": req.query,
            "redacted_query": cleaned_query,
            "is_simulation": True,
            "simulated_purchase": sim,
            "probability_of_overdraft": res["probability_of_overdraft"],
            "trajectory": res["median_trajectory"],
            "long_term_runway_months": runway,
            "coaching_message": advice
        }
        
    try:
        res_dict = await orchestrator.process_query_to_dict(req.query, ledger, persona=req.persona, mcp_client=mcp_client)
        return res_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
