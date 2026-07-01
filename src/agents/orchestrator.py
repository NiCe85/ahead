import json
import re
from google import genai
from google.genai import types

from src.utils.pii_redactor import PIIRedactor
from src.agents.specialists import IncomeParserTool, SpendParserTool
from src.agents.coach import CoachAgent
from src.forecaster.engine import ForecastEngine

MODEL_NAME = "gemini-2.5-flash"

class OrchestratorAgent:
    """
    Main coordinator agent.
    1. Extracts intent from user query (regular query vs. purchase simulation).
    2. Coordinates semantic parser tools (Income, Spend) and ForecastEngine.
    3. Triggers PII redaction.
    4. Hands data to Coach Agent for final response.
    """
    def __init__(self):
        self.client = genai.Client()
        self.income_tool = IncomeParserTool()
        self.spend_tool = SpendParserTool()
        self.coach_agent = CoachAgent()

    def parse_simulation_intent(self, query: str) -> dict:
        """
        Uses Gemini to extract purchase amount and date if the user wants to simulate a purchase.
        """
        prompt = (
            "Analyze this user query and determine if they want to simulate a hypothetical purchase.\n"
            "If yes, extract the amount (float) and estimated date (YYYY-MM-DD).\n"
            "If no date is mentioned, assume 2026-06-21.\n"
            "Return ONLY a JSON object like:\n"
            "{\n"
            "  \"is_simulation\": true,\n"
            "  \"amount\": 300.00,\n"
            "  \"date\": \"2026-06-25\"\n"
            "}\n"
            "If not a simulation, return:\n"
            "{\n"
            "  \"is_simulation\": false\n"
            "}\n"
            "Do not include markdown blocks or any other explanation.\n\n"
            f"Query: \"{query}\""
        )
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction="You are an intent parser. Extract financial simulation parameters. Output only valid JSON."
                )
            )
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
        except Exception:
            return {"is_simulation": False}

    async def process_query_to_dict(self, query: str, ledger_data: dict, persona: str = "gentle", mcp_client=None) -> dict:
        """
        Processes a user query by coordinating tools and returning a rich dict.
        """
        # 1. PII check on user input
        cleaned_query = PIIRedactor.redact_text(query)
        
        # 2. Extract purchase simulation parameters if any
        simulated_purchase = None
        is_baseline = query.lower() in ["", "baseline"]
        
        if not is_baseline:
            intent = self.parse_simulation_intent(cleaned_query)
            if intent.get("is_simulation"):
                simulated_purchase = {
                    "amount": intent["amount"],
                    "date": intent["date"]
                }
            
        # Extract data from ledger
        transactions = ledger_data["transactions"]
        current_balance = ledger_data["account"]["balances"]["current"]
        
        # 3. Analyze income and spending via semantic extraction tools
        income_sources = self.income_tool.analyze_income(transactions)
        fixed_bills = self.spend_tool.analyze_spending(transactions)
        
        # Check for proactive refuel events
        injected_refuels, refuel_warning = ForecastEngine.predict_upcoming_refuels(transactions, "2026-06-20", forecast_days=14)
        
        combined_fixed_bills = fixed_bills.copy()
        if injected_refuels:
            combined_fixed_bills.extend(injected_refuels)
            
        # Proactively check live inflation indices via MCP client
        category_multipliers = {}
        inflation_warnings = []
        
        if mcp_client:
            # Query travel/gas index
            try:
                res_str = await mcp_client.call_tool("get_live_price_index", {"category": "gas"})
                res_data = json.loads(res_str)
                if res_data.get("multiplier", 1.0) > 1.0:
                    category_multipliers[res_data["category"]] = res_data["multiplier"]
                    inflation_warnings.append(res_data["message"])
            except Exception:
                pass
                
            # Query food/groceries index
            try:
                res_str = await mcp_client.call_tool("get_live_price_index", {"category": "groceries"})
                res_data = json.loads(res_str)
                if res_data.get("multiplier", 1.0) > 1.0:
                    category_multipliers[res_data["category"]] = res_data["multiplier"]
                    inflation_warnings.append(res_data["message"])
            except Exception:
                pass
                
        category_multipliers = category_multipliers if category_multipliers else None
        inflation_context = " | ".join(inflation_warnings) if inflation_warnings else None
        
        # Extract spend pool for Monte Carlo
        # Find transaction IDs of fixed items to filter them from the discretionary spend pool
        fixed_ids = set()
        for tx in transactions:
            desc = tx.get("description", "").upper()
            for bill in fixed_bills:
                if bill["description"].upper() in desc:
                    fixed_ids.add(tx["transaction_id"])
            for inc in income_sources:
                if inc["description"].upper() in desc:
                    fixed_ids.add(tx["transaction_id"])
                    
        discretionary_pool = ForecastEngine.extract_daily_discretionary_spend(
            transactions, fixed_ids, category_multipliers=category_multipliers
        )
        
        # 4. Run Monte-Carlo simulations via Forecast Engine
        forecast_res = ForecastEngine.simulate_paths(
            current_balance=current_balance,
            daily_discretionary_spend_pool=discretionary_pool,
            fixed_bills=combined_fixed_bills,
            income_sources=income_sources,
            start_date_str="2026-06-20",
            simulation_days=14,
            num_paths=10000,
            simulated_purchase=simulated_purchase
        )
        
        # Calculate long-term cash runway
        runway = ForecastEngine.calculate_runway(
            current_balance=current_balance,
            transactions=transactions,
            recurring_bills=fixed_bills,
            income_sources=income_sources
        )
        
        # Combine warning contexts for the Coach Agent
        coaching_context = []
        if refuel_warning:
            coaching_context.append(refuel_warning)
        if inflation_context:
            coaching_context.append(inflation_context)
            
        combined_context_str = "\n".join(coaching_context) if coaching_context else None
        
        # 5. Delegate message drafting to Coach Agent (under skill rules)
        coaching_msg = self.coach_agent.generate_message(
            current_balance=current_balance,
            overdraft_prob=forecast_res["probability_of_overdraft"],
            runway_months=runway,
            simulated_purchase=simulated_purchase,
            persona=persona,
            inflation_context=combined_context_str
        )
        
        return {
            "original_query": query,
            "redacted_query": cleaned_query,
            "is_simulation": False if is_baseline else intent.get("is_simulation", False),
            "simulated_purchase": simulated_purchase,
            "probability_of_overdraft": forecast_res["probability_of_overdraft"],
            "trajectory": forecast_res["median_trajectory"],
            "long_term_runway_months": runway,
            "coaching_message": coaching_msg
        }

    async def process_query(self, query: str, ledger_data: dict, mcp_client=None) -> str:
        """
        Processes a user query by coordinating tools and specialist agents.
        """
        res_dict = await self.process_query_to_dict(query, ledger_data, persona="gentle", mcp_client=mcp_client)
        return res_dict["coaching_message"]
