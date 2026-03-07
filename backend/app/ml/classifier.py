"""
Document Classifier
===================
Classifies documents into categories using a pre-trained BERT model.

What is Document Classification?
    Given a piece of text, predict what TYPE of document it is.
    Examples: invoice, resume, legal contract, report, letter, etc.

How it works (at a high level):
    1. Take the extracted text from OCR
    2. Tokenize it (convert text to numbers that BERT understands)
    3. Feed through the BERT model
    4. Get probability scores for each category
    5. Return the top prediction

BERT (Bidirectional Encoder Representations from Transformers):
    - A transformer model pre-trained on massive text data
    - "Bidirectional" = reads text both left-to-right AND right-to-left
    - We use a fine-tuned version that's been trained on document types
    - In production, you'd fine-tune on YOUR company's document types

Industry context:
    - This is the core of Intelligent Document Processing (IDP)
    - Companies like ABBYY, Kofax, and AWS Textract do this
    - The model here uses zero-shot classification (no custom training needed)
"""

from transformers import pipeline
import logging
from typing import List, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Default document categories
DEFAULT_CATEGORIES = [
    "invoice",
    "resume",
    "report",
    "legal_contract",
    "letter",
    "scientific_paper",
    "email",
    "news_article",
    "receipt",
    "form",
    "memo",
    "presentation",
    "technical_documentation",
    "financial_statement",
]


class DocumentClassifier:
    """
    Classifies documents into predefined categories using BERT.

    Uses zero-shot classification — no custom training needed!
    The model understands natural language labels and matches them.

    Usage:
        classifier = DocumentClassifier()
        classifier.load_model()
        result = classifier.classify("text of the document...")
        print(f"Type: {result['label']}, Confidence: {result['confidence']}")
    """

    def __init__(self, categories: Optional[List[str]] = None):
        """
        Args:
            categories: List of document types to classify into.
                       Uses DEFAULT_CATEGORIES if not specified.
        """
        self.categories = categories or DEFAULT_CATEGORIES
        self.classifier = None
        self._model_name = "facebook/bart-large-mnli"

    def load_model(self):
        """
        Load the classification model into memory.

        This is called lazily (on first use) rather than at startup
        because the model is ~1.6GB and takes a few seconds to load.

        The model used is facebook/bart-large-mnli:
        - BART = Bidirectional and Auto-Regressive Transformers
        - MNLI = Multi-genre Natural Language Inference
        - Zero-shot = can classify without training examples
        """
        if self.classifier is None:
            logger.info(f"Loading classifier model: {self._model_name}")
            self.classifier = pipeline(
                "zero-shot-classification",
                model=self._model_name,
                device=-1,  # -1 = CPU, 0 = GPU
            )
            logger.info("Classifier model loaded successfully")

    def classify(
        self,
        text: str,
        top_k: int = 5,
        max_length: int = 1024,
    ) -> dict:
        """
        Classify a document's text.

        Supports two modes:
        - "local": Uses HuggingFace facebook/bart-large-mnli
        - "bedrock": Uses AWS Bedrock Claude for zero-shot classification
        """
        if settings.ml_inference_mode == "bedrock":
            return self._classify_bedrock(text, top_k)
        return self._classify_local(text, top_k, max_length)

    def _classify_bedrock(self, text: str, top_k: int) -> dict:
        """Classify using AWS Bedrock."""
        from app.ml.bedrock_client import get_bedrock_client

        client = get_bedrock_client()
        return client.classify(text, self.categories, top_k)

    def _classify_local(self, text: str, top_k: int, max_length: int) -> dict:
        """Classify using local HuggingFace model."""
        self.load_model()

        truncated_text = text[:max_length]

        result = self.classifier(
            truncated_text,
            candidate_labels=self.categories,
            multi_label=False,
        )

        all_labels = [
            {"label": label, "score": round(score, 4)}
            for label, score in zip(result["labels"][:top_k], result["scores"][:top_k])
        ]

        return {
            "label": result["labels"][0],
            "confidence": round(result["scores"][0], 4),
            "all_labels": all_labels,
        }
