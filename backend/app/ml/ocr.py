"""
OCR Engine
==========
Extracts text from documents using Tesseract OCR.

What is OCR?
    Optical Character Recognition — converts images of text into
    actual text strings. Think of it as teaching a computer to read.

How this works:
    1. PDF → Convert each page to an image using pdf2image
    2. Image preprocessing → Improve quality for better OCR accuracy:
       - Convert to grayscale
       - Apply adaptive thresholding (separate text from background)
       - Denoise (remove speckles)
       - Deskew (straighten rotated text)
    3. Tesseract → Run OCR on each processed page
    4. Combine → Merge text from all pages

Industry context:
    - AWS Textract is the commercial equivalent
    - Google Vision API is another option
    - Tesseract is the open-source gold standard
    - Production systems often combine multiple OCR engines
"""

import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
import cv2
import numpy as np
import logging
from typing import Optional
import io

logger = logging.getLogger(__name__)


class OCREngine:
    """
    Extracts text from PDFs and images using Tesseract.

    Usage:
        ocr = OCREngine()
        result = ocr.extract_text_from_pdf(pdf_bytes)
        print(result["text"])
        print(f"Confidence: {result['confidence']}%")
    """

    def __init__(self, lang: str = "eng"):
        """
        Initialize OCR engine.

        Args:
            lang: Tesseract language pack (e.g., "eng", "hin", "eng+hin")
        """
        self.lang = lang

    # ── PDF Processing ───────────────────────────────────────

    def extract_text_from_pdf(
        self,
        pdf_bytes: bytes,
        dpi: int = 300,
    ) -> dict:
        """
        Extract text from a PDF file.

        Args:
            pdf_bytes: Raw PDF file content
            dpi: Resolution for PDF-to-image conversion
                 300 = good balance of quality and speed
                 Higher = better quality but slower

        Returns:
            {
                "text": "full extracted text...",
                "confidence": 87.5,
                "page_count": 3,
                "pages": [
                    {"page": 1, "text": "...", "confidence": 92.1},
                    ...
                ]
            }
        """
        # Convert PDF pages to images
        try:
            images = convert_from_bytes(pdf_bytes, dpi=dpi)
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            raise ValueError(f"Failed to convert PDF to images: {e}")

        pages = []
        all_text = []
        total_confidence = 0

        for i, image in enumerate(images):
            # Convert PIL Image to OpenCV format for preprocessing
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            # Preprocess the image for better OCR
            processed = self._preprocess_image(cv_image)

            # Run OCR
            text = pytesseract.image_to_string(processed, lang=self.lang)
            data = pytesseract.image_to_data(
                processed, lang=self.lang, output_type=pytesseract.Output.DICT
            )

            # Calculate confidence (average of non-empty word confidences)
            confidences = [
                int(c) for c in data["conf"] if int(c) > 0
            ]
            page_confidence = (
                sum(confidences) / len(confidences) if confidences else 0
            )

            pages.append({
                "page": i + 1,
                "text": text.strip(),
                "confidence": round(page_confidence, 2),
            })
            all_text.append(text.strip())
            total_confidence += page_confidence

        avg_confidence = (
            total_confidence / len(pages) if pages else 0
        )

        return {
            "text": "\n\n".join(all_text),
            "confidence": round(avg_confidence, 2),
            "page_count": len(pages),
            "pages": pages,
        }

    # ── Image Processing ─────────────────────────────────────

    def extract_text_from_image(
        self,
        image_bytes: bytes,
    ) -> dict:
        """
        Extract text from a single image file (PNG, JPG, etc.).

        Args:
            image_bytes: Raw image file content

        Returns:
            Same format as extract_text_from_pdf but with 1 page
        """
        # Load image
        nparr = np.frombuffer(image_bytes, np.uint8)
        cv_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if cv_image is None:
            raise ValueError("Failed to decode image")

        # Preprocess
        processed = self._preprocess_image(cv_image)

        # OCR
        text = pytesseract.image_to_string(processed, lang=self.lang)
        data = pytesseract.image_to_data(
            processed, lang=self.lang, output_type=pytesseract.Output.DICT
        )

        confidences = [int(c) for c in data["conf"] if int(c) > 0]
        confidence = (
            sum(confidences) / len(confidences) if confidences else 0
        )

        return {
            "text": text.strip(),
            "confidence": round(confidence, 2),
            "page_count": 1,
            "pages": [{
                "page": 1,
                "text": text.strip(),
                "confidence": round(confidence, 2),
            }],
        }

    # ── Image Preprocessing ──────────────────────────────────

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess an image to improve OCR accuracy.

        Pipeline:
        1. Grayscale → Remove color info (OCR only needs light/dark)
        2. Denoise → Remove small speckles that confuse OCR
        3. Adaptive threshold → Convert to pure black/white
           - "Adaptive" means it adjusts for uneven lighting
        4. Deskew → Straighten rotated text

        Why each step matters:
        - Without preprocessing, OCR accuracy can drop 20-30%
        - This is a standard industry preprocessing pipeline
        """
        # Step 1: Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Step 2: Denoise (removes small noise while keeping edges)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # Step 3: Adaptive thresholding
        # ADAPTIVE_THRESH_GAUSSIAN_C: uses Gaussian-weighted sum of
        # neighborhood values. Better for documents with shadows.
        binary = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,  # Block size (neighborhood)
            2,   # Constant subtracted from mean
        )

        # Step 4: Deskew (straighten rotated text)
        binary = self._deskew(binary)

        return binary

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Correct image rotation / skew.

        How it works:
        1. Find all non-zero pixels (text pixels)
        2. Compute the minimum area bounding rectangle
        3. Get the rotation angle
        4. Rotate the image to straighten it
        """
        coords = np.column_stack(np.where(image > 0))

        if len(coords) < 10:
            return image  # Not enough text to determine skew

        angle = cv2.minAreaRect(coords)[-1]

        # Adjust angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Only correct small skews (< 15 degrees)
        if abs(angle) > 15:
            return image

        # Rotate
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, matrix, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

        return rotated
