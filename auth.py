"""
Auth module — CSV-backed user store with SHA-256 password hashing.
Users are persisted in data/users.csv and mirrored to data/users.xlsx.
"""

import csv
import hashlib
import io
import secrets
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

import openpyxl

DATA_DIR   = Path(__file__).parent / "data"
USERS_CSV  = DATA_DIR / "users.csv"
USERS_XLSX = DATA_DIR / "users.xlsx"

USERS_FIELDS = ["user_id", "username", "email", "password_hash", "role", "created_at", "last_login"]

# In-memory session store  {token: username}
_sessions: Dict[str, str] = {}

ADMIN_USERNAME = "superadmin"
ADMIN_PASSWORD = "Admin@RIA2024"
ADMIN_EMAIL    = "admin@redcross.org.au"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _ensure_csv():
    DATA_DIR.mkdir(exist_ok=True)
    if not USERS_CSV.exists():
        with open(USERS_CSV, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=USERS_FIELDS).writeheader()


def _read_users() -> list[dict]:
    _ensure_csv()
    with open(USERS_CSV, newline="") as f:
        return list(csv.DictReader(f))


def _write_users(rows: list[dict]):
    with open(USERS_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=USERS_FIELDS)
        w.writeheader()
        w.writerows(rows)
    _sync_excel(rows, USERS_CSV, USERS_XLSX)


def _sync_excel(rows: list[dict], csv_path: Path, xlsx_path: Path):
    if not rows:
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22
    wb.save(xlsx_path)


def seed_admin():
    """Create the default super admin account if it doesn't exist yet."""
    users = _read_users()
    if any(u["username"].lower() == ADMIN_USERNAME.lower() for u in users):
        return
    users.append({
        "user_id":       str(uuid.uuid4()),
        "username":      ADMIN_USERNAME,
        "email":         ADMIN_EMAIL,
        "password_hash": _hash(ADMIN_PASSWORD),
        "role":          "admin",
        "created_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_login":    "",
    })
    _write_users(users)
    print(f"[auth] Super admin created — username: {ADMIN_USERNAME}")


# ── Public API ────────────────────────────────────────────────────────────────

def register(username: str, email: str, password: str) -> dict:
    users = _read_users()
    if any(u["username"].lower() == username.lower() for u in users):
        return {"ok": False, "error": "Username already exists."}
    if any(u["email"].lower() == email.lower() for u in users):
        return {"ok": False, "error": "Email already registered."}

    users.append({
        "user_id":       str(uuid.uuid4()),
        "username":      username,
        "email":         email,
        "password_hash": _hash(password),
        "role":          "user",
        "created_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_login":    "",
    })
    _write_users(users)
    return {"ok": True}


def login(username: str, password: str) -> dict:
    users = _read_users()
    user  = next((u for u in users if u["username"].lower() == username.lower()), None)
    if not user or user["password_hash"] != _hash(password):
        return {"ok": False, "error": "Invalid username or password."}

    for u in users:
        if u["username"].lower() == username.lower():
            u["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_users(users)

    token = secrets.token_hex(32)
    _sessions[token] = username
    return {"ok": True, "token": token, "username": username, "role": user.get("role", "user")}


def logout(token: str):
    _sessions.pop(token, None)


def get_user_from_token(token: str) -> Optional[str]:
    return _sessions.get(token)


def get_role(username: str) -> str:
    users = _read_users()
    user  = next((u for u in users if u["username"].lower() == username.lower()), None)
    return user.get("role", "user") if user else "user"


def get_all_users() -> list[dict]:
    return _read_users()


def excel_bytes(csv_path: Path) -> bytes:
    rows = []
    if csv_path.exists():
        with open(csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
    wb = openpyxl.Workbook()
    ws = wb.active
    if rows:
        ws.append(list(rows[0].keys()))
        for row in rows:
            ws.append(list(row.values()))
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 24
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
