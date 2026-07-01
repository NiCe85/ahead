import json
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.data.generator import SeededLedgerGenerator
from src.forecaster.engine import ForecastEngine

def run_evaluation():
    print("Initializing Lookahead-Free Backtest...")
    
    # 1. Generate full historical dataset (180 days of history)
    generator = SeededLedgerGenerator(seed=42)
    ledger_data = generator.generate(days=180, end_date_str="2026-06-20", starting_balance=300.00)
    
    full_txs = ledger_data["transactions"]
    starting_balance = 300.00
    
    # Convert transactions to DataFrame for easier slicing
    df = pd.DataFrame(full_txs)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    # Define start and end date of simulation evaluation window
    min_date = df['date'].min()
    max_date = df['date'].max()
    
    # We evaluate every 2 days from Day 40 to Day 165 to get a robust evaluation range
    eval_dates = []
    start_eval = min_date + timedelta(days=40)
    end_eval = max_date - timedelta(days=15)
    
    curr = start_eval
    while curr <= end_eval:
        eval_dates.append(curr)
        curr += timedelta(days=2)
        
    print(f"Evaluation Period: {start_eval.strftime('%Y-%m-%d')} to {end_eval.strftime('%Y-%m-%d')}")
    print(f"Running {len(eval_dates)} lookahead-free evaluations...")
    
    # Setup fixed bill templates matching generator
    bills_template = [
        {"amount": 1200.00, "day_of_month": 1},
        {"amount": 85.00, "day_of_month": 10},
        {"amount": 60.00, "day_of_month": 18},
        {"amount": 15.00, "day_of_month": 5}
    ]
    
    income_template = [
        # In generator, income is bi-weekly. We will calculate the next pay date relative to the evaluation date
        {"amount": -1100.00, "frequency_days": 14}
    ]
    
    # Track statistics
    predictions = []
    ground_truths = []
    
    for eval_dt in eval_dates:
        # Sliced data representing historical records UP TO the evaluation date (lookahead-free)
        sliced_txs_df = df[df['date'] <= eval_dt]
        sliced_txs = sliced_txs_df.to_dict('records')
        
        # Calculate balance at the evaluation date
        # Balance = starting_balance - net transaction amounts (since outflows are positive, inflows negative)
        inflows = abs(sliced_txs_df[sliced_txs_df['amount'] < 0]['amount'].sum())
        outflows = sliced_txs_df[sliced_txs_df['amount'] > 0]['amount'].sum()
        current_balance = starting_balance + inflows - outflows
        
        # Ground truth: Did the actual balance drop below zero in the next 14 days?
        future_txs_df = df[(df['date'] > eval_dt) & (df['date'] <= eval_dt + timedelta(days=14))]
        
        # Compute balance track day-by-day for the next 14 days
        temp_balance = current_balance
        overdrafted = False
        
        # Group by date to check balance at end of each day
        future_by_date = future_txs_df.groupby('date')
        for check_dt in pd.date_range(eval_dt + timedelta(days=1), eval_dt + timedelta(days=14)):
            if check_dt in future_by_date.groups:
                day_txs = future_by_date.get_group(check_dt)
                day_inflow = abs(day_txs[day_txs['amount'] < 0]['amount'].sum())
                day_outflow = day_txs[day_txs['amount'] > 0]['amount'].sum()
                temp_balance += day_inflow - day_outflow
            if temp_balance < 0:
                overdrafted = True
                break
                
        # Generate model forecast inputs
        fixed_ids = set()
        fixed_desc_substrs = ["RENT", "ELECTRIC", "INTERNET", "NETFLIX", "PAYROLL"]
        for tx in sliced_txs:
            for sub in fixed_desc_substrs:
                if sub in tx['description'].upper():
                    fixed_ids.add(tx['transaction_id'])
                    
        spend_pool = ForecastEngine.extract_daily_discretionary_spend(sliced_txs, fixed_ids)
        
        # Find next paycheck date prior/on/after eval_dt
        # Income occurs bi-weekly on Fridays. Let's find the next Friday paycheck date
        next_pay_date = eval_dt
        while True:
            # Check if this date has a payroll in full transaction history
            # (or calculate matching Fridays)
            if next_pay_date.weekday() == 4: # Friday
                break
            next_pay_date += timedelta(days=1)
            
        income_sources = [
            {
                "amount": -1100.00,
                "frequency_days": 14,
                "next_date": next_pay_date.strftime("%Y-%m-%d")
            }
        ]
        
        # Run Monte Carlo
        res = ForecastEngine.simulate_paths(
            current_balance=current_balance,
            daily_discretionary_spend_pool=spend_pool,
            fixed_bills=bills_template,
            income_sources=income_sources,
            start_date_str=eval_dt.strftime("%Y-%m-%d"),
            simulation_days=14,
            num_paths=5000, # 5000 per step for evaluation speed
            seed=42
        )
        
        prob = res["probability_of_overdraft"]
        predictions.append(prob)
        ground_truths.append(1 if overdrafted else 0)
        
    # Calculate performance metrics
    predictions = np.array(predictions)
    ground_truths = np.array(ground_truths)
    
    # 1. Brier Score
    brier_score = np.mean((predictions - ground_truths)**2)
    
    # 2. Recall & False Alarm (threshold of 10% probability triggers warning)
    threshold = 0.10
    alerts_triggered = (predictions >= threshold)
    
    true_positives = np.sum((alerts_triggered == 1) & (ground_truths == 1))
    false_positives = np.sum((alerts_triggered == 1) & (ground_truths == 0))
    false_negatives = np.sum((alerts_triggered == 0) & (ground_truths == 1))
    true_negatives = np.sum((alerts_triggered == 0) & (ground_truths == 0))
    
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    false_alarm_rate = false_positives / (false_positives + true_negatives) if (false_positives + true_negatives) > 0 else 0.0
    
    print("\n" + "="*50)
    print("EVALUATION RESULTS SUMMARY")
    print("="*50)
    print(f"Total Evaluations Conducted: {len(eval_dates)}")
    print(f"Brier Score (lower is better): {brier_score:.4f}")
    print(f"Alert Threshold: {threshold * 100:.0f}%")
    print(f"Warning Recall (overdrafts caught): {recall * 100:.1f}%")
    print(f"False-Alarm Rate: {false_alarm_rate * 100:.1f}%")
    
    # Calculate calibration
    bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    print("\nCalibration breakdown:")
    for i in range(len(bins)-1):
        bin_lower = bins[i]
        bin_upper = bins[i+1]
        mask = (predictions >= bin_lower) & (predictions < bin_upper)
        if np.sum(mask) > 0:
            actual_rate = np.mean(ground_truths[mask])
            print(f"  Bin {bin_lower*100:.0f}% - {bin_upper*100:.0f}%: Predicted mean ~{(bin_lower+bin_upper)/2*100:.0f}%, Actual Rate = {actual_rate*100:.1f}% ({np.sum(mask)} cases)")
    print("="*50 + "\n")
    
    # Save statistics
    stats = {
        "brier_score": float(brier_score),
        "recall": float(recall),
        "false_alarm_rate": float(false_alarm_rate),
        "total_evaluations": len(eval_dates)
    }
    
    stats_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "backtest_results.json")
    os.makedirs(os.path.dirname(stats_path), exist_ok=True)
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)

if __name__ == "__main__":
    run_evaluation()
