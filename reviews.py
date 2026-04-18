"""
Reviews — stores admin manual reviews of NEEDS REVIEW queries.
"""

import csv
import uuid
from datetime import datetime
from pathlib import Path

from auth import _sync_excel

DATA_DIR     = Path(__file__).parent / "data"
REVIEWS_CSV  = DATA_DIR / "reviews.csv"
REVIEWS_XLSX = DATA_DIR / "reviews.xlsx"

REVIEW_FIELDS = [
    "review_id", "timestamp", "username", "query",
    "original_verdict", "admin_username", "admin_response", "reviewed_at"
]


def _ensure_csv():
    DATA_DIR.mkdir(exist_ok=True)
    if not REVIEWS_CSV.exists():
        with open(REVIEWS_CSV, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=REVIEW_FIELDS).writeheader()


def get_pending_reviews() -> list[dict]:
    """Return NEEDS REVIEW assess rows that have no admin response yet."""
    from activity_logger import get_all_activity
    _ensure_csv()
    reviewed_ids = set()
    with open(REVIEWS_CSV, newline="") as f:
        for r in csv.DictReader(f):
            reviewed_ids.add(r["review_id"])

    pending = []
    for row in get_all_activity():
        if row.get("verdict") == "NEEDS REVIEW":
            if row["log_id"] not in reviewed_ids:
                pending.append(row)
    return pending


def get_all_reviews() -> list[dict]:
    _ensure_csv()
    with open(REVIEWS_CSV, newline="") as f:
        return list(csv.DictReader(f))


def get_user_reviews(username: str) -> list[dict]:
    _ensure_csv()
    with open(REVIEWS_CSV, newline="") as f:
        return [r for r in csv.DictReader(f) if r["username"] == username]


def submit_review(log_id: str, username: str, query: str,
                  original_verdict: str, admin_username: str,
                  admin_response: str) -> dict:
    _ensure_csv()
    row = {
        "review_id":        log_id,
        "timestamp":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username":         username,
        "query":            query,
        "original_verdict": original_verdict,
        "admin_username":   admin_username,
        "admin_response":   admin_response,
        "reviewed_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(REVIEWS_CSV, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=REVIEW_FIELDS).writerow(row)

    all_rows = []
    with open(REVIEWS_CSV, newline="") as f:
        all_rows = list(csv.DictReader(f))
    _sync_excel(all_rows, REVIEWS_CSV, REVIEWS_XLSX)
    return row
