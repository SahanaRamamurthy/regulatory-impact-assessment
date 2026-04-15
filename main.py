"""
Regulatory Impact Assessment Assistant — FastAPI Backend
"""

import os
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from document_loader import DOCS_DIR, save_uploaded_file, EXTRACTORS
from rag_engine import RAGEngine

rag: Optional[RAGEngine] = None

SUPPORTED_EXTENSIONS = sorted(EXTRACTORS.keys())


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag
    rag = RAGEngine()
    yield
    rag = None


app = FastAPI(
    title="Regulatory Impact Assessment Assistant",
    description="AI-powered compliance analysis using RAG (TF-IDF + GPT)",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Request models ────────────────────────────────────────────────────────────

class ComplianceQuery(BaseModel):
    query: str
    top_k: int = 4


class RetrieveQuery(BaseModel):
    query: str
    top_k: int = 4


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "engine_ready": rag is not None,
        "chunks_indexed": len(rag.documents) if rag else 0,
    }


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Upload one or more files to the docs/ folder and re-index automatically.
    Supported: PDF, DOCX, XLSX, PPTX, CSV, TXT, MD.
    """
    saved = []
    skipped = []

    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            skipped.append({"filename": file.filename, "reason": f"Unsupported format '{ext}'"})
            continue
        data = await file.read()
        save_uploaded_file(file.filename, data)
        saved.append(file.filename)

    # Rebuild the index to include the new files
    index_info = rag.reload()

    return {
        "saved": saved,
        "skipped": skipped,
        "index": index_info,
        "supported_formats": SUPPORTED_EXTENSIONS,
    }


@app.post("/api/reload")
async def reload_index():
    """Re-scan the docs/ folder and rebuild the TF-IDF index."""
    info = rag.reload()
    return {"status": "ok", **info}


@app.post("/api/assess")
async def assess_compliance(body: ComplianceQuery):
    """Full RAG pipeline — retrieve clauses then generate a GPT compliance verdict."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured. Add it to your .env file.",
        )
    try:
        return rag.assess_compliance(body.query, top_k=body.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/retrieve")
async def retrieve_clauses(body: RetrieveQuery):
    """Retrieve the most relevant chunks without GPT generation."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    clauses = rag.retrieve(body.query, top_k=body.top_k)
    return {"query": body.query, "clauses": clauses}


@app.get("/api/documents")
async def list_documents():
    """List all files currently indexed."""
    files: dict = {}
    for doc in rag.documents:
        src = doc["source"]
        files.setdefault(src, 0)
        files[src] += 1

    return {
        "total_chunks": len(rag.documents),
        "files": [{"filename": k, "chunks": v} for k, v in files.items()],
        "supported_formats": SUPPORTED_EXTENSIONS,
    }


@app.delete("/api/documents/{filename}")
async def delete_document(filename: str):
    """Delete a file from the docs/ folder and re-index."""
    target = DOCS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")
    target.unlink()
    info = rag.reload()
    return {"deleted": filename, "index": info}
