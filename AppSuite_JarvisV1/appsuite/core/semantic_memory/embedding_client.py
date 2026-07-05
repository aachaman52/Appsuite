from __future__ import annotations
import os
import json
import requests
import hashlib
from typing import Any, List, Optional
from ...logging_setup import get_logger

log = get_logger("semantic_memory.embedding")

class EmbeddingClient:
    """Retrieves text embeddings from NVIDIA NIM or uses a local fallback vector."""
    
    def __init__(self, db: Optional[Any] = None, provider_manager: Optional[Any] = None):
        self.db = db
        self.providers = provider_manager

    def get_embedding(self, text: str) -> List[float]:
        if not text:
            return [0.0] * 512

        # 1. Try to check DB cache
        if self.db and hasattr(self.db, "get_cached_embedding"):
            cached = self.db.get_cached_embedding(text)
            if cached:
                return cached

        # 2. Try NVIDIA NIM Embeddings API
        api_key = os.environ.get("NVIDIA_API_KEY")
        base_url = "https://integrate.api.nvidia.com/v1"
        model = "nvidia/nv-embed-v1"

        # Check if providers list NVIDIA NIM
        if self.providers:
            nim_p = next((p for p in self.providers._providers if p.get("id") == "nvidia-nim"), None)
            if nim_p and nim_p.get("enabled"):
                base_url = nim_p.get("base_url") or base_url
                api_key = os.environ.get(nim_p.get("api_key_env") or "NVIDIA_API_KEY") or api_key
                model = nim_p.get("model") or model

        if api_key:
            try:
                url = f"{base_url}/embeddings"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "input": [text],
                    "model": model
                }
                log.info("Requesting NIM embeddings for text: %r", text[:60])
                r = requests.post(url, json=payload, headers=headers, timeout=10.0)
                r.raise_for_status()
                res = r.json()
                
                # Format: {"data": [{"embedding": [...]}]} or similar depending on spec
                # Let's support both formats (our MCP return was a list of embeddings under "embeddings")
                embedding = None
                if "embeddings" in res and res["embeddings"]:
                    embedding = res["embeddings"][0].get("embedding")
                elif "data" in res and res["data"]:
                    embedding = res["data"][0].get("embedding")
                
                if embedding:
                    # Cache the embedding in DB
                    if self.db and hasattr(self.db, "cache_embedding"):
                        try:
                            self.db.cache_embedding(text, embedding)
                        except Exception as e:
                            log.warning("Failed to cache embedding: %s", e)
                    return embedding
            except Exception as e:
                log.warning("NIM embedding request failed: %s. Falling back to local vector.", e)

        # 3. Local Fallback: Deterministic 512-dimensional vector
        embedding = self._local_fallback_vector(text)
        
        # Cache local fallback too to save CPU time on tokenization
        if self.db and hasattr(self.db, "cache_embedding"):
            try:
                self.db.cache_embedding(text, embedding)
            except Exception:
                pass
                
        return embedding

    def _local_fallback_vector(self, text: str) -> List[float]:
        import re
        tokens = re.findall(r"\w+", text.lower())
        vec = [0.0] * 512
        if not tokens:
            return vec
        for t in tokens:
            # Deterministic hash of token to index in [0, 511]
            idx = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16) % 512
            vec[idx] += 1.0
        
        # L2 Normalize
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0.0:
            vec = [x / norm for x in vec]
        return vec

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
