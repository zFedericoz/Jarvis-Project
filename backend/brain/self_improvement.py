import json
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("jarvis.brain.self_improvement")

_AUTO_TUNE_INTERVAL = 50
_FEEDBACK_FILE = Path("data/feedback.jsonl")
_BENCHMARK_FILE = Path("data/self_improvement_benchmark.json")
_FINETUNE_DATASET_FILE = Path("data/finetuning_dataset.jsonl")
_SAMPLE_QUESTIONS = [
    "Che anno siamo?",
    "Cosa puoi fare?",
    "Qual è la capitale d'Italia?",
    "Spiega cos'è un algoritmo in parole semplici",
    "Scrivi una funzione Python che calcola il fattoriale",
]

_EXAMPLES_CACHE: list[dict] | None = None
_EXAMPLES_CACHE_TIME = 0


class SelfImprovement:
    def __init__(self, memory, llm_client, rag_searcher):
        self._mem = memory
        self._llm = llm_client
        self._rag = rag_searcher
        self._response_count = 0
        self._recent_ratings: list[int] = []
        self._daily_timer: threading.Timer | None = None
        logger.info("SelfImprovement inizializzato")

    def record_response(self, user_msg: str, assistant_response: str, intent: str,
                        language: str = "it", rating: int | None = None):
        self._response_count += 1

        if rating is not None and rating >= 4:
            self._store_as_example(user_msg, assistant_response, intent, rating, language)
        elif rating is None:
            score = self._rate_auto(assistant_response, language)
            if score >= 8:
                self._store_as_example(user_msg, assistant_response, intent, score, language)

        if rating is not None:
            self._recent_ratings.append(rating)
            if len(self._recent_ratings) > 100:
                self._recent_ratings.pop(0)

        if self._response_count % _AUTO_TUNE_INTERVAL == 0:
            self._auto_tune()

    def handle_bad_feedback(self, user_msg: str, bad_response: str,
                            rating: int, intent: str, language: str = "it"):
        improved = self._llm._improve_response(user_msg, bad_response, None, language, rating)
        self._store_as_example(user_msg, improved, intent, 10, language, is_correction=True)
        logger.info(f"Bad feedback handled: rating={rating}, improvement stored")
        return improved

    def search_examples(self, query: str, intent: str, n: int = 2) -> list[str]:
        """Cerca esempi di alta qualità simili alla domanda corrente."""
        if not self._mem:
            return []
        try:
            results = self._mem.search_knowledge(query, n_results=n * 3)
            filtered = [
                r for r in results
                if r["metadata"].get("source", "").startswith("self_improvement")
                and int(r["metadata"].get("score", 0)) >= 7
            ]
            return [r["text"] for r in filtered[:n]]
        except Exception as e:
            logger.warning(f"search_examples fallito: {e}")
            return []

    def export_finetuning_dataset(self) -> Path:
        """Esporta un dataset fine-tuning da feedback.jsonl + knowledge base esempi."""
        pairs = []

        if _FEEDBACK_FILE.exists():
            with open(_FEEDBACK_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        pairs.append({
                            "instruction": entry.get("user_message", ""),
                            "output": entry.get("assistant_response", ""),
                            "rating": entry.get("rating", 0),
                            "intent": entry.get("intent", ""),
                            "language": entry.get("language", "it"),
                        })
                    except json.JSONDecodeError:
                        continue

        if self._mem:
            try:
                all_docs = self._mem.knowledge.get()
                for doc, meta in zip(all_docs.get("documents", []), all_docs.get("metadatas", [])):
                    source = meta.get("source", "") if meta else ""
                    if source.startswith("self_improvement"):
                        text = doc or ""
                        if "Q: " in text and "\nA: " in text:
                            parts = text.split("\nA: ", 1)
                            pairs.append({
                                "instruction": parts[0].replace("Q: ", "", 1),
                                "output": parts[1],
                                "rating": int(meta.get("score", 5)) if meta else 5,
                                "intent": meta.get("intent", "") if meta else "",
                                "language": meta.get("language", "it") if meta else "it",
                            })
            except Exception as e:
                logger.warning(f"Knowledge base export fallito: {e}")

        _FINETUNE_DATASET_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_FINETUNE_DATASET_FILE, "w", encoding="utf-8") as f:
            for pair in pairs:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
        logger.info(f"Dataset fine-tuning esportato: {len(pairs)} coppie -> {_FINETUNE_DATASET_FILE}")
        return _FINETUNE_DATASET_FILE

    def schedule_daily_evaluation(self):
        """Avvia scheduler giornaliero per benchmark automatico."""
        if self._daily_timer and self._daily_timer.is_alive():
            return

        def _run():
            try:
                logger.info("Esecuzione benchmark giornaliero automatico...")
                self.run_evaluation()
                self.export_finetuning_dataset()
                logger.info("Benchmark giornaliero completato")
            except Exception as e:
                logger.error(f"Benchmark giornaliero fallito: {e}")

        def _schedule():
            next_run = 24 * 3600
            self._daily_timer = threading.Timer(next_run, _schedule)
            self._daily_timer.daemon = True
            self._daily_timer.start()
            _run()

        # First run after 1 hour delay to let system stabilize
        initial_delay = 3600
        self._daily_timer = threading.Timer(initial_delay, _schedule)
        self._daily_timer.daemon = True
        self._daily_timer.start()
        logger.info(f"Scheduler benchmark giornaliero avviato (prima esecuzione tra {initial_delay}s)")

    def _rate_auto(self, response: str, language: str) -> int:
        try:
            return self._llm._rate_response("", response, language)
        except Exception:
            return 5

    def _store_as_example(self, user_msg: str, response: str, intent: str,
                          score: int, language: str = "it",
                          is_correction: bool = False):
        if not self._mem:
            return
        text = f"Q: {user_msg}\nA: {response}"
        source = "self_improvement_correction" if is_correction else "self_improvement_example"
        doc_id = f"self_{intent}_{datetime.now(timezone.utc).timestamp()}"
        self._mem.index_document(
            text=text,
            source=source,
            chunk_id=doc_id,
            extra_meta={
                "intent": intent,
                "score": score,
                "language": language,
                "is_correction": str(is_correction),
            },
        )
        logger.info(f"Stored {source}: {intent} score={score}")

    def _auto_tune(self):
        if len(self._recent_ratings) < 10:
            return
        avg = sum(self._recent_ratings[-20:]) / min(len(self._recent_ratings[-20:]), 20)
        logger.info(f"Auto-tune: avg rating={avg:.1f} over last {min(len(self._recent_ratings), 20)} responses")

        from brain.rag_searcher import rag_distance_threshold
        if avg < 3.0 and rag_distance_threshold < 2.0:
            new_val = min(rag_distance_threshold + 0.2, 2.0)
            old_val = rag_distance_threshold
            import brain.rag_searcher as rs
            rs.rag_distance_threshold = new_val
            logger.info(f"RAG threshold adjusted: {old_val:.1f} -> {new_val:.1f} (avg rating low)")

    def run_evaluation(self) -> dict:
        results = []
        correct_count = 0
        from brain.rag_searcher import rag_distance_threshold
        for q in _SAMPLE_QUESTIONS:
            response, _ = self._llm.chat(q)
            score = self._rate_auto(response, "it")
            is_correct = score >= 6
            if is_correct:
                correct_count += 1
            results.append({"question": q, "score": score, "is_correct": is_correct})
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": len(_SAMPLE_QUESTIONS),
            "correct": correct_count,
            "accuracy": round(correct_count / len(_SAMPLE_QUESTIONS) * 100, 1),
            "rag_threshold": rag_distance_threshold,
            "results": results,
        }
        _BENCHMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_BENCHMARK_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Benchmark: {report['accuracy']}% ({report['correct']}/{report['total']})")
        return report
