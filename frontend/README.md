# GraphMind Frontend

A developer dashboard and interactive knowledge graph explorer for **GraphMind: Persistent Multi-Agent Memory & Decision System**, built with Next.js (App Router), TypeScript, Tailwind CSS, Lucide icons, and React Flow (`@xyflow/react`).

---

## Features

### 1. Overview Dashboard (`/`)
- Real-time statistics from the FalkorDB graph: total stored facts, identified entities, and relationship edges.
- Health monitor showing live FalkorDB connectivity and backend status.
- Summary of the 4 autonomous agents (Coordinator, Memory, Reasoning, Verification).
- Recent facts table with status badges (`active`, `superseded`), confidence scores, and stable SHA-256 fact IDs.

### 2. Memory Chat (`/chat`)
- Natural-language Q&A interface grounded strictly in stored knowledge graph facts.
- Multi-agent verification status badge for every response:
  - `SUPPORTED`: Validated by graph evidence.
  - `PARTIALLY_SUPPORTED`: Some claims substantiated, others unestablished.
  - `CONFLICTING`: Contradictory statements detected in the knowledge base.
  - `UNSUPPORTED`: Insufficient graph evidence to substantiate the query.
- Collapsible inspection drawer:
  - **Supported Claims**: Granular claims validated against facts.
  - **Unsupported Claims / Conflicts**: Detailed conflict notices.
  - **Supporting Evidence**: Fact statements paired with original source text.
  - **Agent Execution Trace**: Coordinator, Reasoning Agent, and Verification Agent sequence with latencies.

### 3. Add Memory (`/memory`)
- Input natural-language statements (e.g., *"I am building GraphMind using Python and FalkorDB"*).
- Displays extracted subject-predicate-object triples with confidence scores and duplicate/superseded flags.
- Source provenance node identifier tracking.
- Paginated table of all facts currently persisted in FalkorDB.

### 4. Knowledge Graph Explorer (`/graph`)
- Interactive canvas powered by React Flow (`@xyflow/react`).
- Custom color-coded node rendering:
  - **Entities**: Violet themed with entity name and type.
  - **Facts**: Emerald/Amber themed with predicate, object value, and active/superseded status.
  - **Sources**: Slate/Indigo themed showing provenance statements.
- Labeled relationship edges (`SUBJECT_OF`, `OBJECT_OF`, `SUPPORTS`).
- Full pan, zoom, fit view controls, and minimap.
- Interactive side drawer displaying all properties upon clicking any node.
- Node type filter controls (`All`, `Entities`, `Facts`, `Sources`).

### 5. Agent Workflow (`/workflow`)
- Real multi-agent execution trace inspector.
- Visualizes the 4-stage pipeline:
  1. **Coordinator Agent**: Query ingestion and dispatch.
  2. **Memory / Reasoning Agent**: Extraction / multi-hop graph retrieval & generation.
  3. **Verification Agent**: Evidence integrity, staleness, and claim validation.
  4. **Grounded Response**: Final synthesis.
- Live pipeline runner allowing interactive testing of queries and statements with step-by-step millisecond execution latencies.

---

## Getting Started

### Prerequisites
- Node.js 18+ (tested on Node v24)
- GraphMind FastAPI backend running on `http://127.0.0.1:8000`

### 1. Configure Environment
Copy `.env.local.example` to `.env.local`:
```bash
cp .env.local.example .env.local
```
Ensure `NEXT_PUBLIC_API_BASE_URL` points to your running FastAPI backend:
```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Run Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Production Build & Start
```bash
npm run build
npm start
```
