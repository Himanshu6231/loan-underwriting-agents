# Multi-Agent Loan Underwriting System

Decides a loan application as **sanction / decline / refer**, with EMI, affordability verdict and a one-paragraph justification.

## Architecture: manager-worker delegation
The Underwriting Manager delegates to four worker agents in order and decides from what they post to one shared `ApplicantRecord`. Why it fits: the task is a fixed set of independent specialist checks plus one accountable decision-maker, so a manager that delegates, then decides, matches it directly. See `architecture.svg`.

## Agent roster (one module each, `agents/`)
| Agent | Role | Tools (plain Python, wrapped as Semantic Kernel plugin) |
|---|---|---|
| Document Agent | Application text -> income, existing EMIs, amount, tenure | `extract_fields`, `validate_income_present` |
| EMI Agent | Reducing-balance EMI (deterministic, not the model) | `compute_emi`, `total_interest` |
| Affordability Agent | (EMI + existing EMIs) <= 40% of net income | `emi_to_income_ratio`, `affordability_verdict` |
| Credit-History Agent | Red flags from prior-record store | `lookup_prior_records`, `flag_red_flags` |
| Underwriting Manager | Delegates, halts, decides, justifies | `decide_rule`, `format_justification` |

Tools are called through `kernel.invoke(...)`. The trace shows `via: kernel` or `via: direct` for each call.

## Memory (short-term, long-term, audit)
- **Short-term - shared applicant record** (`state.py`): all agents read and write it during one application.
- **Long-term - SQLite store** (`memory.py`, `data/memory.db`): persists across runs. Seeded from `data/prior_records.json` (defaults, missed payments, active loans). The Manager writes every decision back (`remember_decision`), and the Credit-History Agent recalls it next time, so a returning applicant's earlier outcomes (e.g. repeated declines) influence the new decision. `python memory.py show` lists stored applications; `python memory.py reset` clears them.
- **Audit - run log** (`run_log.jsonl`): append-only, every event.

## Decision rules
Missing income/amount/tenure -> **refer** (halts before any calculation). Prior default or over 40% -> **decline**. 2+ missed payments -> **refer**. Declined 2+ times before (long-term memory) -> **refer**. Otherwise **sanction**. Interest rate defaults to 10.5% p.a. unless the text states one.

## LLM use (Groq via Semantic Kernel)
Groq's OpenAI-compatible endpoint (`openai/gpt-oss-120b`) is used for (1) filling fields the regex missed and (2) polishing the justification. All numbers and decisions come from tools. Without `GROQ_API_KEY`, the system runs fully offline.

## One honest failure handled
An LLM can invent an income that is not in the application. The Document Agent accepts an LLM-extracted number only if its digits appear in the source text (`grounded()`). Otherwise it logs `llm_value_rejected`, leaves income empty, and the Manager refers the case instead of assuming. Limitation: regex extraction expects phrasing like "net monthly income Rs 60,000", and unusual wording gets referred, not guessed.

## Run
```
pip install -r requirements.txt
export GROQ_API_KEY=...        # optional
python run_demo.py             # or open demo.ipynb
pytest tests -q
```

## Bank comparison and advisory (new)
After the underwriting decision, four more agents help the applicant choose a loan:
| Agent | Role | Tools |
|---|---|---|
| Eligibility Agent | Checks the applicant against each bank's criteria (min income, amount range, max tenure, EMI-to-income limit, credit band from memory) and explains every rejection | `list_banks`, `credit_band`, `check_eligibility` |
| Comparison Agent | Prices each eligible bank (rate, EMI, processing fee, total cost) and ranks them | `price_option`, `rank_options` |
| Advisor Agent | Loan-type advice and a recommendation built only from the ranked facts | `loan_type_advice`, `build_advisory` |
| Counter-Offer Agent | If affordability fails: the largest amount that would pass, and the shortest tenure that would pass | `max_affordable_amount`, `min_tenure_months` |

Loan types: personal, home, car, education (detected from the application text; default personal). **The bank catalog (`data/banks.json`) is illustrative sample data with fictional banks, not live rates.** Replace it with figures from official bank websites for real use.
