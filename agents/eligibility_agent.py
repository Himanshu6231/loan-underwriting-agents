"""Eligibility Agent: checks the applicant against each bank's criteria. Tools: list_banks, credit_band, check_eligibility.
Catalog (data/banks.json) is ILLUSTRATIVE sample data, not live bank rates."""
import json, os
from agents.base import BaseAgent, kernel_function
from agents.emi_agent import compute_emi

CATALOG = os.path.join(os.path.dirname(__file__), "..", "data", "banks.json")


def _products():
    with open(CATALOG, encoding="utf-8") as f:
        return json.load(f)["products"]


def list_banks(loan_type: str) -> list:
    return [p["bank"] for p in _products() if p["loan_type"] == loan_type]


def credit_band(defaults: int, missed: int, past_declines: int) -> str:
    if defaults > 0:
        return "blocked"
    if missed >= 2 or past_declines >= 2:
        return "subprime"
    if missed == 1 or past_declines == 1:
        return "standard"
    return "prime"


def pick_rate(p: dict, band: str):
    return {"prime": p["min_rate"], "standard": round((p["min_rate"] + p["max_rate"]) / 2, 2),
            "subprime": p["max_rate"]}.get(band)


def check_eligibility(bank: str, loan_type: str, income: float, amount: float, tenure_months: int,
                      existing_emis: float, band: str) -> dict:
    p = next(x for x in _products() if x["bank"] == bank and x["loan_type"] == loan_type)
    reasons = []
    if band == "blocked":
        reasons.append("prior default on record")
    if income < p["min_income"]:
        reasons.append(f"income below minimum Rs {p['min_income']:,}")
    if not p["min_amount"] <= amount <= p["max_amount"]:
        reasons.append(f"amount outside Rs {p['min_amount']:,} - Rs {p['max_amount']:,}")
    if tenure_months > p["max_tenure_months"]:
        reasons.append(f"tenure above maximum {p['max_tenure_months']} months")
    rate = pick_rate(p, band)
    emi = foir = None
    if rate and tenure_months > 0:
        emi = compute_emi(amount, rate, tenure_months)
        foir = round((emi + existing_emis) / income, 4)
        if foir > p["max_foir"]:
            reasons.append(f"EMI-to-income {foir:.0%} exceeds bank limit {p['max_foir']:.0%}")
    return {"bank": bank, "eligible": not reasons, "reasons": reasons, "rate": rate, "emi": emi, "foir": foir,
            "criteria": {"min_income": p["min_income"], "max_foir": p["max_foir"],
                         "max_tenure_months": p["max_tenure_months"]}}


class EligibilityPlugin:
    @kernel_function(name="list_banks", description="Banks offering a loan type")
    def list_banks(self, loan_type: str) -> list:
        return list_banks(loan_type)

    @kernel_function(name="credit_band", description="prime/standard/subprime/blocked from remembered history")
    def credit_band(self, defaults: int, missed: int, past_declines: int) -> str:
        return credit_band(defaults, missed, past_declines)

    @kernel_function(name="check_eligibility", description="Check one bank's criteria")
    def check_eligibility(self, bank: str, loan_type: str, income: float, amount: float, tenure_months: int,
                          existing_emis: float, band: str) -> dict:
        return check_eligibility(bank, loan_type, income, amount, tenure_months, existing_emis, band)


class EligibilityAgent(BaseAgent):
    name, plugin_name = "EligibilityAgent", "eligibility"

    def __init__(self):
        super().__init__(EligibilityPlugin())

    async def run(self, rec):
        h = rec.credit or {}
        rec.credit_band = await self.tool(rec, "credit_band", defaults=h.get("defaults", 0),
                                          missed=h.get("missed_payments_12m", 0), past_declines=h.get("past_declines", 0))
        banks = await self.tool(rec, "list_banks", loan_type=rec.loan_type)
        rec.eligibility = []
        for b in banks:
            r = await self.tool(rec, "check_eligibility", bank=b, loan_type=rec.loan_type, income=rec.income,
                                amount=rec.amount, tenure_months=rec.tenure_months, existing_emis=rec.existing_emis,
                                band=rec.credit_band)
            rec.eligibility.append(r)
        return [e for e in rec.eligibility if e["eligible"]]
