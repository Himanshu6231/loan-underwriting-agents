"""Affordability Agent. Rule: (new EMI + existing EMIs) <= 40% of net monthly income."""
from agents.base import BaseAgent, kernel_function

LIMIT = 0.40


def emi_to_income_ratio(emi: float, existing: float, income: float) -> float:
    return round((emi + existing) / income, 4)


def affordability_verdict(ratio: float, limit: float = LIMIT) -> bool:
    return ratio <= limit


class AffordabilityPlugin:
    @kernel_function(name="emi_to_income_ratio", description="Total obligations / income")
    def emi_to_income_ratio(self, emi: float, existing: float, income: float) -> float:
        return emi_to_income_ratio(emi, existing, income)

    @kernel_function(name="affordability_verdict", description="True if ratio within limit")
    def affordability_verdict(self, ratio: float, limit: float = LIMIT) -> bool:
        return affordability_verdict(ratio, limit)


class AffordabilityAgent(BaseAgent):
    name, plugin_name = "AffordabilityAgent", "affordability"

    def __init__(self):
        super().__init__(AffordabilityPlugin())

    async def run(self, rec):
        rec.ratio = await self.tool(rec, "emi_to_income_ratio", emi=rec.emi,
                                    existing=rec.existing_emis, income=rec.income)
        rec.affordable = await self.tool(rec, "affordability_verdict", ratio=rec.ratio, limit=LIMIT)
        return rec.affordable
