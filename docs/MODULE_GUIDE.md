# IntelliDoc — Complete Module Guide
## How Everything Works: Setup, Run, Control

---

## Module 1: Data Pipeline (S3 + PostgreSQL + Docker)

### What this module does
- Stores documents in AWS S3 (object storage)
- Tracks document metadata and processing status in PostgreSQL
- Runs infrastructure locally via Docker Compose

### Setup

```bash
# 1. Start infrastructure services
docker-compose up -d

# 2. Verify services are running
docker-compose ps
# Should show: postgres (5432), redis (6379), localstack (4566)

# 3. Create the local S3 bucket (using LocalStack)
aws --endpoint-url=http://localhost:4566 s3 mb s3://intellidoc-documents

# 4. For local development, update .env:
#    AWS_ACCESS_KEY_ID=test
#    AWS_SECRET_ACCESS_KEY=test
#    Then add to s3_service.py __init__:
#    endpoint_url="http://localhost:4566"
```

### Key Files
| File | Purpose |
|------|---------|
| `docker-compose.yml` | PostgreSQL, Redis, LocalStack |
| `app/config.py` | All environment configuration |
| `app/database.py` | Async SQLAlchemy engine + sessions |
| `app/models/document.py` | Document, Metadata, ProcessingJob |
| `app/services/s3_service.py` | S3 upload/download/presign |
| `app/services/document_service.py` | Document CRUD operations |

### How S3 Upload Works
```
User uploads file → API validates type/size → S3 upload (unique key) 
→ DB record created → Return document ID
```

### How to Control & Test
```bash
# Upload a document
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@sample.pdf"

# List documents
curl http://localhost:8000/api/documents/

# Get download URL
curl http://localhost:8000/api/documents/{id}/download

# View DB directly
docker exec -it intellidoc-postgres psql -U intellidoc_user -d intellidoc
SELECT * FROM documents;
```

---

## Module 2: ML/AI Engine (OCR + Classification + NER + Summarization)

### What this module does
- **OCR**: Extracts text from PDFs/images using Tesseract
- **Classifier**: Categorizes documents (invoice, report, resume, etc.)
- **NER**: Finds people, organizations, locations in text
- **Summarizer**: Creates AI-generated summaries
- **Image Analyzer**: Checks quality, detects tables, analyzes layout

### Setup

```bash
# Install Tesseract OCR
# Windows:
choco install tesseract
# Or download from: https://github.com/UB-Mannheim/tesseract/wiki

# Install poppler (for PDF→Image conversion)
# Windows:
choco install poppler

# Download ML models (happens automatically on first use)
# Models are cached in ./ml/models_cache/
# First run takes 2-5 minutes to download models (~3GB total)
```

### Key Files
| File | Purpose |
|------|---------|
| `app/ml/ocr.py` | Tesseract OCR + image preprocessing |
| `app/ml/classifier.py` | Zero-shot BERT classification |
| `app/ml/ner.py` | Named entity extraction |
| `app/ml/summarizer.py` | BART text summarization |
| `app/ml/image_analyzer.py` | OpenCV image analysis |
| `app/api/ml.py` | ML API endpoints |

### OCR Image Preprocessing Pipeline
```
Image → Grayscale → Denoise → Adaptive Threshold → Deskew → Tesseract
```

### How to Use Each ML Feature

```bash
# Step 1: Upload a document first
curl -X POST http://localhost:8000/api/documents/upload -F "file=@doc.pdf"
# Note the returned document ID

# Step 2: Run OCR
curl -X POST http://localhost:8000/api/ml/{doc_id}/ocr
# Returns: {text, confidence, page_count}

# Step 3: Classify (requires OCR first)
curl -X POST http://localhost:8000/api/ml/{doc_id}/classify
# Returns: {label: "report", confidence: 0.89, all_labels: [...]}

# Step 4: Extract entities (requires OCR first)
curl -X POST http://localhost:8000/api/ml/{doc_id}/ner
# Returns: {entities: [{entity: "Google", label: "ORG", score: 0.98}]}

# Step 5: Summarize (requires OCR first)
curl -X POST http://localhost:8000/api/ml/{doc_id}/summarize
# Returns: {summary: "...", original_length: 5000, summary_length: 200}

# Step 6: Analyze image quality
curl -X POST http://localhost:8000/api/ml/{doc_id}/analyze
# Returns: {quality_score: 0.85, has_tables: true, page_type: "text_heavy"}
```

