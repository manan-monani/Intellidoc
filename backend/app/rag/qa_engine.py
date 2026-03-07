"""
RAG Q&A Engine
==============
The crown jewel — Retrieval-Augmented Generation for intelligent Q&A.

What is RAG?
    RAG = Retrieval-Augmented Generation

    The problem with LLMs:
    - They only know their training data (no knowledge of YOUR documents)
    - They can "hallucinate" (make up plausible-sounding false info)

    RAG solves this by:
    1. RETRIEVE: Find relevant text chunks from your documents
    2. AUGMENT: Add those chunks as context to the LLM prompt
    3. GENERATE: LLM generates an answer GROUNDED in your documents

    It's like an open-book exam — the LLM can reference the source material.

How our RAG pipeline works:
    User asks: "What is the revenue growth?"

    Step 1 — Embed the question:
        "What is the revenue growth?" → [0.3, 0.7, 0.2, ...]

    Step 2 — Search FAISS:
        Find chunks with similar embeddings
        → "Revenue grew by 25% in Q3 2024..."
        → "Annual growth targets were exceeded..."

    Step 3 — Build prompt:
        "Based on the following context, answer the question.
        Context: [retrieved chunks]
        Question: What is the revenue growth?
        Answer:"

    Step 4 — LLM generates:
        "Based on the documents, revenue grew by 25% in Q3 2024..."

Industry context:
    - This is the most in-demand AI skill in 2024-2025
    - Used by ChatGPT with browsing, Perplexity, and enterprise AI
    - The JD specifically mentions RAG as a bonus skill!
"""

