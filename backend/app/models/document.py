"""
Document Models
===============
SQLAlchemy models for documents, their metadata, and processing jobs.

Database Schema:
┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
│  documents   │────>│document_metadata │     │ processing_jobs│
│              │     │                  │     │                │
│ id (PK)      │     │ id (PK)          │     │ id (PK)        │
│ filename     │     │ document_id (FK) │     │ document_id(FK)│
│ s3_key       │     │ key              │     │ job_type       │
│ file_type    │     │ value            │     │ status         │
│ file_size    │     └──────────────────┘     │ result_data    │
│ status       │                              │ error_message  │
│ uploaded_by  │                              └────────────────┘
│ created_at   │
│ updated_at   │
└──────────────┘
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, BigInteger, Text, DateTime,
    ForeignKey, JSON, Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import enum


# ── Enums ────────────────────────────────────────────────────

class DocumentStatus(str, enum.Enum):
    """Tracks the lifecycle of a document through the pipeline."""
    UPLOADED = "uploaded"           # File is in S3
    PROCESSING = "processing"      # ML pipeline is running
    PROCESSED = "processed"        # All ML tasks completed
    INDEXED = "indexed"            # Added to vector store
    FAILED = "failed"              # Processing encountered an error


class JobType(str, enum.Enum):
    """Types of ML processing jobs."""
    OCR = "ocr"
    CLASSIFICATION = "classification"
    NER = "ner"
    SUMMARIZATION = "summarization"
    IMAGE_ANALYSIS = "image_analysis"
    EMBEDDING = "embedding"


class JobStatus(str, enum.Enum):
    """Status of an individual processing job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Document Model ───────────────────────────────────────────

class Document(Base):
    """
    Core document entity.
    Each uploaded file becomes one Document record.
    """
    __tablename__ = "documents"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique document identifier"
    )
    filename = Column(
        String(255),
        nullable=False,
        doc="Original filename as uploaded by user"
    )
    s3_key = Column(
        String(512),
        nullable=False,
        unique=True,
        doc="S3 object key (path in bucket)"
    )
    file_type = Column(
        String(50),
        nullable=False,
        doc="MIME type or extension (pdf, png, etc.)"
    )
    file_size = Column(
        BigInteger,
        nullable=False,
        doc="File size in bytes"
    )
    status = Column(
        SQLEnum(DocumentStatus),
        default=DocumentStatus.UPLOADED,
        nullable=False,
        doc="Current processing status"
    )
    extracted_text = Column(
        Text,
        nullable=True,
        doc="Full text extracted by OCR"
    )
    summary = Column(
        Text,
        nullable=True,
        doc="AI-generated summary of the document"
    )
    classification = Column(
        String(100),
        nullable=True,
        doc="Document type classification (invoice, report, etc.)"
    )
    classification_confidence = Column(
        String(10),
        nullable=True,
        doc="Classification confidence score"
    )
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        doc="User who uploaded this document"
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────
    metadata_entries = relationship(
        "DocumentMetadata",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    processing_jobs = relationship(
        "ProcessingJob",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}')>"


# ── Document Metadata ────────────────────────────────────────

class DocumentMetadata(Base):
    """
    Key-value metadata for documents.
    Stores extracted entities, page count, language, etc.
    Flexible schema — any key can be stored.
    """
    __tablename__ = "document_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    key = Column(String(100), nullable=False, doc="Metadata key (e.g., 'page_count', 'language')")
    value = Column(Text, nullable=False, doc="Metadata value")

    document = relationship("Document", back_populates="metadata_entries")

    def __repr__(self):
        return f"<DocumentMetadata(key='{self.key}', value='{self.value[:50]}')>"


# ── Processing Job ───────────────────────────────────────────

class ProcessingJob(Base):
    """
    Tracks individual ML processing tasks for a document.
    Each document goes through multiple jobs: OCR → Classification → NER → etc.
    """
    __tablename__ = "processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_type = Column(
        SQLEnum(JobType),
        nullable=False,
        doc="Which ML task this job performs"
    )
    status = Column(
        SQLEnum(JobStatus),
        default=JobStatus.PENDING,
        nullable=False,
    )
    result_data = Column(
        JSON,
        nullable=True,
        doc="JSON result from the ML model"
    )
    error_message = Column(
        Text,
        nullable=True,
        doc="Error details if job failed"
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document = relationship("Document", back_populates="processing_jobs")

    def __repr__(self):
        return f"<ProcessingJob(type='{self.job_type}', status='{self.status}')>"
