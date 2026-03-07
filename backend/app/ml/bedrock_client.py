"""
AWS Bedrock Client
==================
Unified client for AWS Bedrock model invocations.
Handles text generation, classification, summarization, embeddings, and Q&A.
"""

import json
import re
import boto3
import numpy as np
import logging
from typing import List

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BedrockClient:
    """
    AWS Bedrock client for ML inference.

    Replaces local HuggingFace models when ml_inference_mode="bedrock".
    Uses Claude for text tasks and Titan for embeddings.
    """

    def __init__(self):
        self._runtime = None

    @property
    def runtime(self):
        if self._runtime is None:
            self._runtime = boto3.client(
                "bedrock-runtime",
                region_name=settings.aws_region,
            )
        return self._runtime

    # ── Text Generation ──────────────────────────────────────

    def invoke_model(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> str:
        """Invoke Bedrock text generation model (Claude)."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        })

        response = self.runtime.invoke_model(
            modelId=settings.bedrock_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    # ── Classification ───────────────────────────────────────

    def classify(
        self,
        text: str,
        categories: List[str],
        top_k: int = 5,
    ) -> dict:
        """Zero-shot document classification via Bedrock."""
        categories_str = ", ".join(categories)

        prompt = (
            f"Classify the following document text into exactly one of these categories: "
            f"{categories_str}\n\n"
            f"Document text (first 2000 characters):\n{text[:2000]}\n\n"
            f"Respond in this exact JSON format only, no other text:\n"
            f'{{"label": "category_name", "confidence": 0.95, '
            f'"all_labels": [{{"label": "cat1", "score": 0.95}}, '
            f'{{"label": "cat2", "score": 0.03}}]}}\n\n'
            f"Return the top {top_k} categories with scores summing to ~1.0."
        )

        response_text = self.invoke_model(prompt, max_tokens=500, temperature=0.0)

        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {
                "label": "unknown",
                "confidence": 0.0,
                "all_labels": [{"label": "unknown", "score": 0.0}],
            }

    # ── Summarization ────────────────────────────────────────

    def summarize(self, text: str, max_length: int = 150) -> str:
        """Summarize text using Bedrock."""
        prompt = (
            f"Summarize the following document concisely in approximately "
            f"{max_length} words or less. Capture the key points.\n\n"
            f"Document text:\n{text[:8000]}\n\nSummary:"
        )

        return self.invoke_model(prompt, max_tokens=max_length * 2, temperature=0.1)

    # ── Q&A Generation ───────────────────────────────────────

    def generate_qa_answer(self, question: str, context: str) -> str:
        """Generate a RAG Q&A answer grounded in document context."""
        prompt = (
            "You are an intelligent document assistant. Answer the user's question "
            "based ONLY on the provided context from their documents.\n\n"
            "Rules:\n"
            "1. Only use information from the provided context\n"
            "2. If the answer is not in the context, say "
            '"The documents don\'t contain this information"\n'
            '3. Cite which source(s) you used (e.g., "According to Source 1...")\n'
            "4. Be concise but comprehensive\n"
            "5. If the question is ambiguous, mention what you found and ask for clarification\n\n"
            f"Context from documents:\n{context}\n\n"
            f"Question: {question}\n\nAnswer:"
        )

        return self.invoke_model(prompt, max_tokens=1024, temperature=0.2)

    # ── Embeddings ───────────────────────────────────────────

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text using Titan Embeddings."""
        body = json.dumps({
            "inputText": text[:8000],
            "dimensions": 1024,
            "normalize": True,
        })

        response = self.runtime.invoke_model(
            modelId=settings.bedrock_embed_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        return np.array(result["embedding"], dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts."""
        if not texts:
            return np.array([])

        embeddings = []
        for text in texts:
            embedding = self.embed_text(text)
            embeddings.append(embedding)

        return np.array(embeddings, dtype=np.float32)

    def get_embedding_dimension(self) -> int:
        """Return the embedding dimension for Titan v2."""
        return 1024


# Singleton
_bedrock_client = None


def get_bedrock_client() -> BedrockClient:
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = BedrockClient()
    return _bedrock_client