### ML Models Used
| Model | Task | Size | Source |
|-------|------|------|--------|
| Tesseract | OCR | Built-in | System install |
| facebook/bart-large-mnli | Classification | ~1.6GB | HuggingFace |
| dslim/bert-base-NER | Entity extraction | ~400MB | HuggingFace |
| facebook/bart-large-cnn | Summarization | ~1.6GB | HuggingFace |

---

## Module 3: RAG Pipeline (FAISS + Embeddings + LLM)

### What this module does
- Chunks documents into searchable pieces
- Converts text to vector embeddings
- Stores embeddings in FAISS for fast semantic search
- Generates answers using an LLM (Mistral via Ollama)

### Setup

```bash
# Install Ollama (LLM runtime)
# Download from: https://ollama.com
# Then pull the Mistral model:
ollama pull mistral

# Start Ollama server (runs on port 11434)
ollama serve
```

### Key Files
| File | Purpose |
|------|---------|
| `app/rag/chunker.py` | LangChain text splitting |
| `app/rag/embeddings.py` | Sentence-Transformers embeddings |
| `app/rag/vector_store.py` | FAISS index management |
| `app/rag/qa_engine.py` | Full RAG Q&A pipeline |
| `app/api/rag.py` | RAG API endpoints |

### RAG Pipeline Flow
```
Document Text → Chunk (800 chars) → Embed (384-dim vector) → Store in FAISS
                                                                    │
User Question → Embed → Search FAISS → Top-K chunks → Build prompt → LLM → Answer
```

### How to Use

```bash
# Step 1: After OCR, index the document for RAG
curl -X POST http://localhost:8000/api/rag/{doc_id}/index
# Returns: {chunks_indexed: 15}

# Step 2: Ask a question!
curl -X POST http://localhost:8000/api/rag/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the key responsibilities?", "top_k": 5}'
# Returns: {answer: "...", sources: [...], confidence: 0.85}

# Step 3: Semantic search (without LLM generation)
curl -X POST http://localhost:8000/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning requirements", "top_k": 10}'

# Check RAG stats
curl http://localhost:8000/api/rag/stats
```

### FAISS Index Persistence
- Index is saved to `app/rag/faiss_index/` as `index.faiss` + `metadata.json`
- Auto-loaded on server startup
- Auto-saved after each indexing operation

---

## Module 4: Backend API (FastAPI + Auth)

### What this module does
- RESTful API for all operations
- JWT authentication for secure access
- WebSocket support for real-time updates
- CORS configuration for frontend

### How to Run

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Interactive API Docs
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Authentication Flow
```bash
# 1. Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@test.com", "username": "testuser", "password": "securepass123"}'
# Returns: {access_token: "eyJ...", user: {...}}

# 2. Use token for authenticated requests
curl -H "Authorization: Bearer eyJ..." \
  http://localhost:8000/api/auth/me
```

---

## Module 5: Frontend Dashboard (React + Vite)

### Coming Next!
The React frontend will include:
- 📤 Document upload with drag-and-drop
- 📊 Processing status dashboard
- 💬 Chat-based Q&A interface
- 📈 Analytics with charts

---

## Module 6: AWS Deployment

### AWS Services Used
| Service | Purpose | Est. Cost/Month |
|---------|---------|----------------|
| EC2 (t3.medium) | Backend server | ~$30 |
| RDS (db.t3.micro) | PostgreSQL | ~$15 |
| S3 | Document storage | ~$0.25 |
| Lambda | Event triggers | Free tier |
| CloudWatch | Monitoring | Free tier |

### Deployment Steps
1. Dockerize the application
2. Push to ECR (container registry)
3. Deploy to EC2/ECS
4. Set up RDS PostgreSQL
5. Configure S3 bucket with proper IAM
6. Set up CloudWatch monitoring
7. Configure CI/CD with GitHub Actions

---

## Complete Workflow: End-to-End

```bash
# 1. Start services
docker-compose up -d
ollama serve

# 2. Start backend
cd backend && uvicorn app.main:app --reload

# 3. Upload a document
# Use Swagger UI at http://localhost:8000/docs
# POST /api/documents/upload

# 4. Run ML pipeline
# POST /api/ml/{id}/ocr
# POST /api/ml/{id}/classify
# POST /api/ml/{id}/ner
# POST /api/ml/{id}/summarize

# 5. Index for RAG
# POST /api/rag/{id}/index

# 6. Ask questions!
# POST /api/rag/ask {"question": "What does this document say about...?"}
```
