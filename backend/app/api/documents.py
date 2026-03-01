"""
Document API Routes
===================
REST endpoints for document upload, listing, and management.

Endpoints:
    POST   /api/documents/upload    — Upload a new document
    GET    /api/documents/          — List documents (paginated)
    GET    /api/documents/{id}      — Get document details
    GET    /api/documents/{id}/status — Get processing status
    DELETE /api/documents/{id}      — Delete a document
    GET    /api/documents/stats     — Get dashboard statistics
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.s3_service import get_s3_service
from app.services.document_service import DocumentService
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentCreate,
    DocumentProcessingStatus,
    ProcessingJobResponse,
)
from app.config import get_settings
from uuid import UUID
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/documents", tags=["Documents"])


# ── Upload ───────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document to S3 and create a database record.

    Flow:
    1. Validate file type and size
    2. Upload to S3
    3. Create document record in PostgreSQL
    4. Return the document details

    The document starts with status='uploaded' and can then be
    processed via the /api/ml/ endpoints.
    """
    # Validate file extension
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {settings.allowed_extensions_list}",
        )

    # Validate file size
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max: {settings.max_upload_size_mb}MB",
        )

    # Reset file position for upload
    await file.seek(0)

    # Upload to S3
    s3 = get_s3_service()
    try:
        s3_key = s3.upload_file(
            file_obj=file.file,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")

    # Create database record
    service = DocumentService(db)
    doc = await service.create_document(
        DocumentCreate(
            filename=file.filename,
            s3_key=s3_key,
            file_type=ext,
            file_size=len(content),
        )
    )

    return doc


# ── List ─────────────────────────────────────────────────────

@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all documents with pagination.

    Supports filtering by status: uploaded, processing, processed, indexed, failed
    """
    service = DocumentService(db)
    documents, total = await service.list_documents(
        page=page,
        page_size=page_size,
        status=status,
    )

    return DocumentListResponse(
        documents=documents,
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Get Details ──────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a specific document."""
    service = DocumentService(db)
    doc = await service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ── Processing Status ────────────────────────────────────────

@router.get("/{document_id}/status", response_model=DocumentProcessingStatus)
async def get_processing_status(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the processing status of a document with all job details.

    Shows the status of each ML task: OCR, classification, NER, etc.
    """
    service = DocumentService(db)
    doc = await service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    jobs = await service.get_document_jobs(document_id)

    return DocumentProcessingStatus(
        document_id=doc.id,
        document_status=doc.status.value,
        jobs=[ProcessingJobResponse.model_validate(job) for job in jobs],
    )


# ── Download URL ─────────────────────────────────────────────

@router.get("/{document_id}/download")
async def get_download_url(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a temporary download URL for the document.

    Returns a presigned S3 URL valid for 1 hour.
    The browser can use this URL directly — no auth needed.
    """
    service = DocumentService(db)
    doc = await service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    s3 = get_s3_service()
    url = s3.generate_presigned_url(doc.s3_key)

    return {"download_url": url, "filename": doc.filename}


# ── Delete ───────────────────────────────────────────────────

@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a document from both S3 and the database.

    This cascades to delete all metadata and processing jobs.
    """
    service = DocumentService(db)
    doc = await service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from S3
    s3 = get_s3_service()
    s3.delete_file(doc.s3_key)

    # Delete from database (cascades to metadata, jobs)
    await service.delete_document(document_id)


# ── Statistics ───────────────────────────────────────────────

@router.get("/stats/overview")
async def get_statistics(
    db: AsyncSession = Depends(get_db),
):
    """
    Get document processing statistics for the dashboard.

    Returns counts by status and file type.
    """
    service = DocumentService(db)
    return await service.get_stats()
