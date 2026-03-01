"""
Image Analyzer
==============
Analyzes document images for layout, quality, and visual features.

What this does:
    - Document layout detection (find text regions, tables, figures)
    - Image quality assessment (blur, contrast, resolution)
    - Orientation detection
    - Table detection (useful for structured data extraction)

How it works:
    Uses OpenCV (Computer Vision library) for image processing:
    - Contour detection to find text blocks
    - Line detection for tables
    - Blur estimation using Laplacian variance
    - Histogram analysis for contrast

Industry context:
    - Layout analysis is crucial for understanding document structure
    - Used by Amazon Textract, Google Document AI
    - Helps decide which OCR strategy to use for different regions
"""

import cv2
import numpy as np
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """
    Analyzes document images for structure and quality.

    Usage:
        analyzer = ImageAnalyzer()
        result = analyzer.analyze(image_bytes)
        print(f"Quality: {result['quality_score']}")
        print(f"Regions: {len(result['regions'])}")
    """

    def analyze(self, image_bytes: bytes) -> dict:
        """
        Perform full analysis on a document image.

        Args:
            image_bytes: Raw image file content

        Returns:
            {
                "quality_score": 0.85,
                "quality_details": {
                    "blur_score": 120.5,
                    "is_blurry": False,
                    "contrast": 0.78,
                    "brightness": 0.62,
                    "resolution": {"width": 2480, "height": 3508}
                },
                "regions": [
                    {"type": "text", "bbox": [x, y, w, h]},
                    {"type": "table", "bbox": [x, y, w, h]},
                    {"type": "figure", "bbox": [x, y, w, h]},
                ],
                "has_tables": True,
                "estimated_orientation": 0,
                "page_type": "text_heavy"
            }
        """
        # Load image
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Failed to decode image")

        # Run all analyses
        quality = self._assess_quality(image)
        regions = self._detect_regions(image)
        has_tables = self._detect_tables(image)
        orientation = self._detect_orientation(image)
        page_type = self._classify_page_type(regions)

        # Calculate overall quality score
        quality_score = self._calculate_quality_score(quality)

        return {
            "quality_score": round(quality_score, 2),
            "quality_details": quality,
            "regions": regions,
            "has_tables": has_tables,
            "estimated_orientation": orientation,
            "page_type": page_type,
        }

    # ── Quality Assessment ───────────────────────────────────

    def _assess_quality(self, image: np.ndarray) -> dict:
        """
        Assess image quality for OCR suitability.

        Checks:
        1. Blur (Laplacian variance) — blurry images = bad OCR
        2. Contrast — low contrast = hard to read
        3. Brightness — too dark/bright = problems
        4. Resolution — too low = pixelated text
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = image.shape[:2]

        # Blur detection using Laplacian
        # Higher variance = sharper image
        # Below 100 is generally considered blurry
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Contrast (standard deviation of pixel values)
        contrast = gray.std() / 255.0

        # Brightness (mean pixel value normalized)
        brightness = gray.mean() / 255.0

        return {
            "blur_score": round(float(laplacian_var), 2),
            "is_blurry": laplacian_var < 100,
            "contrast": round(float(contrast), 3),
            "brightness": round(float(brightness), 3),
            "resolution": {"width": w, "height": h},
        }

    def _calculate_quality_score(self, quality: dict) -> float:
        """
        Calculate an overall quality score (0-1).

        Factors:
        - Sharpness (40% weight)
        - Contrast (30% weight)
        - Brightness optimal range (30% weight)
        """
        # Sharpness score (sigmoid-like normalization)
        blur = quality["blur_score"]
        sharpness = min(blur / 200.0, 1.0)

        # Contrast (higher is better, up to a point)
        contrast = min(quality["contrast"] * 2, 1.0)

        # Brightness (optimal around 0.4-0.7)
        brightness = quality["brightness"]
        if 0.3 <= brightness <= 0.8:
            brightness_score = 1.0
        else:
            brightness_score = max(0, 1 - abs(brightness - 0.55) * 3)

        return sharpness * 0.4 + contrast * 0.3 + brightness_score * 0.3

    # ── Region Detection ─────────────────────────────────────

    def _detect_regions(self, image: np.ndarray) -> list:
        """
        Detect text and non-text regions in the document.

        How it works:
        1. Convert to grayscale and threshold
        2. Dilate to merge nearby text into blocks
        3. Find contours (outlines of text blocks)
        4. Filter by size and classify as text/figure

        This is a simplified version of what tools like
        Detectron2 or LayoutParser do with deep learning.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = image.shape[:2]

        # Threshold
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        # Dilate to merge text into blocks
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 5))
        dilated = cv2.dilate(binary, kernel, iterations=3)

        # Find contours
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        regions = []
        min_area = w * h * 0.001  # Ignore tiny regions

        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            area = cw * ch

            if area < min_area:
                continue

            # Classify region by aspect ratio and size
            aspect_ratio = cw / ch if ch > 0 else 0

            if aspect_ratio > 3:
                region_type = "text"  # Wide and short = text line
            elif 0.8 < aspect_ratio < 1.2 and area > w * h * 0.05:
                region_type = "figure"  # Square-ish and large
            else:
                region_type = "text"  # Default to text

            regions.append({
                "type": region_type,
                "bbox": [int(x), int(y), int(cw), int(ch)],
                "area": int(area),
            })

        # Sort by position (top to bottom, left to right)
        regions.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))
        return regions

    # ── Table Detection ──────────────────────────────────────

    def _detect_tables(self, image: np.ndarray) -> bool:
        """
        Detect if the document contains tables.

        How it works:
        1. Find horizontal lines using morphological operations
        2. Find vertical lines similarly
        3. If enough intersecting lines exist, there's probably a table

        This is a heuristic approach. For production, you'd use
        TableTransformer or similar deep learning models.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Threshold
        _, binary = cv2.threshold(
            gray, 200, 255, cv2.THRESH_BINARY_INV
        )

        # Detect horizontal lines
        horizontal_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (w // 4, 1)
        )
        horizontal = cv2.morphologyEx(
            binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2
        )

        # Detect vertical lines
        vertical_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (1, h // 4)
        )
        vertical = cv2.morphologyEx(
            binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2
        )

        # Count lines
        h_lines = cv2.countNonZero(horizontal)
        v_lines = cv2.countNonZero(vertical)

        # If significant lines exist, table is likely present
        threshold = w * h * 0.001
        return h_lines > threshold and v_lines > threshold

    # ── Orientation Detection ────────────────────────────────

    def _detect_orientation(self, image: np.ndarray) -> int:
        """
        Detect document orientation (0, 90, 180, 270 degrees).

        Uses text line detection:
        - Horizontal text lines = 0°
        - Vertical text lines = 90° or 270°
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        # Hough line detection
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

        if lines is None:
            return 0

        # Count line angles
        angles = []
        for line in lines:
            rho, theta = line[0]
            angle_deg = theta * 180 / np.pi
            angles.append(angle_deg)

        if not angles:
            return 0

        # Determine dominant orientation
        mean_angle = np.mean(angles)

        if mean_angle < 45 or mean_angle > 135:
            return 0  # Normal (horizontal text)
        elif 45 <= mean_angle <= 135:
            return 90

        return 0

    # ── Page Type Classification ─────────────────────────────

    def _classify_page_type(self, regions: list) -> str:
        """
        Classify the page as text_heavy, mixed, or image_heavy.
        """
        if not regions:
            return "empty"

        text_count = sum(1 for r in regions if r["type"] == "text")
        figure_count = sum(1 for r in regions if r["type"] == "figure")
        total = text_count + figure_count

        if total == 0:
            return "empty"

        text_ratio = text_count / total

        if text_ratio > 0.8:
            return "text_heavy"
        elif text_ratio < 0.3:
            return "image_heavy"
        else:
            return "mixed"
