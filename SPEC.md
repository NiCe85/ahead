# Ahead Specification

This specification serves as the source of truth for the implementation of Ahead.

---

## 1. Data Schema: Financial Ledger
We operate on a local-first JSON ledger representing a single checking account.

### Account Structure
```json
{
  "account_id": "acc_12345",
  "routing_number": "121000248",
  "account_number": "******7890",
  "name": "Ahead Checking",
  "type": "depository",
  "subtype": "checking",
  "balances": {
    "current": 2450.75,
    "available": 2450.75
  }
}
```

### Transaction Structure
```json
{
  "transaction_id": "tx_987654",
  "date": "2026-06-15",
  "amount": 45.50,
  "description": "Starbucks Coffee #204",
  "category": "Food and Drink",
  "pending": false
}
```
*Note: Negative values represent inflows (e.g. payroll), matching standard Plaid formatting.*

---

## 2. MCP Server Tools
The Model Context Protocol (MCP) server exposes 7 read-only tools to the client.

| Tool Name | Parameters | Returns | Description |
|:---|:---|:---|:---|
| `get_accounts` | None | `List[Account]` | Returns checking accounts list. |
| `get_transactions` | `start_date: str, end_date: str` | `List[Transaction]` | Returns transactions in date range. |
| `get_recurring_bills` | None | `List[RecurringBill]` | Returns detected recurring payment patterns. |
| `get_income_sources` | None | `List[IncomeSource]` | Returns detected recurring payroll details. |
| `get_forecast_inputs` | None | `ForecastInputs` | Returns daily spend distribution parameters. |
| `simulate_transaction_impact`| `amount: float, date: str` | `SimulationResult` | Returns probability of overdraft with simulated cost. |
| `get_live_price_index` | `category: str` | `PriceIndex` | Returns inflation and commodity price multipliers. |

---

## 3. Agent Roles & Orchestrator Design

We employ a two-agent architecture for execution safety and concern separation:

### A. Orchestrator Agent (ADK)
Uses the Gemini model to parse user queries, determine if a simulated event is requested, extract amount/date, check for inflation keywords, invoke specialized tools, and delegate recommendations to the Coach. It runs automatically on page load or transaction updates to evaluate the baseline cashflow.

### B. Coach Agent (ADK)
* **Role:** Generates consumer-facing warning alerts and budget adjustments.
* **Skill:** Governed by `coach_skill.md` rules. Has 0 direct tool access to ensure execution safety. Supports dynamic swap between Empathetic, Strict, and Analyst styles, shifting the advice tone in real-time.

### C. Helper Tools (Refactored)
To maintain structural integrity and avoid "agents in name only" for deterministic extractions, transaction analysis resides in semantic tools:
* **Income Parser Tool:** Extracts income schedules and pay frequencies using LLM analysis.
* **Spend Parser Tool:** Extracts fixed bill deadlines and subscription costs.
* **Forecast Engine:** Simulates 10,000 balance paths locally using bootstrapped discretionary spending.
* **Proactive Refuel Predictor:** Automatically detects and projects periodic refuel schedules (like gas purchases), injecting them into the Monte Carlo simulation.
* **PII Redactor:** Sanitizes sensitive information locally before it reaches remote LLMs.

---

## 4. Forecasting Algorithm (Monte-Carlo & Bootstrap)

Let $B_0$ be the current balance at day $t=0$.
For a simulation path $p \in [1, N_{paths}]$ (where $N_{paths} \ge 10,000$):
For each day $d$ from $t=1$ to $t=14$:
1. Determine Scheduled Income $I(d)$ and Scheduled Bills $E_{fixed}(d)$ for that calendar date.
2. If the Proactive Refuel Predictor has projected an expected refuel cost $E_{refuel}$ on date $d$, inject $E_{refuel}$ directly into the fixed bills: $E_{fixed}(d) \leftarrow E_{fixed}(d) + E_{refuel}$.
3. Sample a random daily discretionary expense $E_{disc}(d)$ by drawing a value from the user's historical daily spend distribution $D_{disc}$.
4. Calculate the balance:
   $$B_{p}(d) = B_{p}(d-1) + I(d) - E_{fixed}(d) - E_{disc}(d)$$
5. If $B_p(d) < 0$, path $p$ is flagged as an **overdraft**.

The probability of overdraft $P(overdraft)$ is:
$$P(overdraft) = \frac{1}{N_{paths}} \sum_{p=1}^{N_{paths}} \mathbb{I}(\min_{d} B_{p}(d) < 0)$$

*Note: If inflation keywords (e.g. gas, groceries) are detected, transactions in the related category are scaled by the price index multiplier before building the spend distribution.*

---

## 5. Security & Privacy Policies
* **Least Privilege:** Specialized agents are not allowed arbitrary tools. The Coach agent has 0 tool bindings.
* **PII Filter:** Regular expressions intercept text. All routing numbers, accounts, and descriptors resembling SSNs are replaced with `[REDACTED]` or masked.
* **Read-Only Database:** Connection pool configuration enforces `readonly` mode on sandbox connections.
