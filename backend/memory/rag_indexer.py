"""
RAGIndexer — indicizza documenti locali nella knowledge base ChromaDB.

Supporta: PDF, TXT, MD, Python, JS, TS, JSON, YAML, RST, DOCX, XLSX, CSV, HTML, XML.

Chunking adattivo: sceglie la strategia migliore in base al tipo di file.

Utilizzo da codice:
    indexer = RAGIndexer(persistent_memory)
    indexer.index_file("docs/manuale.pdf")
    indexer.watch_folder("data/knowledge")   # monitoraggio automatico

Utilizzo da riga di comando (dentro il container):
    python -m memory.rag_indexer index data/knowledge/
    python -m memory.rag_indexer list
    python -m memory.rag_indexer delete manuale.pdf
"""

import re
import logging
import hashlib
from pathlib import Path
from typing import Generator

logger = logging.getLogger("jarvis.memory.rag")

# Dimensione chunk in caratteri e overlap
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# Estensioni supportate
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".rst", ".docx", ".xlsx", ".csv", ".html", ".xml"}

# ── Chunking strategies ──────────────────────────────────────────────────

def _chunk_by_paragraphs(text: str, chunk_size: int = CHUNK_SIZE) -> Generator[str, None, None]:
    """Divide per paragrafi (doppio newline), raggruppandoli fino a chunk_size."""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return
    buf = []
    buf_len = 0
    for p in paragraphs:
        if buf_len + len(p) > chunk_size and buf:
            yield "\n\n".join(buf)
            buf = [p]
            buf_len = len(p)
        else:
            buf.append(p)
            buf_len += len(p) + 2
    if buf:
        yield "\n\n".join(buf)


