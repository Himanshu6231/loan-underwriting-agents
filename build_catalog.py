"""Build data/banks_real.json from data/banks_real.csv. Only rows marked verified=yes are used.

Usage:  python build_catalog.py [csv_path] [out_path]
Then:   BANK_CATALOG=data/banks_real.json python run_demo.py
"""
import csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REQUIRED = ["bank", "loan_type", "min_rate", "source_url", "as_of_date"]   # everything else may be "not published"
LOAN_TYPES = {"personal", "home", "car", "education"}


def _num(x):
    x = (x or "").strip().replace(",", "")
    return float(x) if x else None


def build(csv_path=None, out_path=None):
    csv_path = csv_path or os.path.join(HERE, "data", "banks_real.csv")
    out_path = out_path or os.path.join(HERE, "data", "banks_real.json")
    products, skipped = [], []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = f"{row.get('bank', '?')} / {row.get('loan_type', '?')}"
            if (row.get("verified") or "").strip().lower() != "yes":
                skipped.append((name, "not verified")); continue
            missing = [k for k in REQUIRED if not (row.get(k) or "").strip()]
            if missing:
                skipped.append((name, "missing: " + ", ".join(missing))); continue
            lo = _num(row["min_rate"]); hi = _num(row.get("max_rate"))
            starting = hi is None                      # only a "starting from" rate is published
            hi = lo if starting else hi
            if row["loan_type"].strip().lower() not in LOAN_TYPES or not (0 < lo <= hi <= 40):
                skipped.append((name, "bad loan_type or rate range")); continue
            foir = _num(row.get("max_foir"))
            products.append({
                "bank": row["bank"].strip(), "loan_type": row["loan_type"].strip().lower(), "scheme": (row.get("scheme") or "").strip(),
                "min_rate": lo, "max_rate": hi,
                "processing_fee_pct": _num(row.get("fee_pct")) or 0.0, "min_fee": _num(row.get("min_fee")) or 0.0,
                "max_fee": _num(row.get("max_fee")) or 0.0, "flat_fee": _num(row.get("flat_fee")) or 0.0,
                "gst_pct": _num(row.get("gst_pct")) or 0.0,
                "min_income": _num(row.get("min_income")), "min_income_published": _num(row.get("min_income")) is not None,
                "min_amount": _num(row.get("min_amount")) or 0.0, "max_amount": _num(row.get("max_amount")) or 1e10,
                "max_tenure_months": int(_num(row.get("max_tenure_months")) or 0) or None,
                "rate_is_starting_from": starting,
                "fee_known": any(_num(row.get(k)) for k in ("fee_pct", "min_fee", "max_fee", "flat_fee")),
                "max_foir": foir if foir else 0.5, "max_foir_is_assumption": not foir,
                "source_url": row["source_url"].strip(), "as_of_date": row["as_of_date"].strip()})
    dates = sorted(p["as_of_date"] for p in products)
    span = (dates[0] if dates[0] == dates[-1] else f"{dates[0]} to {dates[-1]}") if dates else "n/a"
    out = {"_label": f"indicative figures from official bank websites, collected {span}; verify with the bank, not financial advice",
           "_disclaimer": "Collected from official bank websites; rates and fees change. Each product lists its source_url and as_of_date. "
                          "Where max_foir_is_assumption is true the EMI-to-income limit is a project assumption (50%), not a published figure. "
                          "Fields a bank does not publish (minimum income, maximum tenure, processing fee, upper rate) are left empty and flagged, not guessed.",
           "products": products}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return products, skipped


if __name__ == "__main__":
    prods, skipped = build(*(sys.argv[1:3]))
    print(f"{len(prods)} verified product(s) written")
    for name, why in skipped:
        print(f"  skipped {name}: {why}")
