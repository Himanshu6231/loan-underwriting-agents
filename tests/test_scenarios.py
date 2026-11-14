import asyncio, os, sys, tempfile
os.environ["USE_LLM"] = "0"
os.environ["RUN_LOG"] = os.path.join(tempfile.mkdtemp(), "test_run_log.jsonl")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents.manager import UnderwritingManager
from agents.document_agent import grounded, extract_fields

run = lambda t: asyncio.run(UnderwritingManager().underwrite(t))


def test_sanction():
    r = run("Applicant: Ravi Kumar. Net monthly income Rs 60,000. Existing EMIs Rs 5,000. Requesting a loan of Rs 5,00,000 for 36 months.")
    assert r.decision == "sanction" and r.affordable and abs(r.emi - 16251) < 10


def test_decline_unaffordable():
    r = run("Applicant: Neha Singh. Net monthly income Rs 30,000. Existing EMIs Rs 5,000. Requesting a loan of Rs 10,00,000 for 24 months.")
    assert r.decision == "decline" and not r.affordable


def test_refer_when_income_missing():
    r = run("Applicant: Meera Shah. Existing EMIs Rs 3,000. Requesting a loan of Rs 3,00,000 for 24 months.")
    assert r.decision == "refer" and r.emi is None   # halted before any EMI work
    assert any(e["event"] == "halt" for e in r.trace)


def test_decline_on_prior_default():
    r = run("Applicant: Arjun Mehta. Net monthly income Rs 90,000. Requesting a loan of Rs 2,00,000 for 24 months.")
    assert r.decision == "decline" and "prior_default" in r.credit_flags


def test_refer_on_missed_payments():
    r = run("Applicant: Sunita Rao. Net monthly income Rs 90,000. Requesting a loan of Rs 2,00,000 for 24 months.")
    assert r.decision == "refer"


def test_hallucination_guard():
    assert grounded(60000, "income Rs 60,000") and not grounded(80000, "income Rs 60,000")
    assert extract_fields("no numbers here")["income"] is None


def test_run_log_is_append_only():
    p = os.environ["RUN_LOG"]
    before = sum(1 for _ in open(p))
    run("Applicant: Ravi Kumar. Net monthly income Rs 60,000. Requesting a loan of Rs 1,00,000 for 12 months.")
    assert sum(1 for _ in open(p)) > before
