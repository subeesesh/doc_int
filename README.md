# Enterprise Document Intelligence & Decision Support Platform

A self-hosted RAG (Retrieval-Augmented Generation) platform for enterprise document search and Q&A, powered by local LLMs, vector search, and knowledge graphs.

## Architecture

```
User → FastAPI → Query Understanding
                      ↓
         ┌────────────┼────────────┐
         ↓            ↓            ↓
  Elasticsearch    Qdrant       Neo4j
   BM25 Search   Vector Search  Graph
         └────────────┼────────────┘
                      ↓
                 RRF Fusion
                      ↓
                  Reranker
                      ↓
              LLM Generation (Qwen3)
                      ↓
            Citations & Provenance
```

### Document Ingestion
```
Upload → MinIO → Docling/OCR → Pages → Chunks
                                          ↓
                               ┌──────────┴──────────┐
                               ↓                     ↓
                          PostgreSQL          Search Indexes
                          (metadata)       (Qdrant + Elasticsearch)
                               ↓
                          Neo4j Graph
                        (entities/facts)
```

## Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI (Python 3.12) |
| Database | PostgreSQL 17 (psycopg3) |
| Vector DB | Qdrant |
| Graph DB | Neo4j Community |
| Object Storage | MinIO |
| Cache/Queue | Redis |
| Search | Elasticsearch 8 |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (384d) |
| LLM | Qwen3:1.7b via Ollama (local) |
| OCR/Layout | Docling + RapidOCR |
| Migrations | Alembic |
| Task Queue | Celery |

## Quick Start

### 1. Prerequisites

- Docker Desktop
- Python 3.12
- [Ollama](https://ollama.ai) with `qwen3:1.7b` model

```bash
ollama pull qwen3:1.7b
```

### 2. Start Infrastructure

```bash
cd infrastructure
docker compose up -d
```

Wait for all services to be healthy:
```bash
docker compose ps
```

### 3. Backend Setup

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt

# Apply database migrations
alembic upgrade head

# Create test users
python scripts/create_test_user.py
```

### 4. Start the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Open the UI

Visit [http://localhost:8000](http://localhost:8000)

Default credentials:
- **Admin**: `admin@enterprise.local` / `admin123`
- **User**: `user@enterprise.local` / `user123`

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Ports

| Service | Host Port |
|---------|-----------|
| FastAPI | 8000 |
| PostgreSQL | 5433 |
| Qdrant HTTP | 6335 |
| Qdrant gRPC | 6336 |
| Neo4j HTTP | 7474 |
| Neo4j Bolt | 7687 |
| Redis | 6379 |
| MinIO API | 9000 |
| MinIO Console | 9001 |
| Elasticsearch | 9200 |

## API Endpoints

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Register new user |
| `POST` | `/auth/login` | Login (returns JWT) |
| `GET` | `/auth/me` | Get current user |

### Documents
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/documents/upload` | Upload document |
| `GET` | `/documents` | List documents |
| `GET` | `/documents/{id}` | Get document |
| `POST` | `/documents/{id}/process` | Trigger processing |
| `GET` | `/documents/{id}/status` | Processing status |
| `GET` | `/documents/{id}/pages` | Get extracted pages |
| `GET` | `/documents/{id}/chunks` | Get text chunks |

### Search
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/search/semantic` | Vector search (Qdrant) |
| `POST` | `/search/keyword` | BM25 search (Elasticsearch) |
| `POST` | `/search/hybrid` | Hybrid search with RRF fusion |

### Q&A
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/query/ask` | RAG Q&A with citations |
| `GET` | `/query/conversations` | List conversations |
| `GET` | `/query/conversations/{id}` | Get conversation history |

### Analysis
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/analysis/summary/{id}` | Document summary |
| `GET` | `/analysis/entities/{id}` | Extracted entities |
| `GET` | `/analysis/facts/{id}` | Extracted facts |
| `POST` | `/analysis/compare` | Compare two documents |

### System
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |

## Processing a Document

```bash
# Via API
curl -X POST http://localhost:8000/documents/{document_id}/process

# Via script
cd backend
python -m scripts.process_document <document_id>
```

The pipeline:
1. Downloads file from MinIO
2. Runs Docling (PDF/DOCX layout analysis + OCR)
3. Extracts pages and saves to PostgreSQL
4. Chunks text (RecursiveChunker, 512 tokens, 50 overlap)
5. Generates embeddings → upserts to Qdrant
6. Indexes text → Elasticsearch
7. Extracts entities/facts/relationships → PostgreSQL + Neo4j
8. Marks job complete

All steps are **idempotent** — reprocessing the same document clears and rebuilds all derived data.

## Configuration

Edit `backend/.env`:

```env
# Database
DATABASE_URL=postgresql+psycopg://enterprise_user:enterprise_password@localhost:5433/enterprise_db

# LLM (local Ollama)
LLM_PROVIDER=local
LLM_MODEL=qwen3:1.7b
OLLAMA_BASE_URL=http://localhost:11434

# Storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=enterprise_admin
MINIO_SECRET_KEY=enterprise_password

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# Vector DB
QDRANT_HOST=localhost
QDRANT_PORT=6335

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=enterprise_neo4j_password

# Elasticsearch
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
```

### LLM Providers

The platform supports multiple LLM backends via `LLM_PROVIDER`:

| Value | Description |
|-------|-------------|
| `local` | Ollama (default) — uses `LLM_MODEL` |
| `mock` | Returns canned responses (for testing) |
| `bedrock` | AWS Bedrock (stub, future work) |

## Running Tests

```bash
cd backend

# Unit tests (no Docker required)
python -m pytest tests/test_services.py -v

# All tests (requires PostgreSQL running)
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_auth.py -v
```

## Development Scripts

```bash
cd backend

# Health check all services
python scripts/health_check.py

# Reindex a document
python scripts/reindex_document.py <document_id>

# Run search tests
python scripts/search_test.py
python scripts/hybrid_search_test.py

# Seed test data
python scripts/seed_data.py

# Evaluation benchmark
python scripts/evaluate.py
```

## Supported File Types

- PDF (`.pdf`)
- Word (`.docx`, `.doc`)
- Text (`.txt`)
- Images (`.png`, `.jpg`, `.jpeg`)

Max file size: 50 MB (configurable via `MAX_FILE_SIZE_MB`)

## Database Schema

The platform uses 20+ PostgreSQL tables:

**Core**: `users`, `roles`, `user_roles`  
**Documents**: `documents`, `document_versions`, `document_permissions`  
**Processing**: `pages`, `page_assets`, `processing_jobs`, `extraction_results`, `document_classifications`, `chunks`  
**Knowledge**: `entities`, `entity_mentions`, `facts`, `relationships`  
**Conversations**: `conversations`, `messages`, `answers`, `citations`  
**Retrieval**: `retrieval_logs`, `retrieved_items`  
**Evaluation**: `evaluation_datasets`, `evaluation_questions`, `evaluation_runs`, `evaluation_results`

## GPU Support

The platform runs on CPU by default. With an NVIDIA GPU (tested on RTX 3050 4GB VRAM):
- Embedding generation is CPU-based (MiniLM-L6 is fast on CPU)
- LLM inference runs via Ollama (uses GPU automatically)
- Docling OCR uses CPU (RapidOCR)

## License

Internal use — Enterprise Document Intelligence Platform
