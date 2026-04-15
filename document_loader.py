"""
Document Loader — parses files from the docs/ folder.

Supported formats: PDF, DOCX, XLSX, PPTX, TXT, CSV, MD, JSON
Each file is split into chunks so retrieval is precise.
"""

import csv
import io
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any

DOCS_DIR = Path(__file__).parent / "docs"
CHUNK_SIZE = 600        # characters per chunk
CHUNK_OVERLAP = 100     # overlap between chunks


# ── Per-format extractors ─────────────────────────────────────────────────────

def _extract_pdf(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())
    # Also pull text from tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)
    return "\n".join(parts)


def _extract_xlsx(path: Path) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(str(path), data_only=True)
    parts = []
    for sheet in wb.worksheets:
        parts.append(f"[Sheet: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            row_text = " | ".join(str(v) for v in row if v is not None)
            if row_text.strip():
                parts.append(row_text)
    return "\n".join(parts)


def _extract_pptx(path: Path) -> str:
    from pptx import Presentation
    prs = Presentation(str(path))
    parts = []
    for i, slide in enumerate(prs.slides, 1):
        parts.append(f"[Slide {i}]")
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                parts.append(shape.text.strip())
    return "\n".join(parts)


def _extract_csv(path: Path) -> str:
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        return "\n".join(" | ".join(row) for row in reader if any(c.strip() for c in row))


def _extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_json(path: Path) -> str:
    """Recursively flatten a JSON structure into readable key: value lines."""
    def flatten(obj, prefix=""):
        lines = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                label = f"{prefix}{k}" if not prefix else f"{prefix} — {k}"
                lines.extend(flatten(v, label))
        elif isinstance(obj, list):
            for item in obj:
                lines.extend(flatten(item, prefix))
        else:
            val = str(obj).strip()
            if val:
                lines.append(f"{prefix}: {val}" if prefix else val)
        return lines

    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(flatten(data))


EXTRACTORS = {
    ".pdf":  _extract_pdf,
    ".docx": _extract_docx,
    ".doc":  _extract_docx,
    ".xlsx": _extract_xlsx,
    ".xls":  _extract_xlsx,
    ".pptx": _extract_pptx,
    ".ppt":  _extract_pptx,
    ".csv":  _extract_csv,
    ".txt":  _extract_txt,
    ".md":   _extract_txt,
    ".json": _extract_json,
}


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks, splitting on sentence/paragraph boundaries."""
    # Normalise whitespace
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Try to break at a sentence or newline boundary
        if end < len(text):
            for boundary in ["\n\n", "\n", ". ", "! ", "? "]:
                idx = text.rfind(boundary, start, end)
                if idx > start:
                    end = idx + len(boundary)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end - overlap > start else end
    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

def load_documents_from_folder(folder: Path = DOCS_DIR) -> List[Dict[str, Any]]:
    """
    Scan the docs/ folder, extract text from every supported file,
    and return a flat list of chunk dicts compatible with the RAG engine.
    """
    folder.mkdir(parents=True, exist_ok=True)
    results = []

    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        extractor = EXTRACTORS.get(ext)
        if extractor is None:
            continue  # skip unsupported formats silently

        try:
            raw_text = extractor(path)
        except Exception as e:
            print(f"[loader] Could not parse {path.name}: {e}")
            continue

        chunks = _chunk_text(raw_text)
        for idx, chunk in enumerate(chunks):
            results.append({
                "id":               f"{path.stem}-chunk{idx}",
                "source":           path.name,
                "section":          f"Chunk {idx + 1} of {len(chunks)}",
                "title":            f"{path.stem} (part {idx + 1})",
                "content":          chunk,
                "similarity_score": 0.0,   # filled in by the RAG engine
            })

    return results


def save_uploaded_file(filename: str, data: bytes) -> Path:
    """Save an uploaded file to the docs/ folder and return its path."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    dest = DOCS_DIR / filename
    dest.write_bytes(data)
    return dest
