"""EMI Computation Agent: deterministic reducing-balance EMI. Tools: compute_emi, total_interest."""
from agents.base import BaseAgent, kernel_function


def compute_emi(principal: float, annual_rate: float, months: int) -> float:
    r = annual_rate / 12 / 100
    if r == 0:
        return round(principal / months, 2)
    g = (1 + r) ** months
    return round(principal * r * g / (g - 1), 2)


def total_interest(emi: float, months: int, principal: float) -> float:
    return round(emi * months - principal, 2)


class EmiPlugin:
    @kernel_function(name="compute_emi", description="Reducing-balance EMI")
    def compute_emi(self, principal: float, annual_rate: float, months: int) -> float:
        return compute_emi(principal, annual_rate, months)

    @kernel_function(name="total_interest", description="Total interest over the tenure")
    def total_interest(self, emi: float, months: int, principal: float) -> float:
        return total_interest(emi, months, principal)


class EmiAgent(BaseAgent):
    name, plugin_name = "EmiAgent", "emi"

    def __init__(self):
        super().__init__(EmiPlugin())

    async def run(self, rec):
        rec.emi = await self.tool(rec, "compute_emi", principal=rec.amount,
                                  annual_rate=rec.annual_rate, months=rec.tenure_months)
        await self.tool(rec, "total_interest", emi=rec.emi, months=rec.tenure_months, principal=rec.amount)
        return rec.emi
