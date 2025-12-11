# Car Diagnosis System - Project Documentation

## 1. Project Overview
The **Car Diagnosis System** is an AI-powered application designed to help users diagnose car issues. It combines traditional complaint tracking with advanced Multimodal RAG (Retrieval-Augmented Generation) to analyze user descriptions and uploaded documents (like repair invoices or manuals).

### Key Features
- **AI Mechanic Chat**: Interactive chat with an AI assistant that serves as a mechanic.
- **Complaint Management**: Users can submit complaints with vehicle details.
- **RAG Pipeline**: Uploads (PDFs, Images) are indexed and used by the AI to provide context-aware answers.
- **Automated Classification**: The system automatically categorizes complaints (e.g., "Engine", "Brakes") using a trained ML model.

---

## 2. System Architecture

The project follows a modern microservices-like architecture using Docker.

```mermaid
graph TD
    Client[React Frontend] -->|API Requests| Nginx[Nginx / Proxy]
    Nginx -->|/api| Backend[Django Backend]
    Nginx -->|/static| Static[Static Files]
    
    subgraph Data Layer
        Backend --> DB[(PostgreSQL)]
        Backend --> Redis[(Redis)]
    end
    
    subgraph AI Layer
        Backend --> Ollama[Ollama (LLM)]
        Backend --> FAISS[FAISS (Vector DB)]
    end
```

### Components
- **Frontend**: React.js with TailwindCSS (Port 80)
- **Backend**: Django REST Framework (Port 8000)
- **Database**: PostgreSQL 15 (Port 5432)
- **Task Queue**: Celery with Redis (for async ML tasks)
- **AI Engine**: Ollama (running locally on host or container)
- **Vector Store**: FAISS (for storing document embeddings)

---

## 3. Setup & Installation

### Prerequisites
- Docker & Docker Compose
- Ollama (installed on host machine)

### Configuration
1. **Environment Variables**: Managed in `.env` file at the root.
   - `OLLAMA_BASE_URL`: `http://host.docker.internal:11434`
   - `OLLAMA_TEXT_MODEL`: `gpt-oss:120b-cloud` (or `llama3`)

2. **Starting the Application**:
   ```bash
   docker-compose up -d --build
   ```

3. **Running Migrations** (First time only):
   ```bash
   docker-compose exec backend python manage.py migrate
   ```

---

## 4. AI & RAG Pipeline

### How it Works
1. **Document Upload**: User uploads a file (PDF/Text) via the Chat UI.
2. **Text Extraction**: `PyMuPDF` extracts text from the document.
3. **Chunking**: Text is split into manageable chunks (e.g., 1000 characters).
4. **Embedding**: `sentence-transformers` (all-MiniLM-L6-v2) converts text to vector embeddings.
5. **Indexing**: Embeddings are stored in the local FAISS index.
6. **Retrieval**: When a user asks a question:
   - The question is embedded.
   - FAISS finds the most relevant document chunks.
   - These chunks are sent to the LLM (Ollama) as context.

### Troubleshooting AI
- **Model Check**: Run `backend/scripts/test_ollama.py` to verify connection and model availability.
- **Dependencies**: Ensure `sentence-transformers` is installed in the backend container.

---

## 5. API Documentation

### Base URL: `/api/v1/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/complaints/` | GET, POST | List or create complaints |
| `/complaints/quick-submit/` | POST | Quick submission (Customer + Car + Complaint) |
| `/chat/` | GET, POST | Manage chat sessions |
| `/chat/{id}/send_message/` | POST | Send a message to AI (Streaming response) |
| `/chat/{id}/upload_document/` | POST | Upload file for RAG analysis |

---

## 6. Verification Tools

The project includes built-in scripts to verify system health.

- **Storage & Database Verification**:
  ```bash
  docker exec car_diagnosis_backend python scripts/verify_storage.py
  ```
- **Full System Check**:
  ```bash
  docker exec car_diagnosis_backend python scripts/full_system_check.py
  ```

---

## 7. Directory Structure
- `backend/`: Django project root
  - `apps/`: Feature apps (complaints, chat, ml_models, etc.)
  - `ml_models/`: Logic for RAG, Embeddings, and Classifiers.
  - `media/`: User uploads (mounted volume).
- `frontend/`: React application source.
- `rag data/`: Default knowledge base for the system.
