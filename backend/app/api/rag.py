"""
RAG Q&A API Routes
==================
Endpoints for RAG-powered document question answering.

Endpoints:
    POST /api/rag/ask              — Ask a question about documents
    POST /api/rag/search           — Semantic search across documents
    POST /api/rag/{id}/index       — Index a document for RAG
    DELETE /api/rag/{id}/index     — Remove doc from RAG index
    GET  /api/rag/stats            — Get RAG index statistics
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.document_service import DocumentService
from app.models.document import DocumentStatus
from app.schemas.document import (
    QuestionRequest, AnswerResponse,
    SearchRequest, SearchResult,
)
from uuid import UUID
import logging
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["RAG Q&A"])

# Lazy-loaded QA engine singleton
_qa_engine = None


def get_qa_engine():
    global _qa_engine
    if _qa_engine is None:
        from app.rag.qa_engine import QAEngine
        _qa_engine = QAEngine()
    return _qa_engine


# ── Ask Question ─────────────────────────────────────────────

@router.post("/ask", response_model=AnswerResponse)
async def ask_question(
    request: QuestionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Ask a question and get an AI-powered answer.

    The RAG pipeline:
    1. Embeds your question
    2. Searches FAISS for relevant document chunks
    3. Feeds the context to an LLM
    4. Returns an answer with source citations

    You can optionally filter by specific document IDs to
    ask questions about particular documents only.
    """
    qa = get_qa_engine()

    doc_ids = None
    if request.document_ids:
        doc_ids = [str(d) for d in request.document_ids]

    result = qa.ask(
        question=request.question,
        top_k=request.top_k,
        document_ids=doc_ids,
    )

    return AnswerResponse(
        answer=result["answer"],
        sources=result["sources"],
        confidence=result["confidence"],
    )


# ── Semantic Search ──────────────────────────────────────────

@router.post("/search")
async def semantic_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Search for relevant document chunks using semantic similarity.

    Unlike keyword search, this finds conceptually similar content.
    "revenue growth" will find "income increase" even without exact keywords.
    """
    qa = get_qa_engine()

    results = qa.search(
        query=request.query,
        top_k=request.top_k,
    )

    return {
        "query": request.query,
        "results": results,
        "total": len(results),
    }


# ── Index Document ───────────────────────────────────────────

@router.post("/{document_id}/index")
async def index_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Index a document for RAG retrieval.

    Requires: Document must have extracted text (run OCR first).

    What happens:
    1. Text is split into chunks (~800 chars each)
    2. Each chunk is converted to an embedding vector
    3. Vectors are stored in the FAISS index
    4. Document status is updated to 'indexed'

    After indexing, you can ask questions about this document!
    """
    service = DocumentService(db)
    doc = await service.get_document(document_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No extracted text. Run OCR first: POST /api/ml/{id}/ocr",
        )

    qa = get_qa_engine()
    num_chunks = qa.index_document(
        document_id=str(document_id),
        text=doc.extracted_text,
        metadata={
            "filename": doc.filename,
            "file_type": doc.file_type,
        },
    )

    # Update document status
    await service.update_status(document_id, DocumentStatus.INDEXED)

    return {
        "message": "Document indexed successfully",
        "document_id": str(document_id),
        "chunks_indexed": num_chunks,
    }


# ── Remove from Index ────────────────────────────────────────

@router.delete("/{document_id}/index")
async def remove_from_index(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove a document from the RAG index."""
    qa = get_qa_engine()
    qa.remove_document(str(document_id))

    return {"message": "Document removed from index"}


# ── Stats ────────────────────────────────────────────────────

@router.get("/stats")
async def get_rag_stats():
    """Get RAG index statistics."""
    qa = get_qa_engine()
    return qa.get_stats()
