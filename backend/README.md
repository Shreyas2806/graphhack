# GraphMind — Persistent Multi-Agent Memory & Decision System

A hackathon project combining **FalkorDB** (graph database) and **Google Gemini** (LLM)
into a FastAPI backend for persistent multi-agent memory and decision-making.

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.10 |
| Docker & Docker Compose | any recent version |
| A Gemini API key | [Get one here](https://aistudio.google.com/app/apikey) |

---

## 1 — Start FalkorDB

```bash
# From the repo root (D:\graphmind)
docker compose up -d
```

FalkorDB will be available on `127.0.0.1:6379`.  
The RedisInsight UI is available at `http://127.0.0.1:3000`.

---

## 2 — Create and activate the virtual environment

```powershell
# Inside D:\graphmind\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

---

## 3 — Configure environment variables

```powershell
Copy-Item .env.example .env
```

Edit `.env` and fill in your real Gemini API key:

```env
GEMINI_API_KEY=AIza...your_key_here...
GEMINI_MODEL=gemini-2.5-flash
FALKORDB_HOST=127.0.0.1
FALKORDB_PORT=6379
FALKORDB_GRAPH=graphmind
```

> ⚠️ **Never commit `.env`** — it is already in `.gitignore`.

---

## 4 — Install dependencies

```powershell
pip install -r requirements.txt
```

---

## 5 — Run the development server

```powershell
# From D:\graphmind\backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive docs: <http://127.0.0.1:8000/docs>  
Alternative docs: <http://127.0.0.1:8000/redoc>

---

## 6 — Run tests

Tests mock FalkorDB and Gemini — no live services required:

```powershell
python -m pytest tests/ -v
```

---

## API Reference

### `GET /`

Returns project name and running status.

```json
{
  "project": "GraphMind — Persistent Multi-Agent Memory & Decision System",
  "status": "running",
  "version": "0.1.0"
}
```

---

### `GET /health`

Returns application health and FalkorDB connectivity.

```json
{
  "status": "ok",
  "falkordb": { "ok": true }
}
```

`status` is `"degraded"` when FalkorDB is unreachable.

---

### `POST /test-graph`

Creates (or merges) sample `Person` and `Project` nodes with a `WORKS_ON` relationship.

```json
{
  "ok": true,
  "detail": "MERGE succeeded: Person(Alice) -[WORKS_ON]-> Project(GraphMind) in graph 'graphmind'.",
  "nodes_created": 2,
  "relationships_created": 1
}
```

---

### `POST /test-gemini`

**Request body:**

```json
{ "prompt": "Explain graph databases in one sentence." }
```

**Response:**

```json
{
  "ok": true,
  "text": "Graph databases store data as nodes and relationships..."
}
```

---

## Project structure

```text
backend/
├── app/
│   ├── __init__.py      # Package marker
│   ├── config.py        # Environment / settings
│   ├── graph.py         # FalkorDB connection & helpers
│   ├── llm.py           # Gemini integration
│   └── main.py          # FastAPI app & endpoints
├── tests/
│   └── test_health.py   # Unit tests (mocked services)
├── .env.example         # Environment template
├── .gitignore
├── requirements.txt
└── README.md
```
