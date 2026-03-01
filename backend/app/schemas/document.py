"""
Document Schemas
================
Pydantic models for API request/response validation.

These schemas define the shape of data going IN and OUT of the API.
They are separate from SQLAlchemy models (which define the DB schema).
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ── Document Schemas ─────────────────────────────────────────

class DocumentBase(BaseModel):
    """Fields shared across create/read schemas."""
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type (pdf, png, etc.)")


class DocumentCreate(DocumentBase):
    """Schema for creating a new document record (after upload)."""
    s3_key: str = Field(..., description="S3 object key")
    file_size: int = Field(..., description="File size in bytes")


class DocumentResponse(DocumentBase):
    """Schema returned to the client for a single document."""
    id: UUID
    s3_key: str
    file_size: int
    status: str
    extracted_text: Optional[str] = None
    summary: Optional[str] = None
    classification: Optional[str] = None
    classification_confidence: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    metadata_entries: List["MetadataResponse"] = []

    class Config:
        from_attributes = True  # Allows conversion from SQLAlchemy model


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


# ── Metadata Schemas ─────────────────────────────────────────

class MetadataCreate(BaseModel):
    """Add a metadata key-value pair to a document."""
    key: str = Field(..., description="Metadata key")
    value: str = Field(..., description="Metadata value")


class MetadataResponse(BaseModel):
    """Metadata entry response."""
    id: UUID
    key: str
    value: str

    class Config:
        from_attributes = True


# ── Processing Job Schemas ───────────────────────────────────

class ProcessingJobResponse(BaseModel):
    """Status of an individual processing job."""
    id: UUID
    job_type: str
    status: str
    result_data: Optional[dict] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentProcessingStatus(BaseModel):
    """Full processing status for a document with all jobs."""
    document_id: UUID
    document_status: str
    jobs: List[ProcessingJobResponse]


# ── ML Task Schemas ──────────────────────────────────────────

class OCRResult(BaseModel):
    """Result from OCR processing."""
    text: str
    confidence: float
    page_count: int


class ClassificationResult(BaseModel):
    """Result from document classification."""
    label: str
    confidence: float
    all_labels: List[dict]


class NERResult(BaseModel):
    """Named entities extracted from the document."""
    entities: List[dict] = Field(
        ...,
        description="List of {entity, label, score} dicts"
    )


class SummaryResult(BaseModel):
    """Document summarization result."""
    summary: str
    original_length: int
    summary_length: int


# ── RAG Schemas ──────────────────────────────────────────────

class QuestionRequest(BaseModel):
    """User question for RAG Q&A."""
    question: str = Field(..., min_length=3, description="The question to ask")
    document_ids: Optional[List[UUID]] = Field(
        None,
        description="Optional: limit search to specific documents"
    )
    top_k: int = Field(5, ge=1, le=20, description="Number of contexts to retrieve")


class AnswerResponse(BaseModel):
    """RAG-generated answer with sources."""
    answer: str
    sources: List[dict] = Field(
        ...,
        description="List of source chunks with document info"
    )
    confidence: float


class SearchRequest(BaseModel):
    """Semantic document search."""
    query: str = Field(..., min_length=3)
    top_k: int = Field(10, ge=1, le=50)


class SearchResult(BaseModel):
    """A single search result."""
    document_id: UUID
    chunk_text: str
    score: float
    metadata: dict
