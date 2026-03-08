"""
Document Chunker
================
Splits documents into smaller chunks for the RAG pipeline.

Why chunking?
    - LLMs have context window limits (e.g., 4096 tokens)
    - Embeddings work better on focused text segments
    - It's more efficient to search small chunks than full documents
    - We need to find the RELEVANT parts, not return everything

Chunking strategies:
    1. Fixed-size: Split every N characters (simple but bad)
    2. Recursive: Split by paragraphs → sentences → words (what we use)
    3. Semantic: Split by topic/meaning (complex but best)

Overlap:
    Chunks overlap slightly (e.g., 200 chars) so we don't lose
    information at chunk boundaries. Think of a sliding window.

Industry context:
    - LangChain provides standard chunking utilities
    - Chunk size of 500-1000 chars is typical for Q&A
    - Smaller chunks = more precise retrieval
    - Larger chunks = more context per result
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging
from typing import List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class DocumentChunker:
    """
    Splits document text into overlapping chunks.

    Usage:
        chunker = DocumentChunker(chunk_size=800, overlap=200)
        chunks = chunker.chunk_text(
            text="long document text...",
            document_id=uuid,
            metadata={"filename": "report.pdf"}
        )
    """

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
    ):
        """
        Args:
            chunk_size: Target size for each chunk (in characters).
                       800 chars ≈ ~200 tokens ≈ 1 paragraph.
            chunk_overlap: Number of overlapping characters between chunks.
                          Prevents losing info at boundaries.
            separators: Priority list of split characters.
                       Splits at the highest-priority separator that fits.
        """
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators or [
                "\n\n",  # Priority 1: paragraph breaks
                "\n",    # Priority 2: line breaks
                ". ",    # Priority 3: sentences
                ", ",    # Priority 4: clauses
                " ",     # Priority 5: words
                "",      # Priority 6: characters (last resort)
            ],
            length_function=len,
        )

    def chunk_text(
        self,
        text: str,
        document_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
    ) -> List[dict]:
        """
        Split text into chunks with metadata.

        Args:
            text: Full document text
            document_id: UUID of the source document
            metadata: Additional metadata to attach to each chunk

        Returns:
            List of chunk dicts:
            [
                {
                    "text": "chunk text...",
                    "chunk_index": 0,
                    "start_char": 0,
                    "end_char": 800,
                    "document_id": "uuid-here",
                    "metadata": {...}
                }
            ]

        How RecursiveCharacterTextSplitter works:
            1. Try to split at paragraph breaks (\n\n)
            2. If chunks are still too large, split at line breaks (\n)
            3. Continue with sentences, words, etc.
            4. Each chunk aim for chunk_size characters
            5. Adjacent chunks share chunk_overlap characters
        """
        if not text or not text.strip():
            return []

        # Split the text
        chunks = self.splitter.split_text(text)

        # Build chunk objects with metadata
        result = []
        current_pos = 0

        for i, chunk_text in enumerate(chunks):
            # Find the chunk's position in the original text
            start = text.find(chunk_text, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(chunk_text)

            chunk = {
                "text": chunk_text,
                "chunk_index": i,
                "start_char": start,
                "end_char": end,
                "document_id": str(document_id) if document_id else None,
                "metadata": {
                    **(metadata or {}),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            }
            result.append(chunk)

            # Move position forward (accounting for overlap)
            current_pos = start + 1

        logger.info(
            f"Chunked document into {len(result)} chunks "
            f"(avg {sum(len(c['text']) for c in result) // max(len(result), 1)} chars)"
        )

        return result

    def chunk_with_context(
        self,
        text: str,
        document_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
        context_window: int = 1,
    ) -> List[dict]:
        """
        Chunk text with surrounding context for better retrieval.

        Each chunk includes text from adjacent chunks for more context.
        This helps when the answer spans multiple chunks.

        Args:
            context_window: Number of adjacent chunks to include as context
        """
        chunks = self.chunk_text(text, document_id, metadata)

        for i, chunk in enumerate(chunks):
            # Build context from surrounding chunks
            context_parts = []

            # Before
            for j in range(max(0, i - context_window), i):
                context_parts.append(chunks[j]["text"])

            # Current
            context_parts.append(chunk["text"])

            # After
            for j in range(i + 1, min(len(chunks), i + context_window + 1)):
                context_parts.append(chunks[j]["text"])

            chunk["context"] = " ... ".join(context_parts)

        return chunks
