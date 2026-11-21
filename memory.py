"""Long-term memory: a SQLite store that persists across runs and across applications.

profiles     - seeded from data/prior_records.json (defaults, missed payments, active loans)
applications - every decision the system makes is written back here, so a returning
               applicant is recognised and their earlier outcomes influence later decisions.
CLI: python memory.py show | python memory.py reset
"""
import json, os, sqlite3, sys, time

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB = os.path.join(_HERE, "data", "memory.db")
_SEED = os.path.join(_HERE, "data", "prior_records.json")


def _path():
    return os.getenv("MEMORY_DB", _DEFAULT_DB)


def _db():
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    con = sqlite3.connect(_path())
    con.execute("CREATE TABLE IF NOT EXISTS profiles (name TEXT PRIMARY KEY, defaults INTEGER, "
                "missed_payments_12m INTEGER, active_loans INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, "
                "ts REAL, amount REAL, tenure_months INTEGER, emi REAL, decision TEXT, reasons TEXT)")
    if con.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0 and os.path.exists(_SEED):
        with open(_SEED, encoding="utf-8") as f:
            for n, r in json.load(f).items():
                con.execute("INSERT INTO profiles VALUES (?,?,?,?)",
                            (n, r["defaults"], r["missed_payments_12m"], r["active_loans"]))
        con.commit()
    return con


def get_profile(name: str) -> dict:
    """Recall everything known about an applicant: seeded history + past decisions."""
    key = (name or "").strip().lower()
    con = _db()
    row = con.execute("SELECT defaults, missed_payments_12m, active_loans FROM profiles WHERE name=?", (key,)).fetchone()
    counts = dict(con.execute("SELECT decision, COUNT(*) FROM applications WHERE name=? GROUP BY decision", (key,)).fetchall())
    last = con.execute("SELECT decision FROM applications WHERE name=? ORDER BY id DESC LIMIT 1", (key,)).fetchone()
    con.close()
    return {"found": bool(row) or bool(counts),
            "defaults": row[0] if row else 0,
            "missed_payments_12m": row[1] if row else 0,
            "active_loans": row[2] if row else 0,
            "past_applications": sum(counts.values()),
            "past_declines": counts.get("decline", 0),
            "past_sanctions": counts.get("sanction", 0),
            "last_decision": last[0] if last else None}


def record_application(name: str, amount: float, tenure_months: int, emi: float, decision: str, reasons: str) -> int:
    """Write a decision back into long-term memory. Returns the new row id (0 if name unknown)."""
    key = (name or "").strip().lower()
    if not key:
        return 0
    con = _db()
    cur = con.execute("INSERT INTO applications (name, ts, amount, tenure_months, emi, decision, reasons) "
                      "VALUES (?,?,?,?,?,?,?)", (key, time.time(), amount, tenure_months, emi, decision, reasons))
    con.commit()
    rid = cur.lastrowid
    con.close()
    return rid


def reset() -> None:
    if os.path.exists(_path()):
        os.remove(_path())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        reset(); print("memory cleared")
    else:
        con = _db()
        rows = con.execute("SELECT id, name, amount, emi, decision FROM applications ORDER BY id").fetchall()
        print(f"{len(rows)} stored application(s)")
        for r in rows:
            print(r)
