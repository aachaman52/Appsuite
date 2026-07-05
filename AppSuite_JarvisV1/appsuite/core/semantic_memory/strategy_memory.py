from __future__ import annotations
import math
from typing import Any, Dict, List

class StrategyMemory:
    """Stores high-level planning strategies from JarvisBrain in SQLite."""
    def __init__(self, db=None):
        self.db = db
        self._local_strategies = []

    def add_strategy(self, prompt: str, strategy: Dict[str, Any], outcome: str = "success"):
        if self.db and hasattr(self.db, "add_strategy_memory"):
            self.db.add_strategy_memory(prompt, strategy, outcome)
        else:
            self._local_strategies.append({"prompt": prompt, "strategy": strategy, "outcome": outcome})

    def store_strategy(self, strategy: Dict[str, Any]):
        prompt = strategy.get("prompt", "default_prompt")
        self.add_strategy(prompt, strategy, "success")

    def _tokenize(self, text: str) -> Dict[str, int]:
        import re
        tokens = re.findall(r"\w+", text.lower())
        counts: Dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        return counts

    def _tfidf_vector(self, term_counts: Dict[str, int], idf: Dict[str, float]) -> Dict[str, float]:
        return {term: count * idf.get(term, 0.0) for term, count in term_counts.items()}

    def _cosine_similarity(self, vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        dot = sum(vec_a.get(k, 0.0) * vec_b.get(k, 0.0) for k in vec_a)
        norm_a = sum(v * v for v in vec_a.values()) ** 0.5
        norm_b = sum(v * v for v in vec_b.values()) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def get_similar_strategies(self, prompt: str, limit: int = 10, threshold: float = 0.3) -> List[Dict[str, Any]]:
        if self.db and hasattr(self.db, "query"):
            rows = self.db.query("SELECT * FROM strategy_memory")
        else:
            rows = [s for s in self._local_strategies]

        cleaned_prompts = []
        for row in rows:
            if isinstance(row, dict):
                cleaned_prompts.append((row.get("prompt", ""), row))

        if not cleaned_prompts:
            return []

        all_tokens = []
        for text, _ in cleaned_prompts:
            all_tokens.extend(self._tokenize(text).keys())
        idf = {}
        total_docs = len(cleaned_prompts)
        for token in set(all_tokens):
            doc_freq = sum(1 for text, _ in cleaned_prompts if token in self._tokenize(text))
            idf[token] = math.log((total_docs / (1 + doc_freq)) + 1)

        target_vec = self._tfidf_vector(self._tokenize(prompt), idf)
        scored = []
        for text, row in cleaned_prompts:
            candidate_vec = self._tfidf_vector(self._tokenize(text), idf)
            score = self._cosine_similarity(target_vec, candidate_vec)
            if score >= threshold:
                row_copy = dict(row)
                row_copy["similarity_score"] = score
                scored.append(row_copy)

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored[:limit]

    # Compatibility method for the original codebase
    def add_strategy_compat(self, strategy: Dict[str, Any]):
        self.store_strategy(strategy)

    def get_strategies_for_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        if self.db and hasattr(self.db, "get_strategy_memories"):
            return self.db.get_strategy_memories(prompt)
        return [s for s in self._local_strategies if s["prompt"] == prompt]
