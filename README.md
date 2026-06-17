# Production-Grade Multi-Agent AI Research Platform

A professional, hackathon-ready multi-agent AI research orchestration system built with **FastAPI**, **LangGraph**, **Ollama (Qwen3)**, **SQLite**, **ChromaDB**, and **React** (with **TypeScript**, **TailwindCSS**, and **React Flow**).

---

## Key Features

1. **Multi-Agent Collaboration**: Orchestrated by LangGraph with a 6-agent lifecycle:
   - **Planner Agent**: Synthesizes the initial goal & research strategy.
   - **Coordinator Agent**: Decomposes the research topic into 3-5 parallel investigative domains.
   - **Parallel Research Workers**: Fetch web and RAG context to compile facts for individual domains.
   - **Fact Checker Agent**: Reconciles contradicting statements, analyzes uncertainties, and scores confidence.
   - **Critic Agent**: Reviews gaps, weaknesses, and academic rigor.
   - **Report Writer Agent**: Formats reports into publication-grade Markdown documents.
2. **Retrieval-Augmented Generation (RAG)**: Integrates local vector storage using ChromaDB and SentenceTransformers (`all-MiniLM-L6-v2`) for document parsing and context retrieval (supporting PDF, CSV, and TXT uploads).
3. **Web Search Integration**: Abstract Web Research interface with Tavily API support, falling back to a contextual Mock Search engine if no API keys are supplied.
4. **Memory Management**: Structured logging and long-term research persistence utilizing SQLite.
5. **Real-Time State Streaming**: Pushes execution status, active agent highlights, and terminal logs in real-time to the UI using FastAPI WebSockets.
6. **Dynamic Flow Visualizer**: Implements React Flow to illustrate node state changes (Idle -> Running -> Completed) reactively as WS triggers.
7. **Document Export Engine**: Renders and downloads research outcomes as Markdown, JSON, or professional ReportLab-generated PDF documents.

---

## Installation & Setup

### Prerequisites

Ensure you have the following installed on your local machine:
- Python 3.12+
- Node.js (v18+) & npm
- Ollama

### Step 1: Model Setup

Start the Ollama server and pull the Qwen 3 (8B or 4B) model:

```bash
# Start Ollama
ollama serve

# Pull the primary model (runs locally)
ollama pull qwen3:8b
```

> *Note: If you run a different model size, update the `OLLAMA_MODEL` value in `.env` accordingly (e.g., `qwen2.5:7b` or `qwen3:4b`).*

### Step 2: Backend Installation

1. Navigate to the project root:
   ```bash
   pip install -r requirements.txt
   ```
2. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
3. Edit the `.env` file if you wish to add a custom Port or Tavily API Search key.

### Step 3: Frontend Installation

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install --legacy-peer-deps
   ```

---

## How to Run

You need two terminal sessions running simultaneously:

### Terminal 1: FastAPI Backend

From the project root:
```bash
uvicorn app.main:app --reload
```
The backend API documentation is accessible at `http://localhost:8000/docs`.

### Terminal 2: React Frontend

From the `frontend/` directory:
```bash
npm run dev
```
Open `http://localhost:5173` in your browser to interact with the platform.

---

## API Endpoints

### 1. Execute Research Run
- **URL**: `POST /api/research`
- **Payload**:
  ```json
  {
    "query": "Research the impact of Artificial Intelligence on Cybersecurity.",
    "session_id": "optional-pre-generated-uuid"
  }
  ```
- **Response**:
  ```json
  {
    "session_id": "4b5d63f9-7e4d-44aa-9c2b-658a1eeabce2",
    "query": "Research the impact of Artificial Intelligence on Cybersecurity.",
    "report": "# Executive Summary\n...",
    "confidence_score": 0.94,
    "created_at": "2026-06-17T10:45:00.123456"
  }
  ```

### 2. Upload Grounding Documents (RAG)
- **URL**: `POST /api/upload`
- **Method**: Multipart Form Data
- **Fields**:
  - `file`: (Binary File, supporting `.pdf`, `.csv`, `.txt`)
  - `session_id`: (String, UUID)
- **Response**:
  ```json
  {
    "filename": "annual_threat_report.pdf",
    "session_id": "4b5d63f9-7e4d-44aa-9c2b-658a1eeabce2",
    "chunks": 42,
    "message": "File successfully ingested. Split into 42 vector chunks."
  }
  ```

### 3. Fetch History List
- **URL**: `GET /api/history`
- **Response**:
  ```json
  [
    {
      "id": "4b5d63f9-7e4d-44aa-9c2b-658a1eeabce2",
      "query": "Research the impact of Artificial Intelligence on Cybersecurity.",
      "created_at": "2026-06-17T10:45:00.123456",
      "completed": true
    }
  ]
  ```

### 4. Export Formats
- **PDF**: `GET /api/report/{session_id}/export/pdf` (returns standard PDF download)
- **Markdown**: `GET /api/report/{session_id}/export/md` (returns standard markdown download)
- **JSON**: `GET /api/report/{session_id}/export/json` (returns structured JSON data payload)

---

## System Folder Structure

```
project/
├── app/
│   ├── agents/          # Individual agent logic (planner, researcher, etc.)
│   ├── graph/           # LangGraph State definitions and workflow compiler
│   ├── models/          # Pydantic schemas for request/response validation
│   ├── routes/          # FastAPI routers (endpoints for files, runs, history)
│   ├── services/        # Database managers, Ollama connect, export builders
│   ├── utils/           # WebSocket and logger setup
│   └── main.py          # FastAPI application entrypoint
├── frontend/            # React Client
│   ├── src/
│   │   ├── components/  # Render components (flow graph, console feed, report viewer)
│   │   ├── App.tsx      # Main application state and layout manager
│   │   └── index.css    # Tailwind styles and keyframes definition
│   └── package.json
├── requirements.txt     # Python backend dependencies
├── .env.example         # Template configuration
├── README.md            # Installation and usage instructions
└── logs/                # Local text execution log records
```
