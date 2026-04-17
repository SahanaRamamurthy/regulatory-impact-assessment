"""
Activity Logger — records every user action to data/activity.csv
and keeps data/activity.xlsx in sync.
"""

import csv
import uuid
from datetime import datetime
from pathlib import Path

import openpyxl

from auth import _sync_excel

DATA_DIR      = Path(__file__).parent / "data"
ACTIVITY_CSV  = DATA_DIR / "activity.csv"
ACTIVITY_XLSX = DATA_DIR / "activity.xlsx"

ACTIVITY_FIELDS = [
    "log_id", "timestamp", "username", "action",
    "query", "document", "verdict", "risk_level", "details"
]


def _ensure_csv():
    DATA_DIR.mkdir(exist_ok=True)
    if not ACTIVITY_CSV.exists():
        with open(ACTIVITY_CSV, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=ACTIVITY_FIELDS).writeheader()


def log(username: str, action: str, query: str = "", document: str = "",
        verdict: str = "", risk_level: str = "", details: str = ""):
    _ensure_csv()
    row = {
        "log_id":     str(uuid.uuid4())[:8],
        "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username":   username,
        "action":     action,
        "query":      query[:300] if query else "",
        "document":   document,
        "verdict":    verdict,
        "risk_level": risk_level,
        "details":    details[:200] if details else "",
    }
    with open(ACTIVITY_CSV, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=ACTIVITY_FIELDS).writerow(row)

    # Re-sync Excel on every write
    all_rows = []
    with open(ACTIVITY_CSV, newline="") as f:
        all_rows = list(csv.DictReader(f))
    _sync_excel(all_rows, ACTIVITY_CSV, ACTIVITY_XLSX)


def get_user_activity(username: str) -> list[dict]:
    _ensure_csv()
    with open(ACTIVITY_CSV, newline="") as f:
        return [r for r in csv.DictReader(f) if r["username"] == username]


def get_all_activity() -> list[dict]:
    _ensure_csv()
    with open(ACTIVITY_CSV, newline="") as f:
        return list(csv.DictReader(f))
