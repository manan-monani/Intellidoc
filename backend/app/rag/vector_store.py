"""
FAISS Vector Store
==================
Stores and searches document embeddings using FAISS.

What is FAISS?
    Facebook AI Similarity Search — a library for efficient
    similarity search in large collections of vectors.

    Think of it as a specialized database for embeddings:
    - Regular DB: "Find rows WHERE name = 'John'"
    - Vector DB: "Find vectors most SIMILAR to this query vector"

How FAISS works:
    1. Build an index of all document chunk embeddings
    2. When a query comes in, convert it to an embedding
    3. FAISS finds the k nearest neighbors (most similar chunks)
    4. Uses optimized algorithms (not brute force) for speed

    With 1 million vectors, brute force takes seconds.
    FAISS can do it in milliseconds using techniques like:
    - IVF (Inverted File Index): Clusters vectors, only searches relevant clusters
    - PQ (Product Quantization): Compresses vectors for memory efficiency
    - HNSW (Hierarchical Navigable Small World): Graph-based search

    For our scale (<100K vectors), flat index (exact search) is fine.

Industry context:
    - Pinecone, Weaviate, Milvus are managed vector databases
    - FAISS is the most popular open-source option
    - Used by companies like Meta, Spotify, and many startups
    - The JD specifically mentions FAISS as a bonus skill!
"""

import faiss
import numpy as np
import json
import os
import logging
from typing import List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """
    Manages FAISS indices for document chunk embeddings.

    Usage:
        store = FAISSVectorStore(dimension=384)
        store.add_vectors(embeddings, metadata_list)
        results = store.search(query_embedding, top_k=5)
        store.save("./faiss_index")
        store.load("./faiss_index")
    """

    def __init__(self, dimension: int = 384):
        """
        Args:
            dimension: Embedding vector dimension.
                      384 for all-MiniLM-L6-v2
                      768 for all-mpnet-base-v2
        """
        self.dimension = dimension
        self.index = None
        self.metadata: List[dict] = []  # Metadata for each vector
        self._initialize_index()

    def _initialize_index(self):
        """
        Create a new FAISS index.

        We use IndexFlatIP (Inner Product) because:
        - Our embeddings are normalized (unit length)
        - Inner product of normalized vectors = cosine similarity
        - Cosine similarity is the standard for text similarity

        For larger datasets (>1M vectors), you'd use:
        - IndexIVFFlat: Faster but approximate
        - IndexIVFPQ: Memory efficient but approximate
        """
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []
        logger.info(f"Initialized FAISS index (dim={self.dimension})")

    def add_vectors(
        self,
        embeddings: np.ndarray,
        metadata_list: List[dict],
    ) -> int:
        """
        Add vectors to the index.

        Args:
            embeddings: NumPy array of shape (n, dimension)
            metadata_list: List of metadata dicts, one per vector.
                          Must match the number of embeddings.

        Returns:
            Total number of vectors in the index

        What happens:
            1. The embeddings are added to the FAISS index
            2. The metadata is stored in a parallel list
            3. When we search, we use the index position to look up metadata
        """
        if len(embeddings) != len(metadata_list):
            raise ValueError(
                f"Mismatch: {len(embeddings)} embeddings vs "
                f"{len(metadata_list)} metadata entries"
            )

        # Ensure correct shape and type
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        embeddings = embeddings.astype(np.float32)

        # Add to FAISS index
        self.index.add(embeddings)
        self.metadata.extend(metadata_list)

        logger.info(
            f"Added {len(embeddings)} vectors. "
            f"Total: {self.index.ntotal}"
        )
        return self.index.ntotal

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
    ) -> List[dict]:
        """
        Search for the most similar vectors.

        Args:
            query_embedding: Query vector of shape (dimension,)
            top_k: Number of results to return

        Returns:
            List of result dicts:
            [
                {
                    "score": 0.89,
                    "metadata": {
                        "document_id": "uuid",
                        "chunk_text": "relevant text...",
                        "chunk_index": 3,
                    }
                }
            ]

        How the search works:
            1. Compare query against ALL vectors in the index
            2. Compute similarity score (inner product ≈ cosine similarity)
            3. Return the top_k highest-scoring results
            4. Look up metadata for each result
        """
        if self.index.ntotal == 0:
            return []

        # Ensure correct shape
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        query_embedding = query_embedding.astype(np.float32)

        # Clamp top_k to available vectors
        k = min(top_k, self.index.ntotal)

        # Search FAISS index
        scores, indices = self.index.search(query_embedding, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for missing results
                continue

            results.append({
                "score": round(float(score), 4),
                "metadata": self.metadata[idx],
            })

        return results

    def search_with_filter(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        """
        Search with optional document ID filtering.

        Fetches more results than needed, then filters by document_id.
        """
        if document_ids is None:
            return self.search(query_embedding, top_k)

        # Fetch extra results to account for filtering
        all_results = self.search(query_embedding, top_k * 3)

        filtered = [
            r for r in all_results
            if r["metadata"].get("document_id") in document_ids
        ]

        return filtered[:top_k]

    # ── Persistence ──────────────────────────────────────────

    def save(self, directory: str):
        """
        Save the FAISS index and metadata to disk.

        Saves two files:
        - index.faiss: The FAISS index (binary)
        - metadata.json: The metadata list (JSON)
        """
        Path(directory).mkdir(parents=True, exist_ok=True)

        index_path = os.path.join(directory, "index.faiss")
        metadata_path = os.path.join(directory, "metadata.json")

        faiss.write_index(self.index, index_path)

        with open(metadata_path, "w") as f:
            json.dump(self.metadata, f)

        logger.info(
            f"Saved FAISS index ({self.index.ntotal} vectors) to {directory}"
        )

    def load(self, directory: str):
        """
        Load a FAISS index and metadata from disk.
        """
        index_path = os.path.join(directory, "index.faiss")
        metadata_path = os.path.join(directory, "metadata.json")

        if not os.path.exists(index_path):
            logger.warning(f"No FAISS index found at {directory}")
            return

        self.index = faiss.read_index(index_path)

        with open(metadata_path, "r") as f:
            self.metadata = json.load(f)

        logger.info(
            f"Loaded FAISS index ({self.index.ntotal} vectors) from {directory}"
        )

    # ── Management ───────────────────────────────────────────

    def delete_document_vectors(self, document_id: str):
        """
        Remove all vectors for a specific document.

        Note: FAISS doesn't support efficient deletion.
        We rebuild the index without the deleted vectors.
        This is fine for our scale (<100K vectors).
        """
        if self.index.ntotal == 0:
            return

        # Find indices to keep
        keep_indices = [
            i for i, m in enumerate(self.metadata)
            if m.get("document_id") != document_id
        ]

        if len(keep_indices) == len(self.metadata):
            return  # Nothing to delete

        # Rebuild index with only kept vectors
        all_vectors = faiss.rev_swig_ptr(
            self.index.get_xb(), self.index.ntotal * self.dimension
        ).reshape(self.index.ntotal, self.dimension).copy()

        keep_vectors = all_vectors[keep_indices]
        keep_metadata = [self.metadata[i] for i in keep_indices]

        # Reset and re-add
        self._initialize_index()
        if len(keep_vectors) > 0:
            self.add_vectors(keep_vectors, keep_metadata)

        logger.info(f"Removed vectors for document {document_id}")

    def get_stats(self) -> dict:
        """Get index statistics."""
        doc_ids = set(
            m.get("document_id") for m in self.metadata
            if m.get("document_id")
        )
        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "unique_documents": len(doc_ids),
        }
