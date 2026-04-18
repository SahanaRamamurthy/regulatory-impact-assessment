# Regulatory Impact Assessment Assistant

An AI-powered compliance analysis system built with a Retrieval-Augmented Generation (RAG) pipeline. Healthcare governance teams can upload regulatory documents, query policies using text or voice, and receive structured compliance verdicts with evidence-backed citations — all within a secure, authenticated web application.

---

## Features

- **RAG Pipeline** — TF-IDF vectorization and cosine similarity retrieves the most relevant regulatory clauses for any query
- **AI Compliance Verdicts** — Claude (Anthropic) generates structured assessments: `COMPLIANT`, `NON-COMPLIANT`, `PARTIALLY COMPLIANT`, or `NEEDS REVIEW`
- **Rich Citation Metadata** — Citations include page number, section heading, document version, and effective date extracted automatically
- **Web Search Fallback** — If no relevant document content is found, the system searches the web (DuckDuckGo) and returns cited URLs and snippets
- **Multi-format Document Support** — Upload PDF, Word, Excel, PowerPoint, CSV, JSON, TXT, or Markdown files
- **Document Viewer** — Click any indexed document to preview it inline (PDF rendered, text files shown as-is)
- **Voice Input** — Speak your query using the built-in microphone button (Web Speech API, no extra setup)
- **PDF Export** — Download any compliance assessment as a formatted PDF report
- **User Authentication** — Login and sign-up system with role-based access (user / admin)
- **Super Admin Dashboard** — View all users, full activity log, resizable columns, and export data to Excel
- **Admin Review Workflow** — `NEEDS REVIEW` queries are flagged to the admin; admin writes a manual response using RAG context, stored as audit proof in `reviews.csv`
- **User Review Notifications** — Users receive a banner notification and can view admin responses on a dedicated Reviews page
- **Activity Logging** — Every query, upload, login, and action is logged to CSV and Excel in real time
- **My Activity History** — Users can view, click to restore, and download their own query history
- **FastAPI Backend** — REST API with full authentication on all endpoints

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| RAG / NLP | scikit-learn (TF-IDF), cosine similarity |
| AI Model | Claude Haiku (Anthropic API) |
| Web Search Fallback | DuckDuckGo Search (duckduckgo-search) |
| Auth | SHA-256 password hashing, Bearer token sessions |
| Frontend | HTML, CSS, Vanilla JavaScript |
| PDF Export | jsPDF (client-side) |
| Voice Input | Web Speech API |
| Document Parsing | pypdf, python-docx, openpyxl, python-pptx |
| Data Storage | CSV + Excel (openpyxl), auto-synced |

---

## Project Structure

```
RAG/
├── main.py                  — FastAPI backend, all API routes
├── rag_engine.py            — TF-IDF retrieval + Claude verdict + web search fallback
├── document_loader.py       — Multi-format parser, chunker, metadata extractor
├── auth.py                  — User registration, login, role management
├── activity_logger.py       — Logs all user actions to CSV + Excel
├── reviews.py               — Admin review workflow, saves to reviews.csv
├── docs/                    — Drop your regulatory documents here
│   └── (your uploaded files...)
├── data/                    — Auto-generated, not committed to git
│   ├── users.csv / users.xlsx
│   ├── activity.csv / activity.xlsx
│   └── reviews.csv / reviews.xlsx
├── static/
│   ├── login.html           — Login and sign-up page
│   ├── index.html           — Main user application
│   ├── admin.html           — Super admin dashboard
│   ├── reviews.html         — User-facing admin reviews page
│   └── RAG-nobackground.png — Application logo
├── requirements.txt
├── .env                     — API key (not committed to git)
└── .env.example             — Template for environment variables
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/SahanaRamamurthy/regulatory-impact-assessment.git
cd regulatory-impact-assessment
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your Anthropic API key

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

## Default Super Admin Credentials

A super admin account is created automatically on first startup:

| Field | Value |
|---|---|
| Username | `superadmin` |
| Password | `Admin@RIA2024` |

The admin is redirected to `/admin` after login. Regular users go to `/app`.

> Change the password in `auth.py` before deploying to production.

---

## How to Use

### Sign Up / Login
- Go to `http://localhost:8000`
- Create an account or sign in
- Admin accounts are redirected to the Admin Dashboard automatically

