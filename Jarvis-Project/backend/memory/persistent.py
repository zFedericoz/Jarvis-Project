import chromadb
from chromadb.config import Settings
import logging
from pathlib import Path

logger = logging.getLogger("jarvis.memory.persistent")

class PersistentMemory:
    def __init__(self, persist_dir: str = "data/chroma_db", collection_name: str = "jarvis_memories"):
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(name=collection_name)
        logger.info(f"Persistent memory initialized: {persist_dir}")

    def store(self, text: str, metadata: dict | None = None, doc_id: str | None = None):
        from uuid import uuid4
        doc_id = doc_id or str(uuid4())
        self.collection.add(
            documents=[text],
            metadatas=[metadata or {}],
            ids=[doc_id],
        )

    def search(self, query: str, n_results: int = 5) -> list[str]:
        results = self.collection.query(query_texts=[query], n_results=n_results)
        return results["documents"][0] if results["documents"] else []

    def get_recent(self, n: int = 10) -> list[str]:
        results = self.collection.get(limit=n)
        return results["documents"] if results["documents"] else []

    def delete_all(self):
        self.collection.delete()
        logger.info("All memories deleted")