def _chunk_code(text: str, chunk_size: int = CHUNK_SIZE) -> Generator[str, None, None]:
    """Divide codice per funzione/classe, con fallback a chunk fisso."""
    pattern = re.compile(r"^(?:def |class |@\w+|async def |private |public |function |const \w+ = )", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        yield from _chunk_by_paragraphs(text, chunk_size)
        return
    segments = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segments.append(text[start:end].strip())
    buf = []
    buf_len = 0
    for seg in segments:
        if buf_len + len(seg) > chunk_size and buf:
            yield "\n\n".join(buf)
            buf = [seg]
            buf_len = len(seg)
        else:
            buf.append(seg)
            buf_len += len(seg) + 1
    if buf:
        yield "\n\n".join(buf)


def _chunk_by_headings(text: str, chunk_size: int = CHUNK_SIZE) -> Generator[str, None, None]:
    """Divide markdown/rST per headings."""
    pattern = re.compile(r"^(#{1,3}\s|\w[\w\s]*\n[=\-]+\s*$)", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        yield from _chunk_by_paragraphs(text, chunk_size)
        return
    segments = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segments.append(text[start:end].strip())
    buf = []
    buf_len = 0
    for seg in segments:
        if buf_len + len(seg) > chunk_size and buf:
            yield "\n\n".join(buf)
            buf = [seg]
            buf_len = len(seg)
        else:
            buf.append(seg)
            buf_len += len(seg) + 1
    if buf:
        yield "\n\n".join(buf)


def _chunk_structured(text: str, chunk_size: int = CHUNK_SIZE) -> Generator[str, None, None]:
    """Per JSON/YAML: split by top-level keys, raggruppa."""
    if len(text) <= chunk_size * 1.5:
        yield text.strip()
        return
    lines = text.split("\n")
    groups = []
    current = []
    for line in lines:
        if re.match(r'^\s{0,4}"\w+"\s*:|^\s{0,4}\w+\s*:', line) and current:
            groups.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        groups.append("\n".join(current))
    buf = []
    buf_len = 0
    for g in groups:
        if buf_len + len(g) > chunk_size and buf:
            yield "\n\n".join(buf)
            buf = [g]
            buf_len = len(g)
        else:
            buf.append(g)
            buf_len += len(g) + 1
    if buf:
        yield "\n\n".join(buf)


# ── Extraction helpers ───────────────────────────────────────────────────

def _extract_text_from_pdf(path: Path) -> str:
    """Estrae testo da PDF con pypdf (installato nel container)."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        pages = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
        return "\n\n".join(pages)
    except ImportError:
        logger.warning("pypdf non installato — installa con: pip install pypdf")
        return ""
    except Exception as e:
        logger.error(f"Errore lettura PDF {path}: {e}")
        return ""


def _extract_text_from_docx(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        logger.warning("python-docx non installato — installa con: pip install python-docx")
        return ""
    except Exception as e:
        logger.error(f"Errore lettura DOCX {path}: {e}")
        return ""


def _extract_text_from_xlsx(path: Path) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        parts = []
        for sheet in wb.worksheets:
            rows = []
            for row in sheet.iter_rows(values_only=True):
                row_text = "\t".join(str(c) if c is not None else "" for c in row)
                if row_text.strip():
                    rows.append(row_text)
            if rows:
                parts.append(f"=== Foglio: {sheet.title} ===\n" + "\n".join(rows))
        return "\n\n".join(parts)
    except ImportError:
        logger.warning("openpyxl non installato — installa con: pip install openpyxl")
        return ""
    except Exception as e:
        logger.error(f"Errore lettura XLSX {path}: {e}")
        return ""


def _extract_text_from_csv(path: Path) -> str:
    try:
        import csv, io
        text = path.read_text(encoding="utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        lines = [" | ".join(row) for row in reader]
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Errore lettura CSV {path}: {e}")
        return ""


def _extract_text_from_html(path: Path) -> str:
    try:
        from html.parser import HTMLParser
        class TagStripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
            def handle_data(self, data):
                t = data.strip()
                if t:
                    self.text.append(t)
        stripper = TagStripper()
        stripper.feed(path.read_text(encoding="utf-8", errors="replace"))
        return "\n".join(stripper.text)
    except Exception as e:
        logger.error(f"Errore lettura HTML {path}: {e}")
        return ""


def _extract_text(path: Path) -> str:
    """Estrae testo in base all'estensione del file."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_text_from_pdf(path)
    if suffix == ".docx":
        return _extract_text_from_docx(path)
    if suffix == ".xlsx":
        return _extract_text_from_xlsx(path)
    if suffix == ".csv":
        return _extract_text_from_csv(path)
    if suffix == ".html":
        return _extract_text_from_html(path)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Errore lettura {path}: {e}")
        return ""


def _chunk_adaptive(text: str, ext: str) -> Generator[str, None, None]:
    """Seleziona la strategia di chunking in base all'estensione."""
    if ext in (".py", ".js", ".ts", ".jsx", ".tsx"):
        return _chunk_code(text)
    if ext in (".md", ".rst"):
        return _chunk_by_headings(text)
    if ext in (".json", ".yaml", ".yml"):
        return _chunk_structured(text)
    if ext == ".csv":
        rows = [r.strip() for r in text.split("\n") if r.strip()]
        for row in rows:
            yield row
        return
    return _chunk_by_paragraphs(text)


class RAGIndexer:
    def __init__(self, persistent_memory):
        """
        Args:
            persistent_memory: istanza di PersistentMemory
        """
        self._mem = persistent_memory

    # ──────────────────────────────────────────────
    # Indicizzazione
    # ──────────────────────────────────────────────

    def index_file(self, file_path: str | Path, force: bool = False) -> int:
        """
        Indicizza un singolo file.
        Usa l'hash del contenuto per evitare re-indicizzazioni inutili.
        Ritorna il numero di chunk indicizzati (0 se già aggiornato).
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File non trovato: {path}")
            return 0

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.warning(f"Estensione non supportata: {path.suffix}")
            return 0

        text = _extract_text(path)
        if not text.strip():
            logger.warning(f"Nessun testo estratto da {path.name}")
            return 0

        # Controlla se il file è cambiato dall'ultima indicizzazione
        file_hash = hashlib.md5(text.encode()).hexdigest()
        saved_hash = self._mem.get_preference(f"rag_hash_{path.name}")

        if not force and saved_hash == file_hash:
            logger.info(f"'{path.name}' non modificato — skip")
            return 0

        # Rimuovi vecchi chunk e reindicizza
        self._mem.delete_knowledge_source(path.name)

        chunks = list(_chunk_adaptive(text, path.suffix.lower()))
        for i, chunk in enumerate(chunks):
            chunk_id = f"rag_{path.stem}_{i}_{file_hash[:8]}"
            self._mem.index_document(
                text=chunk,
                source=path.name,
                chunk_id=chunk_id,
                extra_meta={"chunk_index": i, "total_chunks": len(chunks), "file_hash": file_hash},
            )

        # Salva l'hash per evitare re-indicizzazioni
        self._mem.set_preference(f"rag_hash_{path.name}", file_hash)
        logger.info(f"Indicizzato '{path.name}': {len(chunks)} chunk")
        return len(chunks)

    def index_folder(self, folder_path: str | Path, recursive: bool = True) -> dict[str, int]:
        """
        Indicizza tutti i file supportati in una cartella.
        Ritorna un dict {nome_file: n_chunk}.
        """
        folder = Path(folder_path)
        if not folder.is_dir():
            logger.error(f"Cartella non trovata: {folder}")
            return {}

        pattern = "**/*" if recursive else "*"
        results = {}
        for path in folder.glob(pattern):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                n = self.index_file(path)
                if n > 0:
                    results[path.name] = n

        total = sum(results.values())
        logger.info(f"Cartella '{folder}' indicizzata: {len(results)} file, {total} chunk totali")
        return results

    def watch_folder(self, folder_path: str | Path, interval_seconds: int = 60):
        """
        Avvia il monitoraggio di una cartella in background (thread daemon).
        Reindicizza automaticamente i file modificati ogni `interval_seconds`.
        """
        import threading

        def _watch():
            import time
            logger.info(f"Watch avviato su '{folder_path}' (ogni {interval_seconds}s)")
            while True:
                try:
                    self.index_folder(folder_path)
                except Exception as e:
                    logger.warning(f"Watch error: {e}")
                time.sleep(interval_seconds)

        t = threading.Thread(target=_watch, daemon=True, name="rag-watcher")
        t.start()
        return t

    # ──────────────────────────────────────────────
    # Gestione
    # ──────────────────────────────────────────────

    def list_sources(self) -> list[str]:
        return self._mem.list_knowledge_sources()

    def delete_source(self, filename: str):
        self._mem.delete_knowledge_source(filename)
        self._mem.delete_preference(f"rag_hash_{filename}")
        logger.info(f"Sorgente rimossa: {filename}")

    def stats(self) -> dict:
        sources = self.list_sources()
        count = self._mem.knowledge.count()
        return {"sources": sources, "total_chunks": count}


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import yaml
    from memory.persistent import PersistentMemory

    with open("config/settings.yaml") as f:
        config = yaml.safe_load(f)

    mem = PersistentMemory(config)
    indexer = RAGIndexer(mem)

    if len(sys.argv) < 2:
        print("Uso: python -m memory.rag_indexer [index <path>|list|delete <source>|stats]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "index" and len(sys.argv) > 2:
        target = Path(sys.argv[2])
        if target.is_dir():
            result = indexer.index_folder(target)
            print(f"Indicizzati {len(result)} file:")
            for name, n in result.items():
                print(f"  {name}: {n} chunk")
        else:
            n = indexer.index_file(target, force=True)
            print(f"Indicizzato: {n} chunk")

    elif cmd == "list":
        sources = indexer.list_sources()
        if sources:
            print(f"Documenti nella knowledge base ({len(sources)}):")
            for s in sources:
                print(f"  - {s}")
        else:
            print("Knowledge base vuota.")

    elif cmd == "delete" and len(sys.argv) > 2:
        indexer.delete_source(sys.argv[2])
        print(f"Rimosso: {sys.argv[2]}")

    elif cmd == "stats":
        s = indexer.stats()
        print(f"Chunk totali: {s['total_chunks']}")
        print(f"Sorgenti: {len(s['sources'])}")
        for src in s["sources"]:
            print(f"  - {src}")