### Assess Compliance
1. Type or **speak** your compliance scenario into the query box
2. Click **Assess Compliance**
3. Claude retrieves the most relevant regulatory clauses and returns:
   - Verdict (`COMPLIANT / NON-COMPLIANT / PARTIALLY COMPLIANT / NEEDS REVIEW`)
   - Risk level and confidence score
   - Key findings
   - Citations with page number, section, version, and effective date
   - Actionable recommendation
4. If no relevant document content is found, the system automatically searches the web and returns cited URLs
5. Click **Download as PDF** to save the report

### Voice Input
- Click the **Speak** button and speak your query
- The button pulses red while listening — stops automatically when you finish
- Works on Chrome and Edge (not Firefox)

### Retrieve Only
- Click **Retrieve Clauses Only** to see matching document chunks without an AI call
- Instant and free — useful for checking document relevance

### Upload Documents
- Drag and drop files onto the upload zone, or click to browse
- Supported: **PDF, DOCX, XLSX, PPTX, CSV, TXT, MD, JSON**
- Files are saved to `docs/` and indexed automatically
- Click any document name to preview it inline

### My Activity
- View your last 50 actions in the **My Activity** panel
- Click any **ASSESS** row to restore that verdict to the results panel
- Click **Download** to export your activity history as CSV

### Admin Reviews
- Queries returning `NEEDS REVIEW` are flagged to the super admin
- Admin sees a notification, retrieves RAG context, and writes a manual response
- The response is saved to `reviews.csv` as an audit record
- The user receives a banner notification and can view the response at `/reviews`

---

## Admin Dashboard

Access at `http://localhost:8000/admin` (admin login required).

- **Stats** — total users, queries, uploads, activity count, and pending reviews
- **Pending Reviews** — all unreviewed `NEEDS REVIEW` queries with a write-response modal
- **Users Table** — all registered accounts with roles and login history (resizable columns)
- **Activity Log** — every action across all users, searchable
- **Export Users / Activity / Reviews** — download as `.xlsx`

---

## API Endpoints

### Public
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/register` | Create a new user account |
| `POST` | `/api/login` | Authenticate and receive a session token |

### User (requires Bearer token)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/assess` | Full RAG + Claude compliance verdict |
| `POST` | `/api/retrieve` | TF-IDF retrieval only (no AI) |
| `POST` | `/api/upload` | Upload documents and re-index |
| `GET` | `/api/documents` | List all indexed files |
| `GET` | `/api/documents/{filename}/view` | Preview a document |
| `DELETE` | `/api/documents/{filename}` | Delete a file and re-index |
| `GET` | `/api/my-activity` | Get current user's activity history |
| `GET` | `/api/my-reviews` | Get admin reviews for current user |
| `POST` | `/api/logout` | End session |

### Admin only
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/all-users` | All registered users |
| `GET` | `/api/admin/all-activity` | Full activity log |
| `GET` | `/api/admin/needs-review` | All unreviewed NEEDS REVIEW queries |
| `POST` | `/api/admin/submit-review` | Submit a manual review response |
| `GET` | `/api/admin/all-reviews` | All submitted reviews |
| `GET` | `/api/export/users` | Download users.xlsx |
| `GET` | `/api/export/activity` | Download activity.xlsx |
| `GET` | `/api/export/reviews` | Download reviews.xlsx |

---

## Adding New Regulatory Documents

Drop any supported file into the `docs/` folder:

```bash
cp my_new_policy.pdf docs/
```

Then either restart the server or click **Refresh** in the web UI. The document is parsed, chunked, and immediately available for queries. Version and effective date are extracted automatically from the filename (e.g. `Policy_v2_2024-07-01.pdf`).

---

## Cost

This project uses **Claude Haiku** — Anthropic's fastest and most affordable model.

- ~$0.001 per compliance query (less than a tenth of a cent)
- $5 of API credits ≈ 3,000–5,000 queries

---

## Background

Built to support governance teams in assessing healthcare regulatory compliance. The system analyses documents such as HIPAA rules, Australian Privacy Principles, Therapeutic Goods Act requirements, and internal organisational policies.
