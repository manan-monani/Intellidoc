# 🔍 IntelliDoc — Intelligent Document Processing & Analysis Platform

> An industry-grade, end-to-end AI/ML platform for intelligent document processing, analysis, and question-answering. Built with FastAPI, PyTorch, FAISS, and deployed on AWS.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![PyTorch](https://img.shields.io/badge/PyTorch-2.5-red)
![FAISS](https://img.shields.io/badge/FAISS-Vector_Search-orange)
![AWS](https://img.shields.io/badge/AWS-Deployed-yellow)

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Frontend (React)                       │
│   Upload Portal │ Q&A Chat │ Analytics │ Admin           │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              FastAPI Backend (REST API)                   │
│   Documents │ ML Processing │ RAG Q&A │ Auth             │
└──────┬─────────────┬──────────────┬─────────────────────┘
       │             │              │
┌──────▼──────┐ ┌────▼─────┐ ┌─────▼──────┐
│ Data Layer  │ │ ML Engine│ │RAG Pipeline│
│ S3 + RDS   │ │ OCR,NER  │ │FAISS+LLM  │
│ + Redis    │ │ BERT,BART│ │ Ollama     │
└─────────────┘ └──────────┘ └────────────┘
```

## ✨ Features

| Feature | Description | Tech Stack |
|---------|-------------|-----------|
| 📄 Document Upload | Upload PDFs, images, TIFF files | S3, FastAPI, PostgreSQL |
| 🔤 OCR | Extract text from scanned documents | Tesseract, OpenCV |
| 🏷️ Classification | Auto-classify document types | BERT (zero-shot) |
| 📍 NER | Extract people, orgs, locations | HuggingFace Transformers |
| 📝 Summarization | AI-generated document summaries | BART (facebook/bart-large-cnn) |
| 🖼️ Image Analysis | Quality, layout, table detection | OpenCV |
| 🤖 RAG Q&A | Ask questions about your documents | FAISS + Sentence-Transformers + Ollama |
| 🔐 Authentication | JWT-based user auth | bcrypt + python-jose |
| 📊 Analytics | Processing statistics dashboard | PostgreSQL aggregations |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Tesseract OCR (`choco install tesseract` on Windows)
- Ollama (`ollama serve` + `ollama pull mistral`)

### 1. Clone & Setup

```bash
git clone <your-repo-url>
cd intellidoc

# Create .env from template
cp .env.example .env
# Edit .env with your settings
```

### 2. Start Infrastructure

```bash
# Start PostgreSQL, Redis, and LocalStack (S3)
docker-compose up -d

# Create local S3 bucket
aws --endpoint-url=http://localhost:4566 s3 mb s3://intellidoc-documents
```

### 3. Install Dependencies

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

### 4. Run the Backend

```bash
# From the backend/ directory
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open API Docs

Navigate to `http://localhost:8000/docs` — interactive Swagger UI with all endpoints.

---

## 📁 Project Structure

```
intellidoc/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── config.py         # Environment configuration
│   │   ├── database.py       # Async SQLAlchemy
│   │   ├── models/           # Database models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── api/              # REST API routes
│   │   │   ├── documents.py  # Document CRUD
│   │   │   ├── ml.py         # ML processing
│   │   │   ├── rag.py        # RAG Q&A
│   │   │   └── auth.py       # Authentication
│   │   ├── services/         # Business logic
│   │   │   ├── s3_service.py
│   │   │   ├── document_service.py
│   │   │   └── auth_service.py
│   │   ├── ml/               # ML models
│   │   │   ├── ocr.py        # Tesseract OCR
│   │   │   ├── classifier.py # BERT classifier
│   │   │   ├── ner.py        # Named Entity Recognition
│   │   │   ├── summarizer.py # BART summarizer
│   │   │   └── image_analyzer.py  # OpenCV analysis
│   │   └── rag/              # RAG pipeline
│   │       ├── chunker.py    # Document chunking
│   │       ├── embeddings.py # Embedding generation
│   │       ├── vector_store.py # FAISS index
│   │       └── qa_engine.py  # Q&A engine
│   └── requirements.txt
├── frontend/                  # React dashboard
├── docker-compose.yml         # Local dev services
├── .env.example               # Environment template
└── docs/                      # Module guides
```

---

## 🧪 API Endpoints

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/upload` | Upload a document |
| GET | `/api/documents/` | List all documents |
| GET | `/api/documents/{id}` | Get document details |
| GET | `/api/documents/{id}/status` | Processing status |
| DELETE | `/api/documents/{id}` | Delete a document |

### ML Processing
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ml/{id}/ocr` | Extract text (OCR) |
| POST | `/api/ml/{id}/classify` | Classify document type |
| POST | `/api/ml/{id}/ner` | Extract named entities |
| POST | `/api/ml/{id}/summarize` | Generate summary |
| POST | `/api/ml/{id}/analyze` | Image quality analysis |

### RAG Q&A
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/rag/ask` | Ask a question |
| POST | `/api/rag/search` | Semantic search |
| POST | `/api/rag/{id}/index` | Index for RAG |

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register user |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Current user |

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | FastAPI | Async REST API |
| Database | PostgreSQL | Document metadata |
| Cache | Redis | Caching & pub/sub |
| Storage | AWS S3 | Document files |
| OCR | Tesseract + OpenCV | Text extraction |
| NLP | HuggingFace Transformers | NER, Classification |
| Summarization | BART | Abstractive summary |
| Embeddings | Sentence-Transformers | Vector generation |
| Vector Search | FAISS | Similarity search |
| LLM | Ollama (Mistral) | Answer generation |
| Auth | JWT + bcrypt | Authentication |
| Containerization | Docker | Deployment |
| Cloud | AWS (EC2, S3, RDS) | Production |

---

## 📜 License

MIT License — see LICENSE file for details.
