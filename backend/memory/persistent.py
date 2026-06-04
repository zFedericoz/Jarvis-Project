"""
PersistentMemory — memoria a lungo termine con ChromaDB.

Gestisce due collezioni separate:
  - jarvis_memories  : storico conversazioni + fatti generici
  - jarvis_knowledge : base di conoscenza RAG (PDF, documenti, note)

Aggiunge anche una "memoria esplicita" per preferenze e fatti
sull'utente (nome, cartelle preferite, progetti attivi, ecc.)
che sopravvivono ai riavvii.
"""

import json
import logging
from pathlib import Path
from uuid import uuid4
from datetime import datetime

import chromadb
from chromadb.config import Settings

logger = logging.getLogger("jarvis.memory.persistent")


class PersistentMemory:
    def __init__(self, config: dict | None = None):
        persist_dir = "data/chroma_db"
        collection_name = "jarvis_memories"

        if config is not None:
            mem_cfg = config.get("memory", {}).get("long_term", {})
            persist_dir = mem_cfg.get("persist_dir", persist_dir)
            collection_name = mem_cfg.get("collection", collection_name)

        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        # Collezione principale: conversazioni e fatti generici
        self.collection = self.client.get_or_create_collection(name=collection_name)

        # Collezione RAG: documenti indicizzati (PDF, testo, note)
        self.knowledge = self.client.get_or_create_collection(name="jarvis_knowledge")

        # Collezione preferenze utente: chiave-valore persistente
        self.prefs = self.client.get_or_create_collection(name="jarvis_preferences")

        logger.info(f"Persistent memory inizializzata: {persist_dir}")

    # ──────────────────────────────────────────────────────────────
    # Memoria conversazioni
    # ──────────────────────────────────────────────────────────────

    def store(self, text: str, metadata: dict | None = None, doc_id: str | None = None):
        """Salva un testo (turno di conversazione o fatto) con metadati opzionali."""
        doc_id = doc_id or str(uuid4())
        meta = {"timestamp": datetime.now().isoformat(), **(metadata or {})}
        self.collection.add(documents=[text], metadatas=[meta], ids=[doc_id])
        logger.debug(f"Stored memory [{doc_id}]: {text[:60]}")

    def search(self, query: str, n_results: int = 5, where: dict | None = None) -> list[dict]:
        """
        Cerca nella memoria per similarità semantica.
        Restituisce lista di dict con 'text', 'metadata', 'id'.
        """
        kwargs = {"query_texts": [query], "n_results": min(n_results, self.collection.count() or 1)}
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)
        if not results["documents"] or not results["documents"][0]:
            return []

        return [
            {"text": doc, "metadata": meta, "id": rid}
            for doc, meta, rid in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["ids"][0],
            )
        ]

    def get_recent(self, n: int = 10) -> list[str]:
        """Ritorna gli N documenti più recenti."""
        results = self.collection.get(limit=n)
        return results["documents"] if results["documents"] else []

    def delete_all(self):
        ids = self.collection.get()["ids"]
        if ids:
            self.collection.delete(ids=ids)
        logger.info("Tutte le memorie di conversazione eliminate")

    # ──────────────────────────────────────────────────────────────
    # Preferenze utente (chiave-valore persistente)
    # ──────────────────────────────────────────────────────────────

    def set_preference(self, key: str, value: str | int | float | list | dict):
        """
        Salva una preferenza utente con chiave univoca.
        Esempi:
          set_preference("nome_utente", "Federico")
          set_preference("cartella_progetti", "C:/Dev")
          set_preference("tema_ui", "dark")
        """
        serialized = json.dumps(value, ensure_ascii=False)
        meta = {"key": key, "updated_at": datetime.now().isoformat()}

        # Upsert: cancella il vecchio valore se esiste
        try:
            existing = self.prefs.get(ids=[f"pref_{key}"])
            if existing["ids"]:
                self.prefs.delete(ids=[f"pref_{key}"])
        except Exception:
            pass

        self.prefs.add(
            documents=[f"{key}: {serialized}"],
            metadatas=[meta],
            ids=[f"pref_{key}"],
        )
        logger.info(f"Preferenza salvata: {key} = {serialized[:80]}")

    def get_preference(self, key: str, default=None):
        """Recupera una preferenza per chiave esatta."""
        try:
            result = self.prefs.get(ids=[f"pref_{key}"])
            if result["documents"]:
                raw = result["documents"][0]
                # Formato: "chiave: valore_json"
                _, _, serialized = raw.partition(": ")
                return json.loads(serialized)
        except Exception as e:
            logger.debug(f"get_preference({key}) fallito: {e}")
        return default

    def get_all_preferences(self) -> dict:
        """Ritorna tutte le preferenze come dizionario."""
        try:
            results = self.prefs.get()
            prefs = {}
            for doc in results.get("documents", []):
                key, _, serialized = doc.partition(": ")
                try:
                    prefs[key] = json.loads(serialized)
                except Exception:
                    prefs[key] = serialized
            return prefs
        except Exception as e:
            logger.warning(f"get_all_preferences fallito: {e}")
            return {}

    def delete_preference(self, key: str):
        try:
            self.prefs.delete(ids=[f"pref_{key}"])
            logger.info(f"Preferenza eliminata: {key}")
        except Exception:
            pass

    def build_user_context_string(self) -> str:
        """
        Ritorna una stringa da iniettare nel system prompt con le
        preferenze note sull'utente (nome, progetti, cartelle, ecc.)
        """
        prefs = self.get_all_preferences()
        if not prefs:
            return ""

        lines = ["# Contesto utente (da memoria persistente)"]
        for k, v in prefs.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────────
    # Base di conoscenza RAG (Step 2 — documenti indicizzati)
    # ──────────────────────────────────────────────────────────────

    def index_document(self, text: str, source: str, chunk_id: str | None = None,
                       extra_meta: dict | None = None):
        """
        Indicizza un chunk di testo nella knowledge base.
        Chiamato dal RAGIndexer (rag_indexer.py).
        """
        doc_id = chunk_id or f"rag_{uuid4()}"
        meta = {
            "source": source,
            "indexed_at": datetime.now().isoformat(),
            **(extra_meta or {}),
        }
        self.knowledge.upsert(documents=[text], metadatas=[meta], ids=[doc_id])

    def search_knowledge(self, query: str, n_results: int = 5) -> list[dict]:
        """Cerca nella knowledge base RAG."""
        count = self.knowledge.count()
        if count == 0:
            return []

        results = self.knowledge.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )
        if not results["documents"] or not results["documents"][0]:
            return []

        return [
            {"text": doc, "metadata": meta, "id": rid}
            for doc, meta, rid in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["ids"][0],
            )
        ]

    def delete_knowledge_source(self, source: str):
        """Rimuove tutti i chunk di un documento dalla knowledge base."""
        try:
            results = self.knowledge.get(where={"source": source})
            if results["ids"]:
                self.knowledge.delete(ids=results["ids"])
                logger.info(f"Rimosso dalla knowledge base: {source} ({len(results['ids'])} chunk)")
        except Exception as e:
            logger.warning(f"delete_knowledge_source fallito: {e}")

    def list_knowledge_sources(self) -> list[str]:
        """Elenca tutti i documenti indicizzati nella knowledge base."""
        try:
            results = self.knowledge.get()
            sources = {m.get("source", "unknown") for m in results.get("metadatas", [])}
            return sorted(sources)
        except Exception:
            return []
