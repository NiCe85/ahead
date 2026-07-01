import random
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

class ForecastEngine:
    """
    Core forecasting engine that runs lookahead-free Monte-Carlo simulations.
    Bootstraps historical daily discretionary spend distributions to forecast balance trajectories.
    """
    
    @staticmethod
    def extract_daily_discretionary_spend(transactions: list, recurring_ids: set, category_multipliers: dict = None) -> list:
        """
        Determines daily discretionary spending from transaction history.
        Subtracts fixed recurring bills and income.
        Optionally scales amounts for specific categories (e.g. for inflation/price shocks).
        """
        if not transactions:
            return [0.0]
            
        sanitized = []
        for tx in transactions:
            dt_str = tx.get("date")
            if isinstance(dt_str, str):
                try:
                    datetime.strptime(dt_str[:10], "%Y-%m-%d")
                    sanitized.append(tx)
                except ValueError:
                    continue
            else:
                sanitized.append(tx)
                
        if not sanitized:
            return [0.0]
            
        df = pd.DataFrame(sanitized)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        
        if df.empty:
            return [0.0]
            
        # Filter out income (inflows are <= 0 in Plaid standard)
        # Filter out fixed recurring transactions (identified by transaction_id in recurring_ids)
        discretionary_df = df[
            (df['amount'] > 0) & 
            (~df['transaction_id'].isin(recurring_ids))
        ].copy()
        
        # Apply category multipliers if provided (for inflation scaling)
        if category_multipliers:
            for cat, mult in category_multipliers.items():
                mask = discretionary_df['category'] == cat
                discretionary_df.loc[mask, 'amount'] = discretionary_df.loc[mask, 'amount'] * mult
        
        # Group by date and sum
        daily_sums = discretionary_df.groupby('date')['amount'].sum()
        
        # Reindex to cover the full date range to include days with $0 spend
        all_dates = pd.date_range(start=df['date'].min(), end=df['date'].max(), freq='D')
        daily_sums = daily_sums.reindex(all_dates, fill_value=0.0)
        
        return daily_sums.tolist()

    @staticmethod
    def simulate_paths(
        current_balance: float,
        daily_discretionary_spend_pool: list,
        fixed_bills: list,      # List of dicts: {"amount": float, "day_of_month": int}
        income_sources: list,   # List of dicts: {"amount": float, "day_of_month": int} or similar
        start_date_str: str,
        simulation_days: int = 14,
        num_paths: int = 10000,
        simulated_purchase: dict = None, # {"amount": float, "date": str}
        seed: int = 42
    ) -> dict:
        """
        Runs Monte-Carlo simulations using numpy vectorization for speed and accuracy.
        """
        np.random.seed(seed)
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        
        # Pre-calculate scheduled income and fixed bills for each day in the simulation window
        dates = [start_date + timedelta(days=i) for i in range(simulation_days)]
        fixed_flows = np.zeros(simulation_days)
        
        # Separate Plaid income representation (negative = inflow) and standard representations
        for i, dt in enumerate(dates):
            # Check fixed bills
            for bill in fixed_bills:
                if dt.day == bill.get("day_of_month"):
                    fixed_flows[i] -= bill.get("amount") # outflow
            
            # Check recurring income
            for inc in income_sources:
                # Plaid income is stored negative. If positive representation is passed, make sure we adjust.
                amt = inc.get("amount")
                # Handle bi-weekly income schedule
                if "next_date" in inc and "frequency_days" in inc:
                    try:
                        next_dt = datetime.strptime(str(inc["next_date"])[:10], "%Y-%m-%d")
                    except ValueError:
                        next_dt = start_date
                    freq = inc["frequency_days"]
                    # If this simulation date matches a pay date
                    days_diff = (dt - next_dt).days
                    if days_diff >= 0 and days_diff % freq == 0:
                        fixed_flows[i] += abs(amt) # inflow
                elif dt.day == inc.get("day_of_month"):
                    fixed_flows[i] += abs(amt) # inflow
                    
            # Check simulated purchase
            if simulated_purchase:
                try:
                    pur_dt = datetime.strptime(str(simulated_purchase["date"])[:10], "%Y-%m-%d")
                except ValueError:
                    pur_dt = start_date
                if dt.date() == pur_dt.date():
                    fixed_flows[i] -= simulated_purchase["amount"] # outflow

        # Convert spend pool to a numpy array
        pool = np.array(daily_discretionary_spend_pool)
        if len(pool) == 0:
            pool = np.array([0.0])
            
        # Draw random discretionary spend matrix: shape (num_paths, simulation_days)
        rand_spends = np.random.choice(pool, size=(num_paths, simulation_days))
        
        # Setup paths matrix: shape (num_paths, simulation_days + 1)
        paths = np.zeros((num_paths, simulation_days + 1))
        paths[:, 0] = current_balance
        
        # Cumulative simulation
        for i in range(simulation_days):
            paths[:, i + 1] = paths[:, i] + fixed_flows[i] - rand_spends[:, i]
            
        # Analyze paths for overdraft
        # An overdraft occurs if any balance along a path goes < 0
        min_balances = np.min(paths[:, 1:], axis=1)
        overdraft_paths = np.sum(min_balances < 0)
        prob_overdraft = float(overdraft_paths / num_paths)
        
        # Calculate expected trajectory (median balance)
        median_trajectory = np.median(paths, axis=0).tolist()
        
        return {
            "probability_of_overdraft": prob_overdraft,
            "median_trajectory": median_trajectory,
            "min_balances": min_balances.tolist()
        }

    @staticmethod
    def calculate_runway(
        current_balance: float,
        transactions: list,
        recurring_bills: list,
        income_sources: list
    ) -> float:
        """
        Calculates the monthly net burn rate and long-term cash runway in months.
        Returns -1.0 if the user has a cash surplus (infinite runway).
        """
        if not transactions:
            return -1.0
            
        sanitized = []
        for tx in transactions:
            dt_str = tx.get("date")
            if isinstance(dt_str, str):
                try:
                    datetime.strptime(dt_str[:10], "%Y-%m-%d")
                    sanitized.append(tx)
                except ValueError:
                    continue
            else:
                sanitized.append(tx)
                
        if not sanitized:
            return -1.0
            
        df = pd.DataFrame(sanitized)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        
        if df.empty:
            return -1.0
            
        total_days = (df['date'].max() - df['date'].min()).days
        if total_days <= 0:
            total_days = 30
            
        # Compute total inflows and outflows
        total_inflow = abs(df[df['amount'] < 0]['amount'].sum())
        total_outflow = df[df['amount'] > 0]['amount'].sum()
        
        monthly_multiplier = 30.4375 / total_days
        avg_monthly_inflow = total_inflow * monthly_multiplier
        avg_monthly_outflow = total_outflow * monthly_multiplier
        
        net_monthly_burn = avg_monthly_outflow - avg_monthly_inflow
        
        if net_monthly_burn <= 0:
            return -1.0 # Infinite runway / cash positive
            
        runway_months = current_balance / net_monthly_burn
        return float(round(runway_months, 2))

    @staticmethod
    def predict_upcoming_refuels(transactions: list, current_date_str: str, forecast_days: int = 14) -> tuple:
        """
        Analyzes transactions to detect periodic discretionary expenses (e.g. Travel/Gas refuel).
        Projects expected dates within forecast window.
        Returns (list_of_injected_expenses, warning_message).
        """
        current_date = datetime.strptime(current_date_str[:10], "%Y-%m-%d")
        
        # Filter for discretionary travel/gas purchases
        gas_txs = []
        for tx in transactions:
            desc = tx.get("description", "").upper()
            cat = tx.get("category", "")
            # Look for indicators of gas station / fuel charges
            if ("SHELL" in desc or "OIL" in desc or "GAS" in desc or "FUEL" in desc or cat == "Travel") and tx.get("amount", 0) > 0:
                gas_txs.append(tx)
                
        if len(gas_txs) < 2:
            return [], ""
            
        # Sort chronologically to compute intervals
        gas_txs.sort(key=lambda x: x["date"])
        
        dates = [datetime.strptime(tx["date"][:10], "%Y-%m-%d") for tx in gas_txs]
        intervals = []
        for i in range(1, len(dates)):
            diff = (dates[i] - dates[i-1]).days
            if diff > 0:
                intervals.append(diff)
                
        if not intervals:
            return [], ""
            
        avg_interval = round(sum(intervals) / len(intervals))
        # Ensure a reasonable minimum interval (e.g. at least 3 days to avoid noise)
        if avg_interval < 3:
            avg_interval = 7
            
        avg_amount = sum(tx["amount"] for tx in gas_txs) / len(gas_txs)
        
        # Find latest gas refuel date
        latest_date = dates[-1]
        
        # Project future expected refuel dates
        projected = []
        next_date = latest_date + timedelta(days=avg_interval)
        
        end_projection_date = current_date + timedelta(days=forecast_days)
        while next_date <= end_projection_date:
            if next_date >= current_date:
                date_str = next_date.strftime("%Y-%m-%d")
                projected.append({
                    "amount": round(avg_amount, 2),
                    "day_of_month": next_date.day,
                    "description": "EXPECTED REFUEL SHOCK",
                    "category": "Travel",
                    "exact_date": date_str
                })
            next_date += timedelta(days=avg_interval)
            
        if projected:
            days_until = (datetime.strptime(projected[0]["exact_date"], "%Y-%m-%d") - current_date).days
            days_str = f"{days_until} days" if days_until > 1 else ("1 day" if days_until == 1 else "today")
            warning = (
                f"Predictive Alert: Ahead expects a ${avg_amount:.2f} Travel/Gas refuel charge in "
                f"{days_str} ({projected[0]['exact_date']}) based on your average {avg_interval}-day refuel cycle."
            )
            return projected, warning
            
        return [], ""

