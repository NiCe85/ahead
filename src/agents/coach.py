import os
import json
from google import genai
from google.genai import types

MODEL_NAME = "gemini-2.5-flash"

class CoachAgent:
    """
    Formulates a consumer-facing early warning or health update message.
    Governed strictly by coach_skill_<persona>.md; has NO direct tool access.
    """
    def __init__(self):
        self.client = genai.Client()
        self.skills_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "skills"
        )
        self.skills = {}
        for p in ["gentle", "strict", "analyst"]:
            path = os.path.join(self.skills_dir, f"coach_skill_{p}.md")
            if os.path.exists(path):
                with open(path, 'r') as f:
                    self.skills[p] = f.read()
            else:
                self.skills[p] = ""

    def generate_message(
        self,
        current_balance: float,
        overdraft_prob: float,
        runway_months: float,
        simulated_purchase: dict = None,
        persona: str = "gentle",
        inflation_context: str = None
    ) -> str:
        instructions = self.skills.get(persona.lower(), self.skills.get("gentle", ""))
        
        prompt = (
            f"Here are the computed cashflow statistics:\n"
            f"- Current Balance: ${current_balance:.2f}\n"
            f"- 14-day Probability of Overdraft: {overdraft_prob * 100:.1f}%\n"
            f"- Long-term Cash Runway: {runway_months if runway_months != -1 else 'Infinite'} months\n"
        )
        
        if simulated_purchase:
            prompt += (
                f"- Simulated Purchase: ${simulated_purchase['amount']:.2f} "
                f"on {simulated_purchase['date']}\n"
            )
            
        if inflation_context:
            prompt += f"- Live Price adjustment notice: {inflation_context}\n"
            
        prompt += (
            "\nDraft a coaching message to the user based on these numbers, strictly adhering "
            "to the tone, safety rules, and structure in the guidelines."
        )

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instructions
            )
        )
        
        return response.text.strip()
