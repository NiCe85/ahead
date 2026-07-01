import random
from datetime import datetime, timedelta
import json

class SeededLedgerGenerator:
    """
    Generates realistic, reproducible financial ledger data for evaluation.
    Enforces a paycheck-to-paycheck persona with typical bills and varying discretionary spend.
    """
    def __init__(self, seed=42):
        self.seed = seed
        random.seed(seed)
        
    def generate(self, days=180, end_date_str="2026-06-20", starting_balance=300.00):
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        start_date = end_date - timedelta(days=days)
        
        balance = starting_balance
        transactions = []
        
        # Define payroll (income)
        # Bi-weekly income of $1100.00. We will schedule it on specific Fridays.
        # Let's find the first Friday after start_date
        current_date = start_date
        while current_date.weekday() != 4:  # 4 is Friday
            current_date += timedelta(days=1)
            
        income_dates = []
        while current_date <= end_date:
            income_dates.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=14)
            
        # Define bills
        # Monthly Rent: $1200 on the 1st of the month
        # Electric bill: $85 on the 10th of the month
        # Internet bill: $60 on the 18th of the month
        # Streaming subscription: $15 on the 5th of the month
        
        current_date = start_date
        tx_counter = 1
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            day_of_month = current_date.day
            
            # 1. Income processing
            if date_str in income_dates:
                # Inflow is represented as negative in Plaid spec, let's keep inflows as negative
                amount = -1100.00
                balance -= amount  # subtracting negative adds to balance
                transactions.append({
                    "transaction_id": f"tx_inc_{tx_counter}",
                    "date": date_str,
                    "amount": amount,
                    "description": "ACME CORP PAYROLL",
                    "category": "Income",
                    "pending": False
                })
                tx_counter += 1
                
            # 2. Fixed Bills
            if day_of_month == 1:
                amount = 1200.00
                balance -= amount
                transactions.append({
                    "transaction_id": f"tx_bill_{tx_counter}",
                    "date": date_str,
                    "amount": amount,
                    "description": "APARTMENTS RENT PAYMENT",
                    "category": "Housing",
                    "pending": False
                })
                tx_counter += 1
                
            if day_of_month == 10:
                amount = 85.00
                balance -= amount
                transactions.append({
                    "transaction_id": f"tx_bill_{tx_counter}",
                    "date": date_str,
                    "amount": amount,
                    "description": "CITY POWER ELECTRIC",
                    "category": "Utilities",
                    "pending": False
                })
                tx_counter += 1
                
            if day_of_month == 18:
                amount = 60.00
                balance -= amount
                transactions.append({
                    "transaction_id": f"tx_bill_{tx_counter}",
                    "date": date_str,
                    "amount": amount,
                    "description": "COMCAST INTERNET SERVICE",
                    "category": "Utilities",
                    "pending": False
                })
                tx_counter += 1
                
            if day_of_month == 5:
                amount = 15.00
                balance -= amount
                transactions.append({
                    "transaction_id": f"tx_bill_{tx_counter}",
                    "date": date_str,
                    "amount": amount,
                    "description": "NETFLIX STREAMING",
                    "category": "Entertainment",
                    "pending": False
                })
                tx_counter += 1
                
            # 3. Discretionary Spending
            # To make it realistic:
            # - 40% chance of $0 spend days
            # - 50% chance of small spend (groceries, food, transport): $5 to $45
            # - 10% chance of larger spend (shopping, dining out, car check): $50 to $200
            rand_val = random.random()
            if rand_val < 0.40:
                # No discretionary spend
                pass
            elif rand_val < 0.90:
                amount = round(random.uniform(5.00, 45.00), 2)
                balance -= amount
                desc = random.choice([
                    "STARBUCKS COFFEE", "SAFEWAY GROCERY", "SHELL OIL", 
                    "UBER TRIP", "MCDONALD'S", "WALGREENS PHARMACY"
                ])
                cat = random.choice(["Food and Drink", "Groceries", "Travel", "Shops"])
                transactions.append({
                    "transaction_id": f"tx_disc_{tx_counter}",
                    "date": date_str,
                    "amount": amount,
                    "description": desc,
                    "category": cat,
                    "pending": False
                })
                tx_counter += 1
            else:
                amount = round(random.uniform(50.00, 200.00), 2)
                balance -= amount
                desc = random.choice([
                    "TARGET STORE", "LOCAL TAVERN RESTAURANT", "AMAZON.COM",
                    "BEST BUY CO", "PATAGONIA OUTDOORS"
                ])
                cat = random.choice(["Shops", "Food and Drink", "Entertainment"])
                transactions.append({
                    "transaction_id": f"tx_disc_{tx_counter}",
                    "date": date_str,
                    "amount": amount,
                    "description": desc,
                    "category": cat,
                    "pending": False
                })
                tx_counter += 1
                
            current_date += timedelta(days=1)
            
        # Reverse transactions so they are ordered chronologically or reverse-chronologically.
        # Standard Plaid returns them reverse-chronologically (newest first). Let's do that.
        transactions.reverse()
        
        account = {
            "account_id": "acc_sentinel_checking",
            "routing_number": "121000248",
            "account_number": "******7890",
            "name": "Sentinel checking",
            "type": "depository",
            "subtype": "checking",
            "balances": {
                "current": round(balance, 2),
                "available": round(balance, 2)
            }
        }
        
        return {
            "account": account,
            "transactions": transactions
        }

if __name__ == "__main__":
    generator = SeededLedgerGenerator()
    data = generator.generate()
    print(f"Generated {len(data['transactions'])} transactions.")
    print(f"Final Balance: ${data['account']['balances']['current']}")
