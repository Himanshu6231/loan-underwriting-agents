"""Document Agent: application text -> structured fields. Tools: extract_fields, validate_income_present."""
import json, re
from agents.base import BaseAgent, kernel_function
from llm import ask


def _n(m):
    return float(m.group(1).replace(",", "").rstrip(",")) if m else None


def extract_fields(text: str) -> dict:
    cur = r"\s*(?:is|are|of|for|:|-)?\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)"
    name = re.search(r"applicant\s*[:\-]?\s*([A-Za-z][A-Za-z .]+?)\s*[.,;\n]", text, re.I)
    ten = re.search(r"(\d+)\s*(years?|yrs?|months?)", text, re.I)
    months = None
    if ten:
        months = int(ten.group(1)) * (12 if ten.group(2).lower().startswith("y") else 1)
    rate = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return {
        "name": name.group(1).strip() if name else None,
        "income": _n(re.search(r"income" + cur, text, re.I)),
        "existing_emis": _n(re.search(r"existing\s+emis?" + cur, text, re.I)),
        "amount": _n(re.search(r"(?:loan|amount|requesting|requested)" + cur, text, re.I)),
        "tenure_months": months,
        "annual_rate": float(rate.group(1)) if rate else None,
    }


def validate_income_present(income: float) -> bool:
    return income is not None and income > 0


def grounded(value, text: str) -> bool:
    """Hallucination guard: a number is accepted only if its digits appear in the source text."""
    return value is not None and str(int(value)) in text.replace(",", "")


class DocumentPlugin:
    @kernel_function(name="extract_fields", description="Regex-extract loan application fields")
    def extract_fields(self, text: str) -> dict:
        return extract_fields(text)

    @kernel_function(name="validate_income_present", description="True if income is a positive number")
    def validate_income_present(self, income: float) -> bool:
        return validate_income_present(income)


class DocumentAgent(BaseAgent):
    name, plugin_name = "DocumentAgent", "document"

    def __init__(self):
        super().__init__(DocumentPlugin())

    async def run(self, rec):
        f = await self.tool(rec, "extract_fields", text=rec.raw_text)
        # Optional LLM pass fills ONLY fields the regex missed, and only if grounded in the text.
        if any(f[k] is None for k in ("income", "amount", "tenure_months")):
            raw = await ask("Extract loan application fields. Return ONLY JSON with keys name, income, "
                            "existing_emis, amount, tenure_months, annual_rate. Use null if absent. Never guess.",
                            rec.raw_text)
            if raw:
                try:
                    j = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
                    for k in ("income", "existing_emis", "amount"):
                        if f[k] is None and j.get(k) is not None:
                            if grounded(j[k], rec.raw_text):
                                f[k] = float(j[k])
                            else:
                                rec.post(self.name, "llm_value_rejected", {"field": k, "value": j[k]})
                    if f["tenure_months"] is None and j.get("tenure_months"):
                        f["tenure_months"] = int(j["tenure_months"])
                except Exception as e:
                    rec.post(self.name, "llm_parse_failed", {"error": type(e).__name__})
        rec.name, rec.income = f["name"], f["income"]
        rec.existing_emis = f["existing_emis"] or 0.0
        rec.amount, rec.tenure_months = f["amount"], f["tenure_months"]
        if f["annual_rate"]:
            rec.annual_rate = f["annual_rate"]
        return await self.tool(rec, "validate_income_present", income=rec.income or 0.0)
