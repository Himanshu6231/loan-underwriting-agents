"""Credit-History Agent: recalls long-term memory. Tools: lookup_prior_records, flag_red_flags."""
from agents.base import BaseAgent, kernel_function
from memory import get_profile


def lookup_prior_records(name: str) -> dict:
    """Reads the long-term memory store (seeded history + every earlier decision)."""
    return get_profile(name)


def flag_red_flags(defaults: int, missed_payments_12m: int, active_loans: int, past_declines: int = 0) -> list:
    flags = []
    if defaults > 0:
        flags.append("prior_default")
    if missed_payments_12m >= 2:
        flags.append("repeated_missed_payments")
    if active_loans > 3:
        flags.append("too_many_active_loans")
    if past_declines >= 2:
        flags.append("repeated_declines")
    return flags


class CreditPlugin:
    @kernel_function(name="lookup_prior_records", description="Recall applicant history from long-term memory")
    def lookup_prior_records(self, name: str) -> dict:
        return lookup_prior_records(name)

    @kernel_function(name="flag_red_flags", description="Derive red flags from remembered history")
    def flag_red_flags(self, defaults: int, missed_payments_12m: int, active_loans: int, past_declines: int = 0) -> list:
        return flag_red_flags(defaults, missed_payments_12m, active_loans, past_declines)


class CreditAgent(BaseAgent):
    name, plugin_name = "CreditHistoryAgent", "credit"

    def __init__(self):
        super().__init__(CreditPlugin())

    async def run(self, rec):
        rec.credit = await self.tool(rec, "lookup_prior_records", name=rec.name or "")
        h = rec.credit
        rec.credit_flags = await self.tool(rec, "flag_red_flags", defaults=h.get("defaults", 0),
                                           missed_payments_12m=h.get("missed_payments_12m", 0),
                                           active_loans=h.get("active_loans", 0),
                                           past_declines=h.get("past_declines", 0))
        return rec.credit_flags
