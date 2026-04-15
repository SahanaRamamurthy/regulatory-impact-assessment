# Regulatory Impact Assessment Assistant

An AI-powered compliance analysis system built with a Retrieval-Augmented Generation (RAG) pipeline. Anybody can upload regulatory documents in any format and query them to receive structured compliance verdicts with evidence-backed citations.

---

## Features

- **RAG Pipeline** — TF-IDF vectorization and cosine similarity to retrieve the most relevant regulatory clauses for any query
- **AI Compliance Verdicts** — Claude (Anthropic) generates structured assessments: `COMPLIANT`, `NON-COMPLIANT`, `PARTIALLY COMPLIANT`, or `NEEDS REVIEW`
- **Multi-format Document Support** — Upload PDF, Word, Excel, PowerPoint, CSV, JSON, TXT, or Markdown files
- **Interactive Web Interface** — Drag-and-drop upload, file manager, example queries, and retrieved clause viewer
- **FastAPI Backend** — REST API with endpoints for assessment, retrieval, upload, and document management

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| RAG / NLP | scikit-learn (TF-IDF), cosine similarity |
| AI Model | Claude Haiku (Anthropic API) |
| Frontend | HTML, CSS, Vanilla JavaScript |
| Document Parsing | pypdf, python-docx, openpyxl, python-pptx |

---

## Project Structure

```
RAG/
├── main.py                  — FastAPI backend and API routes
├── rag_engine.py            — TF-IDF retrieval + Claude verdict generation
├── document_loader.py       — Multi-format file parser and chunker
├── docs/                    — Drop your regulatory documents here
│   ├── HIPAA_Privacy_Rule.txt
│   ├── HIPAA_Security_Rule.txt
│   ├── Australian_Red_Cross_Policies.txt
│   ├── Australian_Privacy_Principles.txt
│   ├── Therapeutic_Goods_Act.txt
│   ├── GDPR.txt
│   └── (your uploaded files...)
├── static/
│   └── index.html           — Web interface
├── requirements.txt
├── .env                     — API key (not committed to git)
└── .env.example             — Template for environment variables
```

---

## Setup

### 1. Clone or download the project

```bash
cd /Users/sahana/Documents/RAG
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your Anthropic API key

Copy the example env file and add your key:

```bash
cp .env.example .env
```

Edit `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...your key here...
```

Get your key at: https://console.anthropic.com/settings/apikeys

### 4. Start the server

```bash
uvicorn main:app --reload
```

### 5. Open the app

Visit `http://localhost:8000` in your browser.

---

## How to Use

### Assess Compliance
1. Type a compliance scenario in the query box (e.g. *"Sharing donor records with a third party without consent"*)
2. Click **Assess Compliance**
3. The system retrieves the most relevant regulatory clauses, then Claude generates a structured verdict with:
   - Verdict (`COMPLIANT / NON-COMPLIANT / PARTIALLY COMPLIANT / NEEDS REVIEW`)
   - Risk level and confidence
   - Key findings
   - Supporting citations
   - Recommendation for the compliance team

### Retrieve Only
- Click **Retrieve Only** to see which document chunks match your query (no AI call, instant and free)
- Useful for verifying your uploaded documents contain relevant content

### Upload Documents
- Drag and drop files onto the upload zone, or click to browse
- Supported formats: **PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, CSV, TXT, MD, JSON**
- Files are saved to the `docs/` folder and indexed automatically
- Click **↺ Refresh** in the sidebar to re-index after manually adding files

### Manage Documents
- View all indexed files and their chunk counts in the **Indexed Documents** sidebar
- Delete any document with the **✕** button — the index rebuilds automatically

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web interface |
| `GET` | `/health` | Server and index status |
| `POST` | `/api/assess` | Full RAG + Claude compliance verdict |
| `POST` | `/api/retrieve` | TF-IDF retrieval only (no AI) |
| `POST` | `/api/upload` | Upload files and re-index |
| `POST` | `/api/reload` | Re-scan docs/ folder and rebuild index |
| `GET` | `/api/documents` | List all indexed files |
| `DELETE` | `/api/documents/{filename}` | Delete a file and re-index |

---

## Adding New Regulatory Documents

Simply drop any supported file into the `docs/` folder:

```bash
cp my_new_policy.pdf /Users/sahana/Documents/RAG/docs/
```

Then either:
- Restart the server (`uvicorn main:app --reload`), or
- Click **↺ Refresh** in the web UI

The document will be parsed, chunked, and immediately available for queries.

---

## Cost

This project uses **Claude Haiku** — Anthropic's fastest and most affordable model.

- ~$0.001 per compliance query (less than a tenth of a cent)
- $5 of API credits ≈ 3,000–5,000 queries

---

## Background

Built as part of an internship at the **Australian Red Cross Blood Service** to support the governance team in assessing healthcare regulatory compliance. The system analyses documents such as HIPAA rules, Australian Privacy Principles, Therapeutic Goods Act requirements, and internal Red Cross policies.
