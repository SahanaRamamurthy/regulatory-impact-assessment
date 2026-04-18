"""
Regulatory Impact Assessment Assistant — FastAPI Backend
"""

import os
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

import auth as Auth
import activity_logger as ActivityLog
import reviews as Reviews
from auth import USERS_CSV, excel_bytes
from activity_logger import ACTIVITY_CSV
from reviews import REVIEWS_CSV
from document_loader import DOCS_DIR, EXTRACTORS, save_uploaded_file
from rag_engine import RAGEngine

rag: Optional[RAGEngine] = None
SUPPORTED_EXTENSIONS = sorted(EXTRACTORS.keys())


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag
    Auth.seed_admin()
    rag = RAGEngine()
    yield
    rag = None


app = FastAPI(title="Regulatory Impact Assessment Assistant", version="3.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Auth helper ───────────────────────────────────────────────────────────────

def require_auth(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")
    token    = authorization.split(" ", 1)[1]
    username = Auth.get_user_from_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    return username


def require_admin(authorization: Optional[str]) -> str:
    username = require_auth(authorization)
    if Auth.get_role(username) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return username


# ── Request models ────────────────────────────────────────────────────────────

class RegisterBody(BaseModel):
    username: str
    email: str
    password: str

class LoginBody(BaseModel):
    username: str
    password: str

class ComplianceQuery(BaseModel):
    query: str
    top_k: int = 4

class RetrieveQuery(BaseModel):
    query: str
    top_k: int = 4

class ReviewSubmit(BaseModel):
    log_id: str
    username: str
    query: str
    original_verdict: str
    admin_response: str


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse("static/login.html")

@app.get("/app", response_class=FileResponse)
async def app_page():
    return FileResponse("static/index.html")

@app.get("/health")
async def health():
    return {"status": "ok", "chunks_indexed": len(rag.documents) if rag else 0}


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/api/register")
async def register(body: RegisterBody):
    if not body.username.strip() or not body.email.strip() or not body.password:
        raise HTTPException(status_code=400, detail="All fields are required.")
    result = Auth.register(body.username.strip(), body.email.strip(), body.password)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["error"])
    ActivityLog.log(body.username, "REGISTER", details="New account created")
    return {"message": "Account created successfully."}


@app.post("/api/login")
async def login(body: LoginBody):
    result = Auth.login(body.username.strip(), body.password)
    if not result["ok"]:
        raise HTTPException(status_code=401, detail=result["error"])
    ActivityLog.log(result["username"], "LOGIN", details="User logged in")
    return {"token": result["token"], "username": result["username"], "role": result["role"]}


@app.post("/api/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token    = authorization.split(" ", 1)[1]
        username = Auth.get_user_from_token(token)
        Auth.logout(token)
        if username:
            ActivityLog.log(username, "LOGOUT")
    return {"message": "Logged out."}


# ── RAG endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/assess")
async def assess_compliance(body: ComplianceQuery, authorization: Optional[str] = Header(None)):
    username = require_auth(authorization)
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured.")
    try:
        result = rag.assess_compliance(body.query, top_k=body.top_k)
        ActivityLog.log(username, "ASSESS", query=body.query,
                        verdict=result.get("verdict", ""),
                        risk_level=result.get("risk_level", ""),
                        details=result.get("summary", "")[:200])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/retrieve")
async def retrieve_clauses(body: RetrieveQuery, authorization: Optional[str] = Header(None)):
    username = require_auth(authorization)
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    clauses = rag.retrieve(body.query, top_k=body.top_k)
    ActivityLog.log(username, "RETRIEVE", query=body.query,
                    details=f"{len(clauses)} clauses retrieved")
    return {"query": body.query, "clauses": clauses}


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...),
                       authorization: Optional[str] = Header(None)):
    username = require_auth(authorization)
    saved, skipped = [], []
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            skipped.append({"filename": file.filename, "reason": f"Unsupported format '{ext}'"})
            continue
        data = await file.read()
        save_uploaded_file(file.filename, data)
        saved.append(file.filename)
        ActivityLog.log(username, "UPLOAD", document=file.filename,
                        details=f"{round(len(data)/1024, 1)} KB")
    index_info = rag.reload()
    return {"saved": saved, "skipped": skipped, "index": index_info,
            "supported_formats": SUPPORTED_EXTENSIONS}


