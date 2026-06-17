🚀 ResearchHubAI

ResearchHubAI is a modern Multi-Agent AI Research Platform that combines intelligent routing, web research, document analysis, code generation, and report writing into a unified workflow. Built with LangGraph, FastAPI, Ollama, ChromaDB, and React, it enables users to conduct deep research, analyze documents, generate code, and create structured reports through a clean ChatGPT-style interface.

⸻

✨ Features

🧠 Multi-Agent Architecture

* Intent Router Agent
* Planning Agent
* Research Agent
* Writer Agent
* Coding Agent
* Assistant Agent
* Memory Context Agent

🔍 Research & Retrieval

* Real-time web search integration
* RAG-powered document retrieval
* ChromaDB vector storage
* Context-aware follow-up conversations
* Multi-source information synthesis

📄 Document Intelligence

* Upload and analyze files
* Extract insights from documents
* Detect inconsistencies and contradictions
* Generate summaries and reports
* Persistent session memory

💻 Code Generation

* Generate production-ready code
* Explain code logic
* Refactor existing implementations
* Debug and optimize solutions

⚡ Real-Time Experience

* Live token streaming
* WebSocket updates
* Progress tracking
* Agent execution monitoring

📊 Report Export

* Markdown Export
* PDF Export
* DOCX Export
* JSON Export

💾 Persistent Storage

* Chat history management
* Session recovery
* Report storage
* Uploaded file tracking

⸻

🏗️ System Architecture

User Query
    │
    ▼
Intent Router
    │
    ├── Research Workflow
    ├── Coding Workflow
    ├── Assistant Workflow
    └── Follow-Up Workflow
            │
            ▼
     Memory Context Agent
            │
            ▼
      Final Response

⸻

📁 Project Structure

project/
├── app/
│   ├── agents/          # Individual agent logic
│   ├── graph/           # LangGraph workflows
│   ├── models/          # Pydantic schemas
│   ├── routes/          # FastAPI endpoints
│   ├── services/        # Database and LLM services
│   ├── utils/           # Utilities and WebSockets
│   └── main.py          # FastAPI entrypoint
│
├── frontend/
│   ├── src/
│   │   ├── components/  # UI components
│   │   ├── App.tsx      # Main application
│   │   └── index.css    # Styling
│   └── package.json
│
├── requirements.txt
├── .env.example
├── README.md
└── logs/

⸻

🛠️ Tech Stack

Backend

* Python
* FastAPI
* LangGraph
* LangChain
* Ollama
* ChromaDB
* SQLite
* WebSockets

Frontend

* React
* TypeScript
* Tailwind CSS
* React Flow

AI Models

* Qwen3
* Gemma
* DeepSeek
* Any Ollama-compatible model

⸻

⚙️ Installation

Clone Repository

git clone https://github.com/amrindersingh1820/ResearchHub-AI-.git
cd ResearchHub-AI-

Backend Setup

python -m venv .venv
source .venv/bin/activate
# Windows
# .venv\Scripts\activate
pip install -r requirements.txt

Install Ollama Models

ollama pull qwen3:1.7b
ollama pull qwen3:4b

Frontend Setup

cd frontend
npm install
npm run dev

Run Backend

uvicorn app.main:app --reload

⸻

🌐 Access Application

Frontend:

http://localhost:5173

Backend:

http://localhost:8000

API Docs:

http://localhost:8000/docs

⸻

📈 Workflow

1. User submits a query.
2. Intent Router determines the task type.
3. Planner creates execution strategy.
4. Research Agent gathers information.
5. Writer/Coder generates output.
6. Results stream in real time.
7. Reports and chat history are saved.
8. Follow-up questions use memory context.

⸻

🔒 Key Capabilities

* Multi-Agent Collaboration
* Context-Aware Memory
* Retrieval-Augmented Generation (RAG)
* Real-Time Streaming
* Session Persistence
* Report Exporting
* Local LLM Support
* Offline Operation

⸻

🚀 Future Roadmap

* Multi-user authentication
* Team collaboration workspaces
* Advanced observability dashboard
* Agent marketplace
* Voice interaction support
* MCP integration
* Cloud deployment support

⸻

👨‍💻 Author

Amrinder Singh

Computer Science & Engineering 

GitHub: https://github.com/amrindersingh1820

⸻

⭐ Support

If you find this project useful, consider giving it a star on GitHub and contributing to its development.
