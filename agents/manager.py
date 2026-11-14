"""Underwriting Manager: delegates to workers, halts on missing income, decides."""
from agents.base import BaseAgent, kernel_function
from agents.document_agent import DocumentAgent
from agents.emi_agent import EmiAgent
from agents.affordability_agent import AffordabilityAgent
from agents.credit_agent import CreditAgent
from llm import ask
from state import ApplicantRecord


def decide_rule(income_ok: bool, affordable: bool, defaults: int, missed: int) -> dict:
    if not income_ok:
        return {"decision": "refer", "reasons": ["required data missing (e.g. income) - not assumed, referred to human underwriter"]}
    reasons = []
    if defaults > 0:
        reasons.append("prior default on record")
    if not affordable:
        reasons.append("obligations exceed 40% of net income")
    if reasons:
        return {"decision": "decline", "reasons": reasons}
    if missed >= 2:
        return {"decision": "refer", "reasons": ["repeated missed payments need human review"]}
    return {"decision": "sanction", "reasons": ["affordability passes and no credit red flags"]}


def format_justification(decision: str, reasons: str, emi: float, ratio: float) -> str:
    emi_txt = f"EMI Rs {emi:,.2f}" if emi else "no EMI computed"
    ratio_txt = f", total obligations at {ratio*100:.1f}% of net income (limit 40%)" if ratio else ""
    return f"Decision: {decision}. {emi_txt}{ratio_txt}. Reason: {reasons}."


class ManagerPlugin:
    @kernel_function(name="decide_rule", description="Rule-based sanction/decline/refer")
    def decide_rule(self, income_ok: bool, affordable: bool, defaults: int, missed: int) -> dict:
        return decide_rule(income_ok, affordable, defaults, missed)

    @kernel_function(name="format_justification", description="Fact-only justification text")
    def format_justification(self, decision: str, reasons: str, emi: float, ratio: float) -> str:
        return format_justification(decision, reasons, emi, ratio)


class UnderwritingManager(BaseAgent):
    name, plugin_name = "UnderwritingManager", "manager"

    def __init__(self):
        super().__init__(ManagerPlugin())
        self.document, self.emi = DocumentAgent(), EmiAgent()
        self.afford, self.credit = AffordabilityAgent(), CreditAgent()

    async def delegate(self, rec, worker):
        rec.post(self.name, "delegate", {"to": worker.name})
        return await worker.run(rec)

    async def underwrite(self, text: str) -> ApplicantRecord:
        rec = ApplicantRecord(raw_text=text)
        rec.post(self.name, "received_application", {"chars": len(text)})
        income_ok = await self.delegate(rec, self.document)
        complete = income_ok and rec.amount and rec.tenure_months
        if not complete:                      # HALT: never assume missing data
            rec.post(self.name, "halt", {"missing": [k for k in ("income", "amount", "tenure_months")
                                                      if not getattr(rec, k)]})
            out = await self.tool(rec, "decide_rule", income_ok=False, affordable=False, defaults=0, missed=0)
        else:
            await self.delegate(rec, self.emi)
            await self.delegate(rec, self.afford)
            await self.delegate(rec, self.credit)
            h = rec.credit
            out = await self.tool(rec, "decide_rule", income_ok=True, affordable=bool(rec.affordable),
                                  defaults=h.get("defaults", 0), missed=h.get("missed_payments_12m", 0))
        rec.decision, rec.reasons = out["decision"], out["reasons"]
        text_j = await self.tool(rec, "format_justification", decision=rec.decision,
                                 reasons="; ".join(rec.reasons), emi=rec.emi or 0.0, ratio=rec.ratio or 0.0)
        # Optional LLM polish, restricted to the facts above.
        polished = await ask("Rewrite as ONE short paragraph for a loan file. Use ONLY the facts given; "
                             "do not add numbers or reasons.", text_j)
        rec.justification = polished.strip() if polished else text_j
        rec.post(self.name, "final_decision", {"decision": rec.decision})
        return rec
