"""Counter-Offer Agent: when affordability fails, propose what WOULD pass. Tools: max_affordable_amount, min_tenure_months."""
import math
from agents.base import BaseAgent, kernel_function
from agents.emi_agent import compute_emi

LIMIT = 0.40


def max_affordable_amount(income: float, existing_emis: float, annual_rate: float, months: int, limit: float = LIMIT) -> float:
    room = limit * income - existing_emis
    if room <= 0:
        return 0.0
    r = annual_rate / 12 / 100
    g = (1 + r) ** months
    principal = room * (g - 1) / (r * g) if r else room * months
    return float(math.floor(principal / 1000) * 1000)


def min_tenure_months(amount: float, income: float, existing_emis: float, annual_rate: float,
                      max_months: int, limit: float = LIMIT) -> int:
    for m in range(6, max_months + 1):
        if (compute_emi(amount, annual_rate, m) + existing_emis) / income <= limit:
            return m
    return 0   # 0 = no tenure within the cap makes it affordable


class CounterOfferPlugin:
    @kernel_function(name="max_affordable_amount", description="Largest amount that passes the affordability rule")
    def max_affordable_amount(self, income: float, existing_emis: float, annual_rate: float, months: int, limit: float = LIMIT) -> float:
        return max_affordable_amount(income, existing_emis, annual_rate, months, limit)

    @kernel_function(name="min_tenure_months", description="Shortest tenure that passes the affordability rule (0 = none)")
    def min_tenure_months(self, amount: float, income: float, existing_emis: float, annual_rate: float,
                          max_months: int, limit: float = LIMIT) -> int:
        return min_tenure_months(amount, income, existing_emis, annual_rate, max_months, limit)


class CounterOfferAgent(BaseAgent):
    name, plugin_name = "CounterOfferAgent", "counter_offer"

    def __init__(self):
        super().__init__(CounterOfferPlugin())

    async def run(self, rec, max_months: int = 84):
        amt = await self.tool(rec, "max_affordable_amount", income=rec.income, existing_emis=rec.existing_emis,
                              annual_rate=rec.annual_rate, months=rec.tenure_months, limit=LIMIT)
        ten = await self.tool(rec, "min_tenure_months", amount=rec.amount, income=rec.income,
                              existing_emis=rec.existing_emis, annual_rate=rec.annual_rate, max_months=max_months, limit=LIMIT)
        rec.counter_offer = {"max_amount_at_requested_tenure": amt, "min_tenure_for_requested_amount": ten or None,
                             "tenure_cap_months": max_months}
        return rec.counter_offer
