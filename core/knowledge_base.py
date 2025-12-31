import os
import pypdf
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any, Optional

class KnowledgeBaseManager:
    """
    Handles document ingestion, embedding, and retrieval for the AI Theater.
    Uses ChromaDB for local vector storage.
    """
    
    def __init__(self, persist_directory: str = "theater_db/knowledge"):
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.collection = self.client.get_or_create_collection(name="world_lore")
        self.embedding_fn = None

    def set_embedding_provider(self, api_key: str, base_url: str, model: str = "text-embedding-3-small"):
        """Configures the embedding function using an OpenAI-compatible API."""
        self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            api_base=base_url,
            model_name=model
        )

    def add_document(self, file_path: str, metadata: Optional[Dict[str, Any]] = None):
        """Parses and adds a document to the knowledge base."""
        if not os.path.exists(file_path):
            return False
            
        content = ""
        if file_path.endswith(".pdf"):
            content = self._parse_pdf(file_path)
        elif file_path.endswith(".md") or file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        
        if not content:
            return False
            
        chunks = self._chunk_text(content)
        ids = [f"{os.path.basename(file_path)}_{i}" for i in range(len(chunks))]
        metas = [metadata or {} for _ in range(len(chunks))]
        
        self.collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metas
        )
        return True

    def query(self, text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Retrieves relevant context from the knowledge base."""
        results = self.collection.query(
            query_texts=[text],
            n_results=n_results
        )
        
        structured_results = []
        if results['documents']:
            for i in range(len(results['documents'][0])):
                structured_results.append({
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "id": results['ids'][0][i]
                })
        return structured_results

    def _parse_pdf(self, path: str) -> str:
        text = ""
        try:
            reader = pypdf.PdfReader(path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            print(f"Error parsing PDF: {e}")
        return text

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """Simple recursive-style chunking."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def clear_database(self):
        """Wipes all documents from the collection."""
        self.client.delete_collection(name="world_lore")
        self.collection = self.client.get_or_create_collection(name="world_lore")
