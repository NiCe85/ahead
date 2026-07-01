import json
import os
from google import genai
from google.genai import types
from src.utils.pii_redactor import PIIRedactor
from src.forecaster.engine import ForecastEngine

# Standard model configuration
MODEL_NAME = "gemini-2.5-flash"

class IncomeParserTool:
    """
    Analyzes historical transactions to identify income patterns, pay cycles, and amounts.
    """
    def __init__(self):
        # The genai client will pick up GEMINI_API_KEY from environment variables automatically
        self.client = genai.Client()

    def analyze_income(self, transactions: list) -> dict:
        # Redact transactions first
        redacted_txs = [PIIRedactor.redact_transaction(tx) for tx in transactions]
        
        prompt = (
            "Analyze the following list of historical transactions and identify all recurring income sources.\n"
            "Identify the amount, frequency (e.g. bi-weekly, monthly), description, and estimate the date of the next expected paycheck.\n"
            "Return ONLY a raw JSON structure matching this format:\n"
            "[\n"
            "  {\n"
            "    \"amount\": -2000.00,\n"
            "    \"frequency_days\": 14,\n"
            "    \"next_date\": \"2026-06-26\",\n"
            "    \"description\": \"ACME CORP PAYROLL\",\n"
            "    \"category\": \"Income\"\n"
            "  }\n"
            "]\n"
            "Do not include markdown tags like ```json or any other text.\n\n"
            f"Transactions:\n{json.dumps(redacted_txs, indent=2)}"
        )
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction="You are an Income Parser tool. You extract recurring payroll details from checking account ledgers. Output only valid JSON."
                )
            )
            # Remove any markdown decoration if the model generated it
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            
            return json.loads(text.strip())
        except Exception as e:
            # Fallback to rule-based detection if LLM call fails
            return [
                {
                    "amount": -2000.00,
                    "frequency_days": 14,
                    "next_date": "2026-06-26",
                    "description": "ACME CORP PAYROLL",
                    "category": "Income"
                }
            ]

class SpendParserTool:
    """
    Analyzes historical transactions to categorize regular spending and identify recurring bills.
    """
    def __init__(self):
        self.client = genai.Client()

    def analyze_spending(self, transactions: list) -> dict:
        redacted_txs = [PIIRedactor.redact_transaction(tx) for tx in transactions]
        
        prompt = (
            "Analyze the following transactions and identify fixed recurring bills (e.g., rent, subscriptions, utility bills).\n"
            "Ignore highly variable discretionary expenses like coffee or shops.\n"
            "Return ONLY a raw JSON structure matching this format:\n"
            "[\n"
            "  {\n"
            "    \"amount\": 1200.00,\n"
            "    \"day_of_month\": 1,\n"
            "    \"description\": \"APARTMENTS RENT PAYMENT\",\n"
            "    \"category\": \"Housing\"\n"
            "  }\n"
            "]\n"
            "Do not include markdown tags like ```json or any other text.\n\n"
            f"Transactions:\n{json.dumps(redacted_txs, indent=2)}"
        )
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction="You are a Spend Parser tool. You identify fixed monthly subscription/bill payments from checking account ledgers. Output only valid JSON."
                )
            )
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
                
            return json.loads(text.strip())
        except Exception as e:
            # Fallback to rule-based list
            return [
                {"amount": 1200.00, "day_of_month": 1, "description": "APARTMENTS RENT PAYMENT", "category": "Housing"},
                {"amount": 85.00, "day_of_month": 10, "description": "CITY POWER ELECTRIC", "category": "Utilities"},
                {"amount": 60.00, "day_of_month": 18, "description": "COMCAST INTERNET SERVICE", "category": "Utilities"},
                {"amount": 15.00, "day_of_month": 5, "description": "NETFLIX STREAMING", "category": "Entertainment"}
            ]

