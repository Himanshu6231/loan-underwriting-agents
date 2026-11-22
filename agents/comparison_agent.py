"""Comparison Agent: prices every eligible bank and ranks them. Tools: price_option, rank_options."""
import json
from agents.base import BaseAgent, kernel_function
from agents.emi_agent import compute_emi


def price_option(bank: str, rate: float, amount: float, tenure_months: int, fee_pct: float) -> dict:
    emi = compute_emi(amount, rate, tenure_months)
    interest = round(emi * tenure_months - amount, 2)
    fee = round(amount * fee_pct / 100, 2)
    return {"bank": bank, "rate": rate, "emi": emi, "total_interest": interest,
            "processing_fee": fee, "total_cost": round(interest + fee, 2)}


def rank_options(options_json: str, priority: str = "total_cost") -> list:
    key = {"total_cost": "total_cost", "emi": "emi", "fee": "processing_fee", "rate": "rate"}.get(priority, "total_cost")
    return sorted(json.loads(options_json), key=lambda o: o[key])


class ComparisonPlugin:
    @kernel_function(name="price_option", description="EMI, interest, fee and total cost for one bank")
    def price_option(self, bank: str, rate: float, amount: float, tenure_months: int, fee_pct: float) -> dict:
        return price_option(bank, rate, amount, tenure_months, fee_pct)

    @kernel_function(name="rank_options", description="Rank priced options by total_cost/emi/fee/rate")
    def rank_options(self, options_json: str, priority: str = "total_cost") -> list:
        return rank_options(options_json, priority)


class ComparisonAgent(BaseAgent):
    name, plugin_name = "ComparisonAgent", "comparison"

    def __init__(self):
        super().__init__(ComparisonPlugin())

    async def run(self, rec, priority: str = "total_cost"):
        from agents.eligibility_agent import _products
        fees = {(p["bank"], p["loan_type"]): p["processing_fee_pct"] for p in _products()}
        priced = []
        for e in rec.eligibility:
            if e["eligible"]:
                priced.append(await self.tool(rec, "price_option", bank=e["bank"], rate=e["rate"], amount=rec.amount,
                                              tenure_months=rec.tenure_months, fee_pct=fees[(e["bank"], rec.loan_type)]))
        rec.options = await self.tool(rec, "rank_options", options_json=json.dumps(priced), priority=priority) if priced else []
        return rec.options
