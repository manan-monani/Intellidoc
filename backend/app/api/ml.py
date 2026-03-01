"""
ML Processing API Routes
========================
Endpoints for running ML tasks on documents.

Endpoints:
    POST /api/ml/{document_id}/process    — Run full processing pipeline
    POST /api/ml/{document_id}/ocr        — Run OCR only
    POST /api/ml/{document_id}/classify   — Classify document
    POST /api/ml/{document_id}/ner        — Extract named entities
    POST /api/ml/{document_id}/summarize  — Generate summary
    POST /api/ml/{document_id}/analyze    — Analyze image quality/layout
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.s3_service import get_s3_service
from app.services.document_service import DocumentService
from app.models.document import DocumentStatus, JobType, JobStatus
from app.schemas.document import (
    OCRResult, ClassificationResult, NERResult, SummaryResult,
)
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ml", tags=["ML Processing"])

# ── Lazy-loaded ML models (singleton pattern) ────────────────
_ocr_engine = None
_classifier = None
_ner_extractor = None
_summarizer = None
_image_analyzer = None


def get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from app.ml.ocr import OCREngine
        _ocr_engine = OCREngine()
    return _ocr_engine


def get_classifier():
    global _classifier
    if _classifier is None:
        from app.ml.classifier import DocumentClassifier
        _classifier = DocumentClassifier()
        _classifier.load_model()
    return _classifier


def get_ner():
    global _ner_extractor
    if _ner_extractor is None:
        from app.ml.ner import NERExtractor
        _ner_extractor = NERExtractor()
        _ner_extractor.load_model()
    return _ner_extractor


def get_summarizer():
    global _summarizer
    if _summarizer is None:
        from app.ml.summarizer import TextSummarizer
        _summarizer = TextSummarizer()
        _summarizer.load_model()
    return _summarizer


def get_image_analyzer():
    global _image_analyzer
    if _image_analyzer is None:
        from app.ml.image_analyzer import ImageAnalyzer
        _image_analyzer = ImageAnalyzer()
    return _image_analyzer


# ── Helper ───────────────────────────────────────────────────

async def _get_document_or_404(doc_id: UUID, db: AsyncSession):
    """Get a document or raise 404."""
    service = DocumentService(db)
    doc = await service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc, service


# ── Full Pipeline ────────────────────────────────────────────

@router.post("/{document_id}/process")
async def process_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Run the full ML processing pipeline on a document.

    Pipeline: OCR → Classification → NER → Summarization

    This runs in the background so the API returns immediately.
    Use GET /api/documents/{id}/status to track progress.
    """
    doc, service = await _get_document_or_404(document_id, db)

    # Update status to processing
    await service.update_status(document_id, DocumentStatus.PROCESSING)

    # Create job records for each step
    for job_type in [JobType.OCR, JobType.CLASSIFICATION, JobType.NER, JobType.SUMMARIZATION]:
        await service.create_processing_job(document_id, job_type)

    return {
        "message": "Processing started",
        "document_id": str(document_id),
        "status": "processing",
        "pipeline": ["ocr", "classification", "ner", "summarization"],
    }


# ── OCR ──────────────────────────────────────────────────────

@router.post("/{document_id}/ocr", response_model=OCRResult)
async def run_ocr(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Extract text from a document using OCR.

    Supports: PDF, PNG, JPG, JPEG, TIFF

    What happens:
    1. Download the file from S3
    2. Run OCR (with image preprocessing)
    3. Save extracted text to the database
    4. Return the result
    """
    doc, service = await _get_document_or_404(document_id, db)

    # Download file from S3
    s3 = get_s3_service()
    try:
        file_bytes = s3.download_file(doc.s3_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {e}")

    # Run OCR
    ocr = get_ocr()
    try:
        if doc.file_type == "pdf":
            result = ocr.extract_text_from_pdf(file_bytes)
        else:
            result = ocr.extract_text_from_image(file_bytes)
    except Exception as e:
        logger.error(f"OCR failed for {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e}")

    # Save to database
    await service.update_extracted_text(document_id, result["text"])
    await service.add_metadata(document_id, "page_count", str(result["page_count"]))
    await service.add_metadata(document_id, "ocr_confidence", str(result["confidence"]))

    return OCRResult(
        text=result["text"],
        confidence=result["confidence"],
        page_count=result["page_count"],
    )


# ── Classification ───────────────────────────────────────────

@router.post("/{document_id}/classify", response_model=ClassificationResult)
async def classify_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Classify the document type (invoice, report, resume, etc.).

    Requires: Document must have extracted text (run OCR first).
    """
    doc, service = await _get_document_or_404(document_id, db)

    if not doc.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No extracted text. Run OCR first: POST /api/ml/{id}/ocr",
        )

    classifier = get_classifier()
    result = classifier.classify(doc.extracted_text)

    # Save to database
    await service.update_classification(
        document_id,
        result["label"],
        str(result["confidence"]),
    )

    return ClassificationResult(
        label=result["label"],
        confidence=result["confidence"],
        all_labels=result["all_labels"],
    )


# ── NER ──────────────────────────────────────────────────────

@router.post("/{document_id}/ner", response_model=NERResult)
async def extract_entities(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Extract named entities (people, orgs, locations) from the document.

    Requires: Document must have extracted text (run OCR first).
    """
    doc, service = await _get_document_or_404(document_id, db)

    if not doc.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No extracted text. Run OCR first.",
        )

    ner = get_ner()
    entities = ner.extract(doc.extracted_text)

    # Save grouped entities as metadata
    grouped = ner.extract_grouped(doc.extracted_text)
    for label, values in grouped.items():
        await service.add_metadata(
            document_id,
            f"entities_{label}",
            ", ".join(values),
        )

    return NERResult(entities=entities)


# ── Summarization ────────────────────────────────────────────

@router.post("/{document_id}/summarize", response_model=SummaryResult)
async def summarize_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an AI summary of the document.

    Requires: Document must have extracted text (run OCR first).
    """
    doc, service = await _get_document_or_404(document_id, db)

    if not doc.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No extracted text. Run OCR first.",
        )

    summarizer = get_summarizer()
    result = summarizer.summarize(doc.extracted_text)

    # Save summary to database
    await service.update_summary(document_id, result["summary"])

    return SummaryResult(
        summary=result["summary"],
        original_length=result["original_length"],
        summary_length=result["summary_length"],
    )


# ── Image Analysis ───────────────────────────────────────────

@router.post("/{document_id}/analyze")
async def analyze_image(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze the document image for quality, layout, and tables.

    Works on: PNG, JPG, JPEG, TIFF
    For PDFs, converts first page to image.
    """
    doc, service = await _get_document_or_404(document_id, db)

    s3 = get_s3_service()
    file_bytes = s3.download_file(doc.s3_key)

    # Convert PDF first page to image if needed
    if doc.file_type == "pdf":
        from pdf2image import convert_from_bytes
        import io
        images = convert_from_bytes(file_bytes, dpi=200, first_page=1, last_page=1)
        if images:
            import numpy as np
            import cv2
            img_array = np.array(images[0])
            _, buffer = cv2.imencode(".png", cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR))
            file_bytes = buffer.tobytes()

    analyzer = get_image_analyzer()
    result = analyzer.analyze(file_bytes)

    # Save analysis results as metadata
    await service.add_metadata(document_id, "quality_score", str(result["quality_score"]))
    await service.add_metadata(document_id, "has_tables", str(result["has_tables"]))
    await service.add_metadata(document_id, "page_type", result["page_type"])

    return result
