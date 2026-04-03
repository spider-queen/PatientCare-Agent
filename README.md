# PatientCare Agent

A full-stack medical assistant project for patient service scenarios.

It combines a FastAPI backend, a React workspace UI, Qwen-based tool calling, patient data management, multimodal input, and short-term / long-term memory retrieval into one runnable project.

## Overview

PatientCare Agent is designed for healthcare support workflows such as:

- patient identity verification
- patient profile, case, and visit record lookup
- multimodal question answering with image input
- short-term conversation memory
- long-term memory extraction and retrieval
- a web workspace for patient-centric interaction

The current version focuses on a local demo / interview-style implementation rather than a production-ready hospital system.

## Features

- Qwen-powered agent entrypoint via `POST /api/agent/query`
- patient lookup by patient code, phone, and identity-related fields
- structured CRUD APIs for patients, medical cases, and visit records
- long-term memory profile, key event extraction, and hybrid retrieval
- React workspace UI for patient overview, chat, visit summary, and memory panel
- image upload support for multimodal queries
- SQLite-based local persistence
- FAISS-based vector index for memory retrieval

## Tech Stack

### Backend

- Python 3.12
- FastAPI
- SQLAlchemy
- Pydantic v2
- SQLite
- FAISS
- OpenAI-compatible SDK calling Qwen / DashScope

### Frontend

- React 18
- Vite
- TypeScript
- Tailwind CSS
- TanStack Query
- Zustand

## Architecture

The project is organized around four main layers:

1. API layer  
   FastAPI routes expose agent, dashboard, patient, visit record, and memory endpoints.

2. Agent layer  
   `QwenMCPAgent` orchestrates LLM reasoning, tool calls, multimodal input, and memory context injection.

3. Data and memory layer  
   SQLite stores structured business data and conversation records, while FAISS supports vector retrieval for long-term memory events.

4. Frontend workspace layer  
   A React app provides a patient-centered workspace with chat, patient overview, visit summary, and memory views.

## Project Structure

```text
.
|-- app/                    # FastAPI app, routes, services, db, llm integration
|   |-- api/routes/         # API route definitions
|   |-- db/                 # SQLAlchemy models, session, DB init
|   |-- llm/                # Qwen client and agent orchestration
|   |-- schemas/            # Pydantic schemas
|   `-- services/           # Business services and memory logic
|-- data/                   # Local SQLite DB, uploaded media, FAISS index files
|-- docs/                   # PRD and architecture notes
|-- frontend/               # React + Vite frontend
|   |-- src/
|   `-- package.json
|-- scripts/                # Demo data and local test scripts
|-- .env.example            # Environment variable template
|-- README.md
`-- requirements.txt
```

## Core API Endpoints

### Agent

- `POST /api/agent/query`
- `GET /api/health`

### Dashboard

- `GET /api/dashboard/patient-overview`

### Memory

- `GET /api/memory/preferences`
- `PUT /api/memory/preferences`
- `POST /api/memory/conversations`
- `GET /api/memory/conversations`
- `POST /api/memory/extract/business`
- `POST /api/memory/extract/conversation`
- `GET /api/memory/events`
- `POST /api/memory/search/events`
- `GET /api/memory/profile`

### Patient Data

- `POST /api/patients`
- `GET /api/patients`
- `GET /api/patients/{patient_id}`
- `PUT /api/patients/{patient_id}`
- `POST /api/medical-cases`
- `GET /api/medical-cases`
- `GET /api/medical-cases/{case_id}`
- `PUT /api/medical-cases/{case_id}`
- `POST /api/visit-records`
- `GET /api/visit-records`
- `GET /api/visit-records/{visit_record_id}`
- `PUT /api/visit-records/{visit_record_id}`

## Quick Start

Run all commands from the repository root `PatientCare-Agent/` unless noted otherwise.

### 1. Create a Python environment

Using `conda`:

```powershell
conda --no-plugins create --solver=classic -n patientcare-agent-dev python=3.12 -y
conda activate patientcare-agent-dev
```

Or with your preferred Python virtual environment tool.

### 2. Install backend dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
QWEN_API_KEY="your_qwen_api_key"
QWEN_MODEL="qwen3.5-plus"
QWEN_EMBEDDING_MODEL="text-embedding-v4"
QWEN_EMBEDDING_DIMENSIONS="1024"
```

Optional:

- `QWEN_BASE_URL` if you want to override the default DashScope-compatible endpoint

### 4. Install frontend dependencies

```powershell
Set-Location frontend
npm install
Set-Location ..
```

### 5. Start the backend

```powershell
python -m uvicorn app.main:app --reload
```

Backend URLs:

- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 6. Start the frontend

Open another terminal:

```powershell
Set-Location frontend
npm run dev
```

Frontend URL:

- Workspace: [http://127.0.0.1:5173](http://127.0.0.1:5173)

The Vite dev server proxies `/api` and `/media` requests to `http://127.0.0.1:8000`.

## Build for Local Preview

You can also build the frontend and let FastAPI serve the compiled assets:

```powershell
Set-Location frontend
npm run build
Set-Location ..
python -m uvicorn app.main:app --reload
```

Then open:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

`app.main` will serve `frontend/dist` automatically when it exists.

## Demo Data

The project uses a local SQLite database at:

- `data/patient_agent.db`

To import demo data:

```powershell
sqlite3 data/patient_agent.db < scripts/seed_demo_data.sql
```

If `sqlite3` is not available on your machine, you can import the SQL file with any SQLite GUI tool.

## Local Testing

There is a simple test script for exercising the agent directly:

```powershell
python scripts/test_qwen_agent.py "Summarize the latest visit for patient P1001"
```

With an image:

```powershell
python scripts/test_qwen_agent.py "Please analyze this image" --image-file data\\example.png
```

## Notes for Open Source Publishing

Before publishing this project to GitHub, it is recommended to avoid committing:

- `.env`
- `frontend/node_modules/`
- `frontend/dist/`
- `data/*.db`
- `data/faiss/`
- `__pycache__/`
- IDE and OS-specific files

This repository now includes a `.gitignore` for those items.

## Suggested Repository Name

If you want a short and clear English repository name, use:

- `patientcare-agent`

It matches the current project terminology, is easy to understand, and works well as a GitHub repository name.

## Current Limitations

- no authentication or authorization system yet
- no production deployment configuration
- no formal automated backend/frontend test suite yet
- local SQLite and FAISS storage are aimed at demo usage
- medical safety, privacy, and compliance controls are not production-complete

## License

No license file is currently included.

If you plan to open source the project publicly, consider adding one of these:

- MIT License
- Apache-2.0
- GPL-3.0
