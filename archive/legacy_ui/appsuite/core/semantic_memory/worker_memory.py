from __future__ import annotations
import difflib
from typing import Any, Dict, List, Optional
from ...db import Database
from .embedding_client import EmbeddingClient

class WorkerMemory:
    def __init__(self, db: Database, client: Optional[EmbeddingClient] = None):
        self.db = db
        self.client = client or EmbeddingClient(db)

    def _compute_similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def remember(
        self,
        job_id: str,
        prompt: str,
        template_id: str,
        outcome: str,
        summary: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        self.db.add_memory(job_id, prompt, template_id, outcome, summary)
        if metadata:
            self.db.update_job(job_id, metadata=metadata)

    def recall(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.db.recall_memory(limit)

    def recall_similar(self, prompt: str, threshold: float = 0.6) -> Optional[Dict[str, Any]]:
        memories = self.recall(limit=100)
        best_match = None
        best_score = 0.0

        # Try semantic embedding similarity first
        try:
            query_emb = self.client.get_embedding(prompt)
            for mem in memories:
                mem_prompt = mem.get("prompt", "")
                cand_emb = self.client.get_embedding(mem_prompt)
                score = EmbeddingClient.cosine_similarity(query_emb, cand_emb)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = mem
        except Exception:
            # Fallback to difflib edit distance similarity
            for mem in memories:
                mem_prompt = mem.get("prompt", "")
                score = self._compute_similarity(prompt, mem_prompt)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = mem

        if best_match:
            result = dict(best_match)
            result["similarity_score"] = best_score
            return result
        return None
