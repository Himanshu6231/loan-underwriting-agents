"""Shared applicant record (memory) + append-only run log."""
import json, os, time
from dataclasses import dataclass, field

RUN_LOG = os.getenv("RUN_LOG", os.path.join(os.path.dirname(__file__), "run_log.jsonl"))


def log_event(entry: dict) -> None:
    """Append-only: file is only ever opened in 'a' mode."""
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


@dataclass
class ApplicantRecord:
    raw_text: str
    name: str = None
    income: float = None
    existing_emis: float = 0.0
    amount: float = None
    tenure_months: int = None
    annual_rate: float = 10.5
    emi: float = None
    ratio: float = None
    affordable: bool = None
    credit: dict = field(default_factory=dict)
    credit_flags: list = field(default_factory=list)
    decision: str = None
    reasons: list = field(default_factory=list)
    justification: str = ""
    trace: list = field(default_factory=list)

    def post(self, agent: str, event: str, data=None) -> None:
        e = {"ts": round(time.time(), 3), "agent": agent, "event": event, "data": data}
        self.trace.append(e)
        log_event(e)


def print_trace(rec: ApplicantRecord) -> None:
    for e in rec.trace:
        print(f"[{e['agent']:<20}] {e['event']:<28} {json.dumps(e['data'], default=str)[:150]}")
    print("-" * 70)
    print(f"DECISION : {rec.decision.upper()}")
    print(f"EMI      : {rec.emi}   Affordability ratio: {rec.ratio}   Affordable: {rec.affordable}")
    print(f"WHY      : {rec.justification}")
