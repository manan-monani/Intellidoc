"""
Named Entity Recognition (NER)
==============================
Extracts named entities (people, organizations, locations, etc.) from text.

What is NER?
    NER finds and classifies "named things" in text:
    - PERSON: "John Smith", "Dr. Patel"
    - ORGANIZATION: "Google", "Reserve Bank of India"
    - LOCATION: "Mumbai", "United States"
    - DATE: "March 2024", "next Monday"
    - MONEY: "$50,000", "₹10 lakhs"
    - And more...

Why is NER useful for document processing?
    - Extract key information from invoices (company names, amounts)
    - Find people mentioned in contracts
    - Identify locations in reports
    - Automate data entry from documents

How the model works:
    This uses a BERT model fine-tuned for NER (dslim/bert-base-NER):
    1. Tokenize the text into wordpieces
    2. Each token gets a label: B-PER (Begin Person), I-PER (Inside Person), etc.
    3. Group consecutive tokens with the same label into entities
    4. Return the entities with their labels and confidence scores

Industry context:
    - SpaCy is another popular NER library
    - AWS Comprehend provides NER as a service
    - Google NLP API also offers NER
    - Custom NER models are trained for specific domains
"""

from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class NERExtractor:
    """
    Extracts named entities from document text.

    Usage:
        ner = NERExtractor()
        ner.load_model()
        entities = ner.extract("John Smith works at Google in Mumbai.")
        # [
        #     {"entity": "John Smith", "label": "PER", "score": 0.99},
        #     {"entity": "Google", "label": "ORG", "score": 0.98},
        #     {"entity": "Mumbai", "label": "LOC", "score": 0.97},
        # ]
    """

    def __init__(self):
        self.ner_pipeline = None
        self._model_name = "dslim/bert-base-NER"

    def load_model(self):
        """
        Load the NER model. Called lazily on first use.

        Model: dslim/bert-base-NER
        - Fine-tuned BERT for token classification
        - Trained on CoNLL-2003 dataset
        - Recognizes: PER, ORG, LOC, MISC
        """
        if self.ner_pipeline is None:
            logger.info(f"Loading NER model: {self._model_name}")
            self.ner_pipeline = pipeline(
                "ner",
                model=self._model_name,
                tokenizer=self._model_name,
                aggregation_strategy="simple",  # Merge B-PER + I-PER
                device=-1,  # CPU
            )
            logger.info("NER model loaded successfully")

    def extract(
        self,
        text: str,
        min_score: float = 0.5,
        max_length: int = 5000,
    ) -> List[dict]:
        """
        Extract named entities from text.

        Args:
            text: Input text to extract entities from
            min_score: Minimum confidence score (0-1)
            max_length: Max text length to process

        Returns:
            List of entity dicts:
            [
                {
                    "entity": "entity text",
                    "label": "PER/ORG/LOC/MISC",
                    "score": 0.99,
                    "start": 0,
                    "end": 10
                }
            ]

        Label meanings:
            PER  = Person name
            ORG  = Organization
            LOC  = Location
            MISC = Miscellaneous (events, nationalities, etc.)
        """
        self.load_model()

        # Process text in chunks if too long
        # (BERT has a 512 token limit)
        chunks = self._chunk_text(text, max_length)
        all_entities = []

        for chunk_start, chunk_text in chunks:
            results = self.ner_pipeline(chunk_text)

            for entity in results:
                if entity["score"] >= min_score:
                    all_entities.append({
                        "entity": entity["word"].strip(),
                        "label": entity["entity_group"],
                        "score": round(entity["score"], 4),
                        "start": entity["start"] + chunk_start,
                        "end": entity["end"] + chunk_start,
                    })

        # Deduplicate entities
        return self._deduplicate(all_entities)

    def extract_grouped(self, text: str) -> dict:
        """
        Extract entities and group them by type.

        Returns:
            {
                "PER": ["John Smith", "Dr. Patel"],
                "ORG": ["Google", "OpenAI"],
                "LOC": ["Mumbai", "San Francisco"],
                "MISC": ["Indian", "AI Summit 2024"],
            }
        """
        entities = self.extract(text)
        grouped = {}

        for entity in entities:
            label = entity["label"]
            if label not in grouped:
                grouped[label] = []
            if entity["entity"] not in grouped[label]:
                grouped[label].append(entity["entity"])

        return grouped

    def _chunk_text(
        self,
        text: str,
        max_length: int,
    ) -> List[tuple]:
        """
        Split text into processable chunks with offset tracking.

        Returns list of (offset, chunk_text) tuples.
        """
        if len(text) <= max_length:
            return [(0, text)]

        chunks = []
        start = 0
        while start < len(text):
            end = start + max_length
            # Try to break at a sentence boundary
            if end < len(text):
                last_period = text[start:end].rfind(".")
                if last_period > max_length * 0.5:
                    end = start + last_period + 1
            chunks.append((start, text[start:end]))
            start = end

        return chunks

    def _deduplicate(self, entities: List[dict]) -> List[dict]:
        """Remove duplicate entities, keeping the highest-scoring one."""
        seen = {}
        for entity in entities:
            key = (entity["entity"].lower(), entity["label"])
            if key not in seen or entity["score"] > seen[key]["score"]:
                seen[key] = entity
        return list(seen.values())
