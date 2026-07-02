import json
import urllib.request
import time
import sys

def post_transaction(amount, description, category, date):
    url = "http://127.0.0.1:8000/api/transactions"
    payload = {
        "amount": amount,
        "description": description,
        "category": category,
        "date": date
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, 
        data=data, 
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"\n[ERROR] Failed to connect to API: {e}")
        print("Make sure the backend is running at http://127.0.0.1:8000!")
        return None

def main():
    print("==================================================")
    print("           AHEAD DEMO COMPANION FEED              ")
    print("==================================================")
    print("This utility feeds simulated transactions into your")
    print("live ledger to demonstrate Ahead's real-time")
    print("forecasting, refuel predictions, and coaching.")
    print("--------------------------------------------------")
    
    # Proactively offer to reset the ledger
    reset_choice = input("Would you like to reset the ledger to its baseline first? (y/n) [default: y]: ").strip().lower()
    if reset_choice in ["", "y", "yes"]:
        import os
        # Path to ledger.json
        WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
        LEDGER_PATH = os.path.join(WORKSPACE_DIR, "data", "ledger.json")
        if os.path.exists(LEDGER_PATH):
            try:
                os.remove(LEDGER_PATH)
                print(" ✅ Ledger successfully reset to baseline! (A new one will generate automatically on next reload)")
            except Exception as e:
                print(f" ❌ Failed to delete ledger.json: {e}")
        else:
            print(" ✅ Ledger is already at baseline (ledger.json doesn't exist).")
    
    # 3 demo events
    events = [
        {
            "amount": 32.40,
            "description": "SHELL OIL #48927",
            "category": "Travel",
            "date": "2026-06-21",
            "narrative": "A Shell Refuel charge of $32.40.\n* Demonstrates: Proactive refuel predictor detecting your travel pattern and updating the cashlow curve."
        },
        {
            "amount": 74.20,
            "description": "WHOLEFOODS MARKET",
            "category": "Food and Drink",
            "date": "2026-06-22",
            "narrative": "A grocery charge of $74.20.\n* Demonstrates: Immediate balance updates, discretionary spend pool recalculation, and updated coaching advice."
        },
        {
            "amount": 15.49,
            "description": "NETFLIX.COM DIGITAL SUB",
            "category": "Entertainment",
            "date": "2026-06-23",
            "narrative": "A subscription charge of $15.49.\n* Demonstrates: Spend parser picking up recurring digital items and adjusting fixed bills."
        }
    ]
    
    for i, ev in enumerate(events, 1):
        print(f"\n👉 [Event {i}/{len(events)}]")
        print(f"   Description : {ev['description']}")
        print(f"   Amount      : ${ev['amount']:.2f}")
        print(f"   Category    : {ev['category']}")
        print(f"   Date        : {ev['date']}")
        print(f"\n   What to watch in the UI:")
        print(f"   {ev['narrative']}")
        
        input(f"\n   [Press ENTER to feed this transaction to the ledger]...")
        
        print("   Sending transaction...", end="", flush=True)
        res = post_transaction(ev["amount"], ev["description"], ev["category"], ev["date"])
        if res:
            print(" ✅ SUCCESS!")
            print(f"   New Balance: ${res['updated_balance']:.2f}")
            time.sleep(0.5)
        else:
            sys.exit(1)
            
    print("\n==================================================")
    print("🎉 All demo transactions successfully processed!")
    print("Ahead dashboard is now fully updated and calibrated.")
    print("==================================================")

if __name__ == "__main__":
    main()
