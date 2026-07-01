import argparse
import sys
import os
from dotenv import load_dotenv

# Load env variables from .env if present
load_dotenv()

from src.data.generator import SeededLedgerGenerator
from src.agents.orchestrator import OrchestratorAgent
from src.mcp_server import load_or_generate_ledger

def main():
    parser = argparse.ArgumentParser(
        description="Ahead CLI — Proactive financial early-warning agent."
    )
    parser.add_argument(
        "--ask", 
        type=str, 
        required=True, 
        help="The query or purchase simulation statement (e.g. 'Can I buy a $300 television?')"
    )
    args = parser.parse_args()
    
    # Check for GEMINI_API_KEY
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        print("Please copy .env.example to .env and fill in your Gemini API key.", file=sys.stderr)
        sys.exit(1)
        
    print("⏳ Loading financial ledger and initializing specialists...")
    ledger_data = load_or_generate_ledger()
    
    orchestrator = OrchestratorAgent()
    print("💡 Processing query and executing cashflow simulations...")
    response = orchestrator.process_query(args.ask, ledger_data)
    
    print("\n" + "="*50)
    print("🛡️ AHEAD ADVICE")
    print("="*50)
    print(response)
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
