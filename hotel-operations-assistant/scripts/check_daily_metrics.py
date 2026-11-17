"""Read a mapped hotel daily-summary CSV; emit JSON without changing input."""
import argparse
import csv
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re
import sys

REQUIRED = ("property_id", "business_date", "currency", "available_room_nights", "sold_room_nights", "room_revenue")

def analyze(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers):
            raise ValueError("Duplicate column headers")
        missing = sorted(set(REQUIRED) - set(headers))
        if missing:
            raise ValueError("Missing columns: " + ", ".join(missing))
        rows = list(reader)
    results, groups = [], {}
    for number, raw in enumerate(rows, 1):
        errors, flags = [], []
        if None in raw:
            errors.append("EXTRA_CSV_CELLS")
        values = {key: (raw.get(key) or "").strip() for key in REQUIRED}
        for key in ("property_id", "business_date", "currency"):
            if not values[key]:
                errors.append("MISSING_" + key.upper())
        try:
            value = values["business_date"]
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                raise ValueError()
            date.fromisoformat(value)
        except ValueError:
            errors.append("INVALID_BUSINESS_DATE")
        parsed = {}
        for key in ("available_room_nights", "sold_room_nights"):
            value = values[key]
            if not re.fullmatch(r"[0-9]+", value):
                errors.append("INVALID_" + key.upper())
            else:
                parsed[key] = int(value)
        value = values["room_revenue"]
        if not re.fullmatch(r"-?[0-9]+(?:\.[0-9]{1,2})?", value):
            errors.append("INVALID_ROOM_REVENUE")
        else:
            parsed["room_revenue"] = Decimal(value)
        metrics = None
        if not errors:
            available, sold, revenue = (parsed[key] for key in REQUIRED[3:])
            if sold > available:
                flags.append("SOLD_EXCEEDS_AVAILABLE")
            if revenue < 0:
                flags.append("NEGATIVE_REVENUE_REVIEW")
            if sold == 0 and revenue != 0:
                flags.append("REVENUE_WITHOUT_SOLD_ROOM_NIGHTS")
            def ratio(numerator, denominator, scale=1):
                if denominator == 0:
                    return {"value": None, "reason": "ZERO_DENOMINATOR"}
                value = (Decimal(numerator) * scale / Decimal(denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                return {"value": str(value), "reason": None}
            metrics = {"occupancy_percent": ratio(sold, available, 100), "adr": ratio(revenue, sold), "revpar": ratio(revenue, available)}
        key = tuple(values[x] for x in REQUIRED[:3])
        if all(key):
            groups.setdefault(key, []).append(len(results))
        results.append({"source_record": number, "key": list(key), "errors": errors, "flags": flags, "metrics": metrics})
    for indices in groups.values():
        if len(indices) > 1:
            for index in indices:
                results[index]["flags"].append("DUPLICATE_DAILY_KEY_REVIEW")
    return {"scope": "mapped_daily_summary_only", "record_count": len(results), "valid_numeric_records": sum(not r["errors"] for r in results), "review_records": sum(bool(r["errors"] or r["flags"]) for r in results), "rows": results, "limitations": ["No totals, accounting audit, tax conversion or source-row mapping", "source_record is CSV record ordinal, not physical file line", "Metrics on flagged rows are provisional; resolve flags before reporting", "No checks possible on transactions or guest/room status from this summary alone"]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv")
    from workflow_guard import add_arguments, require_execution
    add_arguments(parser)
    args = parser.parse_args()
    try:
        require_execution(args.workflow, args.requirement_version, args.plan_version, "metrics")
        result = analyze(args.input_csv)
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