@app.post("/api/reload")
async def reload_index(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    return {"status": "ok", **rag.reload()}


@app.get("/api/documents")
async def list_documents(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    files: dict = {}
    for doc in rag.documents:
        files.setdefault(doc["source"], 0)
        files[doc["source"]] += 1
    return {"total_chunks": len(rag.documents),
            "files": [{"filename": k, "chunks": v} for k, v in files.items()],
            "supported_formats": SUPPORTED_EXTENSIONS}


@app.get("/api/documents/{filename}/view")
async def view_document(filename: str, authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    target = DOCS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")
    ext = target.suffix.lower()
    # For PDFs serve directly
    if ext == ".pdf":
        return FileResponse(str(target), media_type="application/pdf")
    # For text-based files, extract and return plain text
    from document_loader import EXTRACTORS
    extractor = EXTRACTORS.get(ext)
    if not extractor:
        raise HTTPException(status_code=415, detail="Preview not supported for this file type.")
    try:
        pages = extractor(target)
        full_text = "\n\n".join(text for text, _ in pages)
        return {"filename": filename, "text": full_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents/{filename}")
async def delete_document(filename: str, authorization: Optional[str] = Header(None)):
    username = require_auth(authorization)
    target = DOCS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")
    target.unlink()
    ActivityLog.log(username, "DELETE_DOC", document=filename)
    return {"deleted": filename, "index": rag.reload()}


# ── Activity & export ─────────────────────────────────────────────────────────

@app.get("/api/my-activity")
async def my_activity(authorization: Optional[str] = Header(None)):
    username = require_auth(authorization)
    rows = ActivityLog.get_user_activity(username)
    return {"username": username, "count": len(rows), "activity": rows[-50:][::-1]}


@app.get("/api/export/users")
async def export_users(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return Response(content=excel_bytes(USERS_CSV),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=users.xlsx"})


@app.get("/api/export/activity")
async def export_activity(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return Response(content=excel_bytes(ACTIVITY_CSV),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=activity.xlsx"})


@app.get("/api/admin/all-activity")
async def all_activity(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    rows = ActivityLog.get_all_activity()
    return {"count": len(rows), "activity": rows[::-1]}


@app.get("/api/admin/all-users")
async def all_users(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    users = Auth.get_all_users()
    return {"count": len(users), "users": [
        {k: v for k, v in u.items() if k != "password_hash"} for u in users
    ]}


@app.get("/api/admin/needs-review")
async def needs_review(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"pending": Reviews.get_pending_reviews()}


@app.post("/api/admin/submit-review")
async def submit_review(body: ReviewSubmit, authorization: Optional[str] = Header(None)):
    admin_username = require_admin(authorization)
    row = Reviews.submit_review(
        log_id=body.log_id,
        username=body.username,
        query=body.query,
        original_verdict=body.original_verdict,
        admin_username=admin_username,
        admin_response=body.admin_response,
    )
    return {"ok": True, "review": row}


@app.get("/api/admin/all-reviews")
async def all_reviews(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"reviews": Reviews.get_all_reviews()}


@app.get("/api/export/reviews")
async def export_reviews(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return Response(content=excel_bytes(REVIEWS_CSV),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=reviews.xlsx"})


@app.get("/api/my-reviews")
async def my_reviews(authorization: Optional[str] = Header(None)):
    username = require_auth(authorization)
    return {"reviews": Reviews.get_user_reviews(username)}


@app.get("/reviews", response_class=FileResponse)
async def reviews_page():
    return FileResponse("static/reviews.html")

@app.get("/admin", response_class=FileResponse)
async def admin_page():
    return FileResponse("static/admin.html")
