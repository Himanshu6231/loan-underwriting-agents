"""Advisor Agent: loan-type advice + recommendation from the ranked facts. Tools: loan_type_advice, build_advisory."""
import json
from collections import Counter
from agents.base import BaseAgent, kernel_function
from llm import ask

ADVICE = {
    "personal": "Personal loans are unsecured and cost more; a shorter tenure cuts total interest.",
    "home": "Home loans are secured and usually the cheapest; compare processing fees and prepayment terms.",
    "car": "Car loans are secured by the vehicle; check the down-payment requirement and prepayment charges.",
    "education": "Education loans often have moratorium periods and subsidies; check what the bank covers.",
}


def loan_type_advice(loan_type: str, amount: float, income: float) -> str:
    note = ADVICE.get(loan_type, "")
    if loan_type == "personal" and income and amount > 30 * income:
        note += " The amount is high for an unsecured loan; consider a smaller amount or a secured loan type."
    return note


def build_advisory(best_json: str, n_eligible: int, n_total: int, runner_up: str, top_reasons: str, advice: str, loan_type: str,
                   caveats: str = "") -> str:
    if best_json and best_json != "{}":
        b = json.loads(best_json)
        second = f" Next best: {runner_up}." if runner_up else ""
        note = f" Note: {caveats}." if caveats else ""
        return (f"Recommended: {b['bank']} {loan_type} loan at {b['rate']}% - EMI Rs {b['emi']:,.2f}, total cost Rs "
                f"{b['total_cost']:,.2f} (includes processing fee Rs {b['processing_fee']:,.2f}). "
                f"{n_eligible} of {n_total} banks are eligible.{second}{note} {advice}").strip()
    return f"No bank is currently eligible for this {loan_type} loan. Main reasons: {top_reasons}. {advice}".strip()


class AdvisorPlugin:
    @kernel_function(name="loan_type_advice", description="Advice specific to the loan type")
    def loan_type_advice(self, loan_type: str, amount: float, income: float) -> str:
        return loan_type_advice(loan_type, amount, income)

    @kernel_function(name="build_advisory", description="Fact-only advisory text")
    def build_advisory(self, best_json: str, n_eligible: int, n_total: int, runner_up: str,
                       top_reasons: str, advice: str, loan_type: str, caveats: str = "") -> str:
        return build_advisory(best_json, n_eligible, n_total, runner_up, top_reasons, advice, loan_type, caveats)


class AdvisorAgent(BaseAgent):
    name, plugin_name = "AdvisorAgent", "advisor"

    def __init__(self):
        super().__init__(AdvisorPlugin())

    async def run(self, rec):
        advice = await self.tool(rec, "loan_type_advice", loan_type=rec.loan_type, amount=rec.amount or 0.0, income=rec.income or 0.0)
        reasons = Counter(r for e in rec.eligibility for r in e["reasons"][:1])
        top = "; ".join(r for r, _ in reasons.most_common(2)) or "none"
        best = rec.options[0] if rec.options else {}
        runner = rec.options[1]["bank"] if len(rec.options) > 1 else ""
        text = await self.tool(rec, "build_advisory", best_json=json.dumps(best), n_eligible=len(rec.options),
                               n_total=len(rec.eligibility), runner_up=runner, top_reasons=top, advice=advice,
                               loan_type=rec.loan_type, caveats="; ".join(best.get("caveats", [])))
        polished = await ask("Rewrite as ONE short advisory paragraph for a loan applicant. Use ONLY the facts given; "
                             "do not add banks, numbers or claims.", text)
        rec.advisory = polished.strip() if polished else text
        return rec.advisory
