from __future__ import annotations
from typing import Any, Dict, List
from .embedding_client import EmbeddingClient

class FailureMemory:
    """Stores known failures and recovery strategies in SQLite database using embeddings."""
    def __init__(self, db=None, provider_manager=None):
        self.db = db
        self._local_failures = []
        self.client = EmbeddingClient(db, provider_manager)

    def log_failure(self, error_or_prompt: str, context_or_error: Any = None, context: Dict[str, Any] = None):
        if context is not None:
            prompt = error_or_prompt
            error = context_or_error
            ctx = context
        else:
            prompt = "default_prompt"
            error = error_or_prompt
            ctx = context_or_error or {}

        if self.db and hasattr(self.db, "add_failure_memory"):
            self.db.add_failure_memory(prompt, error, ctx)
        else:
            self._local_failures.append({"prompt": prompt, "error": error, "context": ctx})

    def get_similar_failures(self, prompt: str, limit: int = 10, threshold: float = 0.3) -> List[Dict[str, Any]]:
        if self.db and hasattr(self.db, "query"):
            # Load all failures to compare
            rows = self.db.query("SELECT * FROM failure_memory")
            for r in rows:
                if "context" not in r and r.get("context_json"):
                    import json
                    try:
                        r["context"] = json.loads(r["context_json"])
                    except Exception:
                        r["context"] = {}
        else:
            rows = [f for f in self._local_failures]

        cleaned_prompts = []
        for row in rows:
            if isinstance(row, dict):
                r_prompt = row.get("prompt", "")
                cleaned_prompts.append((r_prompt, row))

        if not cleaned_prompts:
            return []

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

    def get_failures_for_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        # Return exact matches first
        exact = []
        if self.db and hasattr(self.db, "get_failure_memories"):
            exact = self.db.get_failure_memories(prompt)
        else:
            exact = [f for f in self._local_failures if f["prompt"] == prompt]
            
        if exact:
            return exact
            
        # Semantic fallback with lower threshold
        return self.get_similar_failures(prompt, limit=5, threshold=0.2)

