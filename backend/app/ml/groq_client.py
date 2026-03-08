"""
Groq LLM Client
================
Free LLM inference via Groq API (Llama 3.3 70B).
Replaces AWS Bedrock for classification, summarization, and Q&A.

Groq provides free API access with generous rate limits:
- Model: llama-3.3-70b-versatile (fast, high quality)
- Free tier: 30 RPM, 14,400 RPD, 6,000 TPM
"""

import json
import re
import httpx
import logging
from typing import List

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqClient:
    """
    Groq-based LLM client for classification, summarization, and Q&A.
    Uses the OpenAI-compatible API endpoint.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def invoke_model(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        system_prompt: str = "",
    ) -> str:
        """Send a chat completion request to Groq."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.post(
            GROQ_API_URL,
            json={
                "model": settings.groq_model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]

    # ── Classification ───────────────────────────────────────

    def classify(
        self,
        text: str,
        categories: List[str],
        top_k: int = 5,
    ) -> dict:
        """Zero-shot document classification via Groq."""
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
        """Summarize text using Groq."""
        prompt = (
            f"Summarize the following document concisely in approximately "
            f"{max_length} words or less. Capture the key points.\n\n"
            f"Document text:\n{text[:8000]}\n\nSummary:"
        )

        return self.invoke_model(prompt, max_tokens=max_length * 2, temperature=0.1)

    # ── Q&A Generation ───────────────────────────────────────

    def generate_qa_answer(self, question: str, context: str) -> str:
        """Generate a RAG Q&A answer grounded in document context."""
        system = (
            "You are an intelligent document assistant. Answer the user's question "
            "based ONLY on the provided context from their documents.\n\n"
            "Rules:\n"
            "1. Only use information from the provided context\n"
            "2. If the answer is not in the context, say "
            '"The documents don\'t contain this information"\n'
            '3. Cite which source(s) you used (e.g., "According to Source 1...")\n'
            "4. Be concise but comprehensive\n"
            "5. If the question is ambiguous, mention what you found and ask for clarification"
        )

        prompt = (
            f"Context from documents:\n{context}\n\n"
            f"Question: {question}\n\nAnswer:"
        )

        return self.invoke_model(
            prompt, max_tokens=1024, temperature=0.2, system_prompt=system
        )


# Singleton
_groq_client = None


def get_groq_client() -> GroqClient:
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client
