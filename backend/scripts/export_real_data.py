"""Writes data/real/: real, openly licensed Samsung appliance fault data as plain CSV tables (one row per code).

Two sources, each pinned to one commit so a rebuild always gives the same rows:
- ha-samsung-washer-local (MIT): Samsung washer fault meanings and fixes, every spelling of a code.
- ApplianceDB free sample (ODbL 1.0): Samsung washer, dryer, refrigerator and dishwasher codes with ranked repairs
  and a source URL per row. ODbL means: credit ApplianceDB, and share any database built from it under ODbL too.

These tables are handed over for embedding; the app itself reads data/manuals/*.md.

    uv run python -m scripts.export_real_data
"""

import csv
import io
import sys
import urllib.request
from pathlib import Path

from scripts.ingest_samsung_faults import COMMIT as SWL_COMMIT
from scripts.ingest_samsung_faults import REPO as SWL_REPO
from scripts.ingest_samsung_faults import TABLE_PATH, read_fault_table

ADB_REPO = "ApplianceDB/ApplianceDB-public"
ADB_COMMIT = "fe7d9928886a48d51e41d7475f379d874f479436"
OUT = Path(__file__).resolve().parents[2] / "data" / "real"


def _raw(repo: str, commit: str, path: str) -> str:
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{commit}/{path}", timeout=30) as r:
        return r.read().decode("utf-8")


def washer_rows() -> list[dict[str, str]]:
    source = f"https://github.com/{SWL_REPO}/blob/{SWL_COMMIT}/{TABLE_PATH}"
    rows = []
    for codes, meaning, action in read_fault_table(_raw(SWL_REPO, SWL_COMMIT, TABLE_PATH)):
        spellings = list(dict.fromkeys(c.upper() if len(c) <= 4 else c for c in codes))
        for code in spellings:
            rows.append(
                {
                    "brand": "Samsung",
                    "appliance_type": "washer",
                    "code": code,
                    "canonical_code": spellings[0],
                    "also_shown_as": ", ".join(c for c in spellings if c != code),
                    "meaning": meaning,
                    "what_to_do": action,
                    "needs_service": "yes" if "service visit" in action or "call service" in action else "no",
                    "source_name": SWL_REPO,
                    "source_url": source,
                    "license": "MIT",
                }
            )
    return rows


def appliancedb_rows() -> list[dict[str, str]]:
    listing = csv.DictReader(io.StringIO(_raw(ADB_REPO, ADB_COMMIT, "error_codes.csv")))
    codes = [r for r in listing if r["brand"] == "Samsung"]
    fixes: dict[str, list[dict[str, str]]] = {}
    for fix in csv.DictReader(io.StringIO(_raw(ADB_REPO, ADB_COMMIT, "repair_procedures.csv"))):
        fixes.setdefault(fix["code_id"], []).append(fix)
    rows = []
    for c in codes:
        ranked = sorted(fixes.get(c["code_id"], []), key=lambda f: int(f["rank"]))
        rows.append(
            {
                "brand": c["brand"],
                "market": c["market"],
                "appliance_type": c["appliance_type"],
                "code": c["code"],
                "meaning": c["meaning"],
                "component": c["component"],
                "cause_category": c["cause_category"],
                "severity": c["severity"],
                "fix_steps": " | ".join(f"{f['rank']}. {f['title']}: {f['steps']}" for f in ranked),
                "diy_difficulty": ranked[0]["diy_difficulty"] if ranked else "",
                "source_type": c["source_type"],
                "source_url": c["source_url"],
                "dataset": f"ApplianceDB free sample ({ADB_REPO}@{ADB_COMMIT[:7]})",
                "license": "ODbL-1.0",
            }
        )
    return rows


def _write(name: str, rows: list[dict[str, str]]) -> None:
    with (OUT / name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    washer, adb = washer_rows(), appliancedb_rows()
    if not washer or not adb:
        sys.exit("refusing: a source came back empty")
    _write("samsung_washer_faults.csv", washer)
    _write("samsung_appliance_codes.csv", adb)


if __name__ == "__main__":
    main()
