"""
Embedding Generator
==================
Converts text into numerical vectors (embeddings) for semantic search.

What are embeddings?
    Embeddings are dense numerical representations of text.
    Think of them as coordinates in a high-dimensional space where
    similar texts are close together.

    Example:
    - "cat" → [0.2, 0.8, 0.1, ...]
    - "kitten" → [0.21, 0.79, 0.12, ...]  (very close!)
    - "car" → [0.9, 0.1, 0.7, ...]  (far away)

Why embeddings for RAG?
    Traditional keyword search: "What is AI?" won't find "artificial intelligence"
    Semantic search with embeddings: These are close in vector space!

    1. Convert all document chunks to embeddings
    2. Convert the user's question to an embedding
    3. Find chunks whose embeddings are closest to the question
    4. Those chunks are the most relevant context for the LLM

Model used: all-MiniLM-L6-v2
    - Small (80MB) but effective
    - Produces 384-dimensional vectors
    - Trained on 1B+ sentence pairs
    - Good balance of speed and quality
    - Industry standard for lightweight embeddings

Industry context:
    - OpenAI ada-002 is the most popular commercial option
    - Cohere embed is another commercial alternative
    - For production, you'd use GPU-accelerated batch embedding
"""

from sentence_transformers import SentenceTransformer
import numpy as np
import logging
from typing import List, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingGenerator:
    """
    Generates embeddings from text using Sentence-Transformers.

    Usage:
        embedder = EmbeddingGenerator()
        vector = embedder.embed_text("Hello world")
        vectors = embedder.embed_batch(["text1", "text2", "text3"])
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Args:
            model_name: Sentence-Transformers model name.
                       Common choices:
                       - "all-MiniLM-L6-v2": Fast, good quality (384-dim)
                       - "all-mpnet-base-v2": Better quality, slower (768-dim)
                       - "paraphrase-multilingual-MiniLM-L12-v2": Multilingual
        """
        self.model_name = model_name
        self.model = None
        self.embedding_dim = None

    def load_model(self):
        """Load the embedding model into memory."""
        if self.model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(
                f"Embedding model loaded. Dimension: {self.embedding_dim}"
            )

    def embed_text(self, text: str) -> np.ndarray:
        """
        Convert a single text to an embedding vector.

        Supports two modes:
        - "local": Uses sentence-transformers (384-dim)
        - "bedrock": Uses Amazon Titan Embeddings v2 (1024-dim)
        """
        if settings.embedding_provider == "bedrock":
            from app.ml.bedrock_client import get_bedrock_client
            return get_bedrock_client().embed_text(text)

        self.load_model()
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embedding

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Convert multiple texts to embeddings efficiently.

        Supports two modes:
        - "local": Uses sentence-transformers batch encoding
        - "bedrock": Uses Amazon Titan Embeddings v2
        """
        if not texts:
            return np.array([])

        if settings.embedding_provider == "bedrock":
            from app.ml.bedrock_client import get_bedrock_client
            return get_bedrock_client().embed_batch(texts)

        self.load_model()
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
        )
        return embeddings

    def get_dimension(self) -> int:
        """Get the embedding dimension."""
        if settings.embedding_provider == "bedrock":
            from app.ml.bedrock_client import get_bedrock_client
            return get_bedrock_client().get_embedding_dimension()
        self.load_model()
        return self.embedding_dim

    def compute_similarity(
        self,
        text1: str,
        text2: str,
    ) -> float:
        """
        Compute semantic similarity between two texts.

        Returns:
            Score between 0 (unrelated) and 1 (identical meaning)

        Uses cosine similarity:
            similarity = dot(A, B) / (|A| * |B|)
            Since we normalize embeddings, this is just dot(A, B)
        """
        emb1 = self.embed_text(text1)
        emb2 = self.embed_text(text2)
        return float(np.dot(emb1, emb2))
