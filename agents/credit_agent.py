"""Credit-History Agent: checks the prior-record store (memory). Tools: lookup_prior_records, flag_red_flags."""
import json, os
from agents.base import BaseAgent, kernel_function

STORE = os.path.join(os.path.dirname(__file__), "..", "data", "prior_records.json")


def lookup_prior_records(name: str) -> dict:
    with open(STORE, encoding="utf-8") as f:
        db = json.load(f)
    rec = db.get((name or "").strip().lower())
    return {"found": True, **rec} if rec else {"found": False}


def flag_red_flags(defaults: int, missed_payments_12m: int, active_loans: int) -> list:
    flags = []
    if defaults > 0:
        flags.append("prior_default")
    if missed_payments_12m >= 2:
        flags.append("repeated_missed_payments")
    if active_loans > 3:
        flags.append("too_many_active_loans")
    return flags


class CreditPlugin:
    @kernel_function(name="lookup_prior_records", description="Look up applicant in prior-record store")
    def lookup_prior_records(self, name: str) -> dict:
        return lookup_prior_records(name)

    @kernel_function(name="flag_red_flags", description="Derive red flags from history")
    def flag_red_flags(self, defaults: int, missed_payments_12m: int, active_loans: int) -> list:
        return flag_red_flags(defaults, missed_payments_12m, active_loans)


class CreditAgent(BaseAgent):
    name, plugin_name = "CreditHistoryAgent", "credit"

    def __init__(self):
        super().__init__(CreditPlugin())

    async def run(self, rec):
        rec.credit = await self.tool(rec, "lookup_prior_records", name=rec.name or "")
        h = rec.credit
        rec.credit_flags = await self.tool(rec, "flag_red_flags", defaults=h.get("defaults", 0),
                                           missed_payments_12m=h.get("missed_payments_12m", 0),
                                           active_loans=h.get("active_loans", 0))
        return rec.credit_flags