if __name__ == "__main__":
    # Test execution
    from src.data.generator import SeededLedgerGenerator
    gen = SeededLedgerGenerator()
    data = gen.generate(days=90, starting_balance=1000.00)
    
    # Identify fixed transaction IDs (Rent, netflix, electric, comcast)
    fixed_desc_substr = ["RENT", "ELECTRIC", "INTERNET", "NETFLIX", "PAYROLL"]
    fixed_ids = set()
    for tx in data['transactions']:
        for substr in fixed_desc_substr:
            if substr in tx['description']:
                fixed_ids.add(tx['transaction_id'])
                
    spend_pool = ForecastEngine.extract_daily_discretionary_spend(data['transactions'], fixed_ids)
    
    # Configure upcoming bills & income
    bills = [
        {"amount": 1200.00, "day_of_month": 1},
        {"amount": 85.00, "day_of_month": 10},
        {"amount": 60.00, "day_of_month": 18},
        {"amount": 15.00, "day_of_month": 5}
    ]
    # Bi-weekly income of 2000.00 starting 2026-06-26
    income = [
        {"amount": -2000.00, "frequency_days": 14, "next_date": "2026-06-26"}
    ]
    
    res = ForecastEngine.simulate_paths(
        current_balance=data['account']['balances']['current'],
        daily_discretionary_spend_pool=spend_pool,
        fixed_bills=bills,
        income_sources=income,
        start_date_str="2026-06-20",
        simulation_days=14
    )
    
    print(f"Prob of Overdraft: {res['probability_of_overdraft'] * 100:.2f}%")
    runway = ForecastEngine.calculate_runway(
        data['account']['balances']['current'],
        data['transactions'],
        bills,
        income
    )
    print(f"Cash Runway (months): {runway if runway != -1 else 'Infinite'}")
