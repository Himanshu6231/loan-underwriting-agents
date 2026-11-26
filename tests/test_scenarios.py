import asyncio, os, sys, tempfile
os.environ["USE_LLM"] = "0"
os.environ["MEMORY_DB"] = os.path.join(tempfile.mkdtemp(), "memory.db")
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


def test_memory_persists_and_is_recalled():
    from memory import get_profile
    app = "Applicant: Asha Verma. Net monthly income Rs 60,000. Requesting a loan of Rs 1,00,000 for 12 months."
    run(app)                                                                   # first time: nothing to recall
    assert get_profile("Asha Verma")["past_applications"] == 1                # decision written back
    r = run(app)                                                               # second time: recalled
    assert any(e["event"] == "recalled_from_memory" for e in r.trace)
    assert "Returning applicant" in r.justification
    assert get_profile("Asha Verma")["past_applications"] == 2


def test_repeat_declines_trigger_refer():
    big = "Applicant: Kiran Patel. Net monthly income Rs 30,000. Requesting a loan of Rs 10,00,000 for 24 months."
    assert run(big).decision == "decline" and run(big).decision == "decline"
    small = "Applicant: Kiran Patel. Net monthly income Rs 30,000. Requesting a loan of Rs 50,000 for 12 months."
    r = run(small)
    assert r.affordable and r.decision == "refer" and "repeated_declines" in r.credit_flags


def test_bank_comparison_is_ranked_and_recommended():
    r = run("Applicant: Ravi Kumar. Net monthly income Rs 60,000. Existing EMIs Rs 5,000. Requesting a loan of Rs 5,00,000 for 36 months.")
    costs = [o["total_cost"] for o in r.options]
    assert r.options and costs == sorted(costs)                       # ranked cheapest first
    assert r.options[0]["bank"] in r.advisory and "Recommended" in r.advisory


def test_ineligible_banks_explain_why():
    r = run("Applicant: Arjun Mehta. Net monthly income Rs 90,000. Requesting a loan of Rs 2,00,000 for 24 months.")
    assert r.options == [] and r.eligibility
    assert all(e["reasons"] and "prior default" in e["reasons"][0] for e in r.eligibility)
    assert "No bank is currently eligible" in r.advisory


def test_loan_type_is_detected_and_banks_filtered():
    r = run("Applicant: Priya Nair. Net monthly income Rs 1,00,000. Requesting a home loan of Rs 30,00,000 for 20 years.")
    assert r.loan_type == "home" and r.tenure_months == 240 and r.options
    from agents.eligibility_agent import list_banks
    assert {e["bank"] for e in r.eligibility} == set(list_banks("home"))


def test_counter_offer_passes_the_affordability_rule():
    from agents.emi_agent import compute_emi
    from agents.counter_offer_agent import min_tenure_months
    r = run("Applicant: Neha Singh. Net monthly income Rs 30,000. Existing EMIs Rs 5,000. Requesting a loan of Rs 10,00,000 for 24 months.")
    amt = r.counter_offer["max_amount_at_requested_tenure"]
    assert r.decision == "decline" and amt > 0
    assert (compute_emi(amt, 10.5, 24) + 5000) / 30000 <= 0.40       # the suggested amount really passes
    m = min_tenure_months(300000, 30000, 5000, 10.5, 84)
    assert m and (compute_emi(300000, 10.5, m) + 5000) / 30000 <= 0.40 and (compute_emi(300000, 10.5, m - 1) + 5000) / 30000 > 0.40


def test_fee_rules_flat_capped_and_gst():
    from agents.comparison_agent import processing_fee
    assert processing_fee(500000, 1.5, 1000, 15000) == 7500.0                 # plain percentage
    assert processing_fee(2000000, 1.5, 1000, 15000) == 15000.0               # capped at max
    assert processing_fee(10000, 1.5, 1000, 15000) == 1000.0                  # raised to min
    assert processing_fee(500000, 0, flat_fee=6500) == 6500.0                 # flat
    assert processing_fee(500000, 1.0, 0, 0, 0, 18) == 5900.0                 # GST on top


def test_real_catalog_loader_uses_verified_rows_only():
    import csv, json
    from build_catalog import build
    d = tempfile.mkdtemp()
    cols = ["bank","loan_type","scheme","min_rate","max_rate","fee_pct","min_fee","max_fee","flat_fee","gst_pct","min_income",
            "min_amount","max_amount","max_tenure_months","max_foir","source_url","as_of_date","verified","notes"]
    ok = ["Test Bank","personal","","10","12","1","1000","5000","","18","20000","","","60","","https://example.com","2026-11-26","yes",""]
    bad = ["Other Bank","personal","","9","11","1","","","","18","20000","","","60","","https://example.com","2026-11-26","no",""]
    gap = ["Gap Bank","personal","","","","1","","","","18","20000","","","60","","https://example.com","2026-11-26","yes",""]
    p = os.path.join(d, "t.csv"); out = os.path.join(d, "t.json")
    with open(p, "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows([ok, bad, gap])
    prods, skipped = build(p, out)
    assert [x["bank"] for x in prods] == ["Test Bank"] and len(skipped) == 2     # unverified and incomplete rows are skipped
    os.environ["BANK_CATALOG"] = out
    try:
        r = run("Applicant: Ravi Kumar. Net monthly income Rs 60,000. Requesting a loan of Rs 5,00,000 for 36 months.")
        assert [o["bank"] for o in r.options] == ["Test Bank"]
        assert r.options[0]["processing_fee"] == 5900.0                          # 1% = 5,000 (cap) + 18% GST
        assert "official bank websites" in r.catalog_note
    finally:
        del os.environ["BANK_CATALOG"]