import ollama
import logging
from typing import List, Optional
from app.rag.embeddings import EmbeddingGenerator
from app.rag.vector_store import FAISSVectorStore
from app.rag.chunker import DocumentChunker
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class QAEngine:
    """
    RAG-powered question-answering engine.

    Usage:
        qa = QAEngine()
        qa.index_document(doc_id, "full document text...", {"filename": "report.pdf"})
        answer = qa.ask("What is the revenue growth?")
    """

    def __init__(self):
        self.embedder = EmbeddingGenerator(model_name=settings.embedding_model)

        # Set FAISS dimension based on embedding provider
        if settings.embedding_provider == "bedrock":
            dimension = 1024  # Titan Embeddings v2
        else:
            dimension = 384   # all-MiniLM-L6-v2

        self.vector_store = FAISSVectorStore(dimension=dimension)
        self.chunker = DocumentChunker(chunk_size=800, chunk_overlap=200)
        self._load_index()

    def _load_index(self):
        """Load existing FAISS index from disk if available."""
        try:
            self.vector_store.load(settings.faiss_index_path)
        except Exception:
            logger.info("No existing FAISS index found. Starting fresh.")

    # ── Indexing ─────────────────────────────────────────────

    def index_document(
        self,
        document_id: str,
        text: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """
        Index a document for RAG retrieval.

        Steps:
        1. Chunk the text into smaller pieces
        2. Generate embeddings for each chunk
        3. Store embeddings and metadata in FAISS

        Args:
            document_id: Unique document ID
            text: Full document text
            metadata: Additional metadata (filename, etc.)

        Returns:
            Number of chunks indexed
        """
        if not text or not text.strip():
            return 0

        # Step 1: Chunk
        chunks = self.chunker.chunk_text(
            text=text,
            document_id=document_id,
            metadata=metadata or {},
        )

        if not chunks:
            return 0

        # Step 2: Generate embeddings for all chunks
        chunk_texts = [c["text"] for c in chunks]
        embeddings = self.embedder.embed_batch(chunk_texts)

        # Step 3: Prepare metadata for each chunk
        chunk_metadata = []
        for chunk in chunks:
            chunk_metadata.append({
                "document_id": document_id,
                "chunk_text": chunk["text"],
                "chunk_index": chunk["chunk_index"],
                **(metadata or {}),
            })

        # Step 4: Add to FAISS
        self.vector_store.add_vectors(embeddings, chunk_metadata)

        # Save index to disk
        self.vector_store.save(settings.faiss_index_path)

        logger.info(
            f"Indexed document {document_id}: "
            f"{len(chunks)} chunks"
        )
        return len(chunks)

    def remove_document(self, document_id: str):
        """Remove a document's vectors from the index."""
        self.vector_store.delete_document_vectors(document_id)
        self.vector_store.save(settings.faiss_index_path)

    # ── Retrieval ────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        """
        Search for relevant document chunks.

        Args:
            query: Search query text
            top_k: Number of results to return
            document_ids: Optional filter by document IDs

        Returns:
            List of search results with score and metadata
        """
        # Embed the query
        query_embedding = self.embedder.embed_text(query)

        # Search FAISS
        results = self.vector_store.search_with_filter(
            query_embedding=query_embedding,
            top_k=top_k,
            document_ids=document_ids,
        )

        return results

    # ── Q&A ──────────────────────────────────────────────────

    def ask(
        self,
        question: str,
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> dict:
        """
        Ask a question and get a RAG-powered answer.

        The full RAG pipeline:
        1. Embed the question
        2. Search FAISS for relevant chunks
        3. Build a context-enriched prompt
        4. Send to LLM for answer generation
        5. Return answer with sources

        Args:
            question: The user's question
            top_k: Number of context chunks to retrieve
            document_ids: Optional filter

        Returns:
            {
                "answer": "Based on the documents...",
                "sources": [...],
                "confidence": 0.85
            }
        """
        # Step 1 & 2: Retrieve relevant chunks
        results = self.search(question, top_k, document_ids)

        if not results:
            return {
                "answer": "I couldn't find any relevant information in the indexed documents. "
                          "Please make sure documents are uploaded and indexed.",
                "sources": [],
                "confidence": 0.0,
            }

        # Step 3: Build context
        context = self._build_context(results)

        # Step 4: Generate answer using LLM
        answer = self._generate_answer(question, context)

        # Step 5: Calculate confidence (average retrieval score)
        avg_score = sum(r["score"] for r in results) / len(results)

        return {
            "answer": answer,
            "sources": [
                {
                    "chunk_text": r["metadata"].get("chunk_text", ""),
                    "document_id": r["metadata"].get("document_id", ""),
                    "score": r["score"],
                    "filename": r["metadata"].get("filename", ""),
                }
                for r in results
            ],
            "confidence": round(avg_score, 4),
        }

    def _build_context(self, results: List[dict]) -> str:
        """
        Build context string from retrieved chunks.

        Format each chunk with its source info so the LLM
        can reference specific documents.
        """
        context_parts = []
        for i, result in enumerate(results, 1):
            chunk_text = result["metadata"].get("chunk_text", "")
            filename = result["metadata"].get("filename", "Unknown")
            score = result["score"]

            context_parts.append(
                f"[Source {i} - {filename} (relevance: {score:.2f})]:\n"
                f"{chunk_text}"
            )

        return "\n\n---\n\n".join(context_parts)

    def _generate_answer(
        self,
        question: str,
        context: str,
    ) -> str:
        """
        Generate an answer using the LLM.

        The prompt is carefully designed to:
        1. Tell the LLM to ONLY use the provided context
        2. Ask it to cite sources
        3. Tell it to say "I don't know" if the info isn't in the context
        4. This reduces hallucinations significantly
        """
        prompt = f"""You are an intelligent document assistant. Answer the user's question 
based ONLY on the provided context from their documents. 

Rules:
1. Only use information from the provided context
2. If the answer is not in the context, say "The documents don't contain this information"
3. Cite which source(s) you used (e.g., "According to Source 1...")
4. Be concise but comprehensive
5. If the question is ambiguous, mention what you found and ask for clarification

Context from documents:
{context}

Question: {question}

Answer:"""

        try:
            if settings.llm_provider == "bedrock":
                # Use AWS Bedrock for LLM inference
                from app.ml.bedrock_client import get_bedrock_client

                client = get_bedrock_client()
                return client.generate_qa_answer(question, context)
            else:
                # Use Ollama for local LLM inference
                response = ollama.chat(
                    model=settings.ollama_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful document analysis assistant. "
                                       "Answer questions accurately based on the provided context.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    options={
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_predict": 500,
                    },
                )
                return response["message"]["content"]

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return (
                f"I found relevant information but couldn't generate a response. "
                f"Error: {str(e)}. "
                f"Make sure Ollama is running with the '{settings.ollama_model}' model."
            )

    # ── Stats ────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get RAG pipeline statistics."""
        return self.vector_store.get_stats()
