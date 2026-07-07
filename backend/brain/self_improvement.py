import json
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("jarvis.brain.self_improvement")

_AUTO_TUNE_INTERVAL = 50
_FEEDBACK_FILE = Path("data/feedback.jsonl")
_BENCHMARK_FILE = Path("data/self_improvement_benchmark.json")
_SAMPLE_QUESTIONS = [
    "Che anno siamo?",
    "Cosa puoi fare?",
    "Qual è la capitale d'Italia?",
    "Spiega cos'è un algoritmo in parole semplici",
    "Scrivi una funzione Python che calcola il fattoriale",
]


class SelfImprovement:
    def __init__(self, memory, llm_client, rag_searcher):
        self._mem = memory
        self._llm = llm_client
        self._rag = rag_searcher
        self._response_count = 0
        self._recent_ratings: list[int] = []
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
