from __future__ import annotations
from typing import Any, Dict, List
from .embedding_client import EmbeddingClient

class StrategyMemory:
    """Stores high-level planning strategies from JarvisBrain in SQLite using embeddings."""
    def __init__(self, db=None, provider_manager=None):
        self.db = db
        self._local_strategies = []
        self.client = EmbeddingClient(db, provider_manager)

    def add_strategy(self, prompt: str, strategy: Dict[str, Any], outcome: str = "success"):
        if self.db and hasattr(self.db, "add_strategy_memory"):
            self.db.add_strategy_memory(prompt, strategy, outcome)
        else:
            self._local_strategies.append({"prompt": prompt, "strategy": strategy, "outcome": outcome})

    def store_strategy(self, strategy: Dict[str, Any]):
        prompt = strategy.get("prompt", "default_prompt")
        self.add_strategy(prompt, strategy, "success")

    def get_similar_strategies(self, prompt: str, limit: int = 10, threshold: float = 0.3) -> List[Dict[str, Any]]:
        if self.db and hasattr(self.db, "query"):
            rows = self.db.query("SELECT * FROM strategy_memory")
        else:
            rows = [s for s in self._local_strategies]

        cleaned_prompts = []
        for row in rows:
            if isinstance(row, dict):
                r_prompt = row.get("prompt", "")
                # If strategy_json exists, parse it
                if "strategy" not in row and row.get("strategy_json"):
                    import json
                    try:
                        row["strategy"] = json.loads(row["strategy_json"])
                    except Exception:
                        row["strategy"] = {}
                cleaned_prompts.append((r_prompt, row))

        if not cleaned_prompts:
            return []

        # Get query embedding
        query_emb = self.client.get_embedding(prompt)
        scored = []
        
        for text, row in cleaned_prompts:
            candidate_emb = self.client.get_embedding(text)
            score = EmbeddingClient.cosine_similarity(query_emb, candidate_emb)
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
        # Let's perform semantic retrieval if no exact match is found, or return exact match first
        exact = []
        if self.db and hasattr(self.db, "get_strategy_memories"):
            exact = self.db.get_strategy_memories(prompt)
        else:
            exact = [s for s in self._local_strategies if s["prompt"] == prompt]
        
        if exact:
            return exact
            
        # Semantic fallback with lower threshold
        return self.get_similar_strategies(prompt, limit=5, threshold=0.2)

