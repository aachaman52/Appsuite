"""
Website Memory
==============
Remembers interactions with websites (urls visited, extraction schemas, 
authentication status, and rate limit states) for reuse.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ...db import Database

class WebsiteMemory:
    def __init__(self, db: Database):
        self.db = db
        self._local_visits: Dict[str, Any] = {}

    def record_visit(self, url: str, action: str, outcome: str, metadata: Dict[str, Any] = None):
        """Records a website visit or interaction."""
        self._local_visits[url] = {
            "action": action,
            "outcome": outcome,
            "metadata": metadata or {},
            "timestamp": time.time()
        }
        # In a full implementation, this would save to a website_memory table.
        if self.db and hasattr(self.db, "execute"):
            try:
                # Fallback to world_model for now if table doesn't exist
                self.db.add_world_model_entry("browser_agent", f"visit:{url}", self._local_visits[url])
            except Exception:
                pass

    def get_best_strategy(self, domain: str) -> Optional[Dict[str, Any]]:
        """Returns the best interaction strategy/schema known for a domain."""
        return None

    def record_rate_limit(self, domain: str, retry_after_secs: float):
        """Records a 429 rate limit hit for a domain."""
        self._local_visits[f"ratelimit:{domain}"] = {
            "retry_after": time.time() + retry_after_secs
        }
        
    def is_rate_limited(self, domain: str) -> bool:
        rl = self._local_visits.get(f"ratelimit:{domain}")
        if rl and rl["retry_after"] > time.time():
            return True
        return False
