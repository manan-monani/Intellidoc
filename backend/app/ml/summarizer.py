"""
Text Summarizer
===============
Generates concise summaries of long documents using BART.

What is Text Summarization?
    Takes a long document and produces a shorter version that
    captures the key points. Two approaches:
    - Extractive: Select important sentences from the original
    - Abstractive: Generate new sentences (what we do here)

How BART works for summarization:
    BART = Bidirectional and Auto-Regressive Transformers

    1. Encoder reads the entire document and creates a representation
    2. Decoder generates the summary word by word
    3. It was trained on millions of (article, summary) pairs
    4. The model learns to identify key information and rephrase it

    Think of it like a human who reads an article and then writes
    a summary in their own words — that's abstractive summarization.

Industry context:
    - Used in news aggregation, legal document review, medical records
    - facebook/bart-large-cnn is trained on CNN/DailyMail news articles
    - For domain-specific docs, you'd fine-tune on your own data
"""

from transformers import pipeline
import logging
from typing import Optional
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TextSummarizer:
    """
    Summarizes text using the BART model.

    Usage:
        summarizer = TextSummarizer()
        summarizer.load_model()
        result = summarizer.summarize("Long document text here...")
        print(result["summary"])
    """

    def __init__(self):
        self.summarizer = None
        self._model_name = "facebook/bart-large-cnn"

    def load_model(self):
        """
        Load the summarization model.

        Model: facebook/bart-large-cnn
        - Fine-tuned BART for text summarization
        - Trained on CNN/DailyMail news dataset
        - Input limit: ~1024 tokens (~800 words)
        - Generates summaries of 50-150 words
        """
        if self.summarizer is None:
            logger.info(f"Loading summarizer: {self._model_name}")
            self.summarizer = pipeline(
                "summarization",
                model=self._model_name,
                device=-1,  # CPU
            )
            logger.info("Summarizer loaded successfully")

    def summarize(
        self,
        text: str,
        max_length: int = 150,
        min_length: int = 50,
        max_input_length: int = 1024,
    ) -> dict:
        """
        Generate a summary of the input text.

        Supports two modes:
        - "local": Uses HuggingFace facebook/bart-large-cnn
        - "bedrock": Uses AWS Bedrock Claude for summarization
        """
        if settings.ml_inference_mode == "bedrock":
            return self._summarize_bedrock(text, max_length)
        return self._summarize_local(text, max_length, min_length, max_input_length)

    def _summarize_bedrock(self, text: str, max_length: int) -> dict:
        """Summarize using AWS Bedrock."""
        from app.ml.bedrock_client import get_bedrock_client

        original_length = len(text)
        if original_length < 100:
            return {
                "summary": text,
                "original_length": original_length,
                "summary_length": original_length,
                "compression_ratio": 1.0,
            }

        client = get_bedrock_client()
        summary = client.summarize(text, max_length)

        return {
            "summary": summary,
            "original_length": original_length,
            "summary_length": len(summary),
            "compression_ratio": round(len(summary) / original_length, 4),
        }

    def _summarize_local(
        self,
        text: str,
        max_length: int,
        min_length: int,
        max_input_length: int,
    ) -> dict:
        """Summarize using local HuggingFace model."""
        self.load_model()

        original_length = len(text)

        if original_length < 100:
            return {
                "summary": text,
                "original_length": original_length,
                "summary_length": original_length,
                "compression_ratio": 1.0,
            }

        if len(text.split()) > max_input_length:
            summary = self._summarize_long_text(
                text, max_length, min_length, max_input_length
            )
        else:
            result = self.summarizer(
                text,
                max_length=max_length,
                min_length=min_length,
                do_sample=False,
            )
            summary = result[0]["summary_text"]

        return {
            "summary": summary,
            "original_length": original_length,
            "summary_length": len(summary),
            "compression_ratio": round(len(summary) / original_length, 4),
        }

    def _summarize_long_text(
        self,
        text: str,
        max_length: int,
        min_length: int,
        max_input_length: int,
    ) -> str:
        """
        Summarize text that's too long for the model in one pass.

        Strategy (hierarchical summarization):
        1. Split text into chunks that fit the model
        2. Summarize each chunk individually
        3. Combine chunk summaries
        4. If still too long, summarize the combined summaries

        This is how production systems handle long documents.
        """
        words = text.split()
        chunks = []
        chunk_size = max_input_length - 50  # Leave some margin

        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)

        # Summarize each chunk
        chunk_summaries = []
        for chunk in chunks:
            try:
                result = self.summarizer(
                    chunk,
                    max_length=max_length,
                    min_length=min(min_length, len(chunk.split()) // 2),
                    do_sample=False,
                )
                chunk_summaries.append(result[0]["summary_text"])
            except Exception as e:
                logger.warning(f"Failed to summarize chunk: {e}")
                continue

        # Combine summaries
        combined = " ".join(chunk_summaries)

        # If combined is still long, summarize again
        if len(combined.split()) > max_input_length:
            try:
                result = self.summarizer(
                    combined,
                    max_length=max_length,
                    min_length=min_length,
                    do_sample=False,
                )
                return result[0]["summary_text"]
            except Exception:
                pass

        return combined
