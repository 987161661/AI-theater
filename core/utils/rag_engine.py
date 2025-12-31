import numpy as np
from typing import List, Dict, Any, Optional
import requests
from pypdf import PdfReader
from core.llm_provider import LLMProvider

class RAGEngine:
    """
    Handles document ingestion, embedding generation, and semantic search.
    """
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.documents = []  # List of dicts: {"text": str, "embedding": np.ndarray}

    def process_pdf(self, file_path: str):
        """Extracts text from PDF and chunks it."""
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        # Simple chunking by paragraph/newline
        chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) > 50]
        self._add_chunks(chunks)

    def process_text(self, text: str):
        """Processes raw text string."""
        chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) > 50]
        self._add_chunks(chunks)

    def _add_chunks(self, chunks: List[str]):
        """Generates embeddings for chunks and adds to store."""
        # Note: In a production app, we'd use a real vector DB. 
        # Here we use a simple numpy-based memory store.
        for chunk in chunks:
            embedding = self._get_embedding(chunk)
            if embedding is not None:
                self.documents.append({
                    "text": chunk,
                    "embedding": np.array(embedding)
                })

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Calls OpenAI Embeddings API (text-embedding-3-small)."""
        if not self.provider.client:
            return None
        
        try:
            response = self.provider.client.embeddings.create(
                input=[text],
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding error: {e}")
            return None

    def query(self, text: str, top_k: int = 3) -> List[str]:
        """Performs semantic search."""
        query_embedding = self._get_embedding(text)
        if query_embedding is None or not self.documents:
            return []

        query_embedding = np.array(query_embedding)
        
        # Calculate cosine similarity
        similarities = []
        for doc in self.documents:
            sim = np.dot(query_embedding, doc["embedding"]) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc["embedding"])
            )
            similarities.append(sim)

        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return [self.documents[i]["text"] for i in top_indices if similarities[i] > 0.3]

    def clear(self):
        """Clears the knowledge base."""
        self.documents = []
