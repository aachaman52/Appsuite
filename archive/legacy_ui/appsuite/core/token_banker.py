"""Token Banker System - tracks usage, cost, and enforces AI provider budgets."""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from ..logging_setup import get_logger

log = get_logger("token_banker")

class TokenBanker:
    """Manages tracking token usage and cost limits across providers."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._lock = threading.Lock()
        
        # Track usage in memory (in a real app, this would be persisted to DB)
        self._usage: Dict[str, Dict[str, float]] = {}
        
        # Global daily limit (e.g. max $1.00 per day across all providers)
        self.daily_budget = float(config.get("daily_budget_usd", 1.0))
        self.current_spend = 0.0

    def get_provider_usage(self, provider_id: str) -> Dict[str, float]:
        with self._lock:
            if provider_id not in self._usage:
                self._usage[provider_id] = {
                    "tokens_consumed": 0.0,
                    "cost_usd": 0.0
                }
            return dict(self._usage[provider_id])

    def consume(self, provider_id: str, tokens: int, cost_per_1k: float) -> None:
        """Record token consumption and update budgets."""
        cost = (tokens / 1000.0) * cost_per_1k
        with self._lock:
            if provider_id not in self._usage:
                self._usage[provider_id] = {"tokens_consumed": 0.0, "cost_usd": 0.0}
            
            self._usage[provider_id]["tokens_consumed"] += tokens
            self._usage[provider_id]["cost_usd"] += cost
            self.current_spend += cost
            
            log.info("TokenBanker: Consumed %d tokens from %s (Cost: $%.4f)", tokens, provider_id, cost)

    def can_execute(self, provider: Dict[str, Any], estimated_tokens: int = 1000) -> bool:
        """
        Check if the provider can execute the task given the current budget.
        Returns True if within budget, False if budget exceeded.
        """
        provider_id = provider.get("id", "unknown")
        cost_per_1k = float(provider.get("cost_per_1k_tokens", 0.0))
        
        estimated_cost = (estimated_tokens / 1000.0) * cost_per_1k
        
        with self._lock:
            if self.current_spend + estimated_cost > self.daily_budget:
                log.warning(
                    "TokenBanker: Budget exceeded! Cannot execute %s. Estimated Cost: $%.4f. Total Spend: $%.4f / $%.2f",
                    provider_id, estimated_cost, self.current_spend, self.daily_budget
                )
                return False
                
        return True
