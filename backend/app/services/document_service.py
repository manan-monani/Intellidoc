"""
Document Service
================
Business logic for document CRUD operations.

This layer sits BETWEEN the API routes and the database.
Routes should never call the database directly — they go through services.

Why?
- Keeps routes thin and focused on HTTP concerns
- Business logic is reusable across routes, background tasks, etc.
- Easier to test (mock the service, not the DB)
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from app.models.document import Document, DocumentMetadata, ProcessingJob
from app.models.document import DocumentStatus, JobType, JobStatus
from app.schemas.document import DocumentCreate
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Handles all document-related business logic.

    Usage:
        service = DocumentService(db_session)
        doc = await service.create_document(data)
        docs = await service.list_documents(page=1, page_size=20)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ───────────────────────────────────────────────

    async def create_document(
        self,
        data: DocumentCreate,
        user_id: Optional[UUID] = None,
    ) -> Document:
        """
        Create a new document record after file upload.

        Args:
            data: Document metadata from the upload
            user_id: Optional owning user

        Returns:
            Created Document object with relationships loaded
        """
        doc = Document(
            filename=data.filename,
            s3_key=data.s3_key,
            file_type=data.file_type,
            file_size=data.file_size,
            status=DocumentStatus.UPLOADED,
            uploaded_by=user_id,
        )
        self.db.add(doc)
        await self.db.flush()  # Get the ID without committing
        logger.info(f"Created document record: {doc.id} - {doc.filename}")

        # Eagerly load relationships so Pydantic can serialize without lazy loading
        await self.db.refresh(doc, attribute_names=["metadata_entries", "processing_jobs"])
        return doc

    # ── Read ─────────────────────────────────────────────────

    async def get_document(self, doc_id: UUID) -> Optional[Document]:
        """Get a document by ID with metadata and jobs loaded."""
        result = await self.db.execute(
            select(Document)
            .options(
                selectinload(Document.metadata_entries),
                selectinload(Document.processing_jobs),
            )
            .where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[DocumentStatus] = None,
        user_id: Optional[UUID] = None,
    ) -> Tuple[List[Document], int]:
        """
        List documents with pagination and optional filters.

        Returns:
            Tuple of (documents_list, total_count)
        """
        query = select(Document).options(
            selectinload(Document.metadata_entries)
        )

        # Apply filters
        if status:
            query = query.where(Document.status == status)
        if user_id:
            query = query.where(Document.uploaded_by == user_id)

        # Count total
        count_query = select(func.count(Document.id))
        if status:
            count_query = count_query.where(Document.status == status)
        if user_id:
            count_query = count_query.where(Document.uploaded_by == user_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        offset = (page - 1) * page_size
        query = (
            query
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        documents = result.scalars().all()

        return list(documents), total

    # ── Update ───────────────────────────────────────────────

    async def update_status(
        self,
        doc_id: UUID,
        status: DocumentStatus,
    ) -> Optional[Document]:
        """Update document processing status."""
        await self.db.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(status=status, updated_at=datetime.now(timezone.utc))
        )
        return await self.get_document(doc_id)

    async def update_extracted_text(
        self,
        doc_id: UUID,
        text: str,
    ) -> None:
        """Store OCR-extracted text."""
        await self.db.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(
                extracted_text=text,
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def update_classification(
        self,
        doc_id: UUID,
        label: str,
        confidence: str,
    ) -> None:
        """Store classification result."""
        await self.db.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(
                classification=label,
                classification_confidence=confidence,
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def update_summary(
        self,
        doc_id: UUID,
        summary: str,
    ) -> None:
        """Store AI-generated summary."""
        await self.db.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(
                summary=summary,
                updated_at=datetime.now(timezone.utc),
            )
        )

    # ── Delete ───────────────────────────────────────────────

    async def delete_document(self, doc_id: UUID) -> bool:
        """Delete a document and all related data (cascades)."""
        doc = await self.get_document(doc_id)
        if not doc:
            return False
        await self.db.delete(doc)
        logger.info(f"Deleted document: {doc_id}")
        return True

    # ── Metadata ─────────────────────────────────────────────

    async def add_metadata(
        self,
        doc_id: UUID,
        key: str,
        value: str,
    ) -> DocumentMetadata:
        """Add a metadata entry to a document."""
        meta = DocumentMetadata(
            document_id=doc_id,
            key=key,
            value=value,
        )
        self.db.add(meta)
        await self.db.flush()
        return meta

    # ── Processing Jobs ──────────────────────────────────────

    async def create_processing_job(
        self,
        doc_id: UUID,
        job_type: JobType,
    ) -> ProcessingJob:
        """Create a new processing job for a document."""
        job = ProcessingJob(
            document_id=doc_id,
            job_type=job_type,
            status=JobStatus.PENDING,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def update_job_status(
        self,
        job_id: UUID,
        status: JobStatus,
        result_data: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update a processing job's status and result."""
        values = {"status": status}

        if status == JobStatus.RUNNING:
            values["started_at"] = datetime.now(timezone.utc)
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
            values["completed_at"] = datetime.now(timezone.utc)

        if result_data:
            values["result_data"] = result_data
        if error_message:
            values["error_message"] = error_message

        await self.db.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .values(**values)
        )

    async def get_document_jobs(
        self,
        doc_id: UUID,
    ) -> List[ProcessingJob]:
        """Get all processing jobs for a document."""
        result = await self.db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.document_id == doc_id)
            .order_by(ProcessingJob.created_at)
        )
        return list(result.scalars().all())

    # ── Statistics ───────────────────────────────────────────

    async def get_stats(self) -> dict:
        """Get document processing statistics for the dashboard."""
        total = await self.db.execute(select(func.count(Document.id)))
        by_status = await self.db.execute(
            select(Document.status, func.count(Document.id))
            .group_by(Document.status)
        )
        by_type = await self.db.execute(
            select(Document.file_type, func.count(Document.id))
            .group_by(Document.file_type)
        )

        return {
            "total_documents": total.scalar(),
            "by_status": {
                str(row[0]): row[1] for row in by_status
            },
            "by_type": {
                row[0]: row[1] for row in by_type
            },
        }
