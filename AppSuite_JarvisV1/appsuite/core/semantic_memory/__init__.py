from __future__ import annotations
import math
import time
import json
from typing import Any, Dict, List, Optional
from ...db import Database

from .worker_memory import WorkerMemory
from .agent_memory import AgentMemory
from .failure_memory import FailureMemory
from .strategy_memory import StrategyMemory
from .procedural_memory import ProceduralMemory
from .embedding_client import EmbeddingClient

class SemanticMemory:
    """Unified Semantic Memory System Facade with advanced capabilities."""
    
    def __init__(self, db: Database, provider_manager: Optional[Any] = None):
        self.db = db
        self.provider_manager = provider_manager
        self.client = EmbeddingClient(db, provider_manager)
        self.worker = WorkerMemory(db, self.client)
        self.agent = AgentMemory()
        self.failure = FailureMemory(db, provider_manager)
        self.strategy = StrategyMemory(db, provider_manager)
        self.procedural = ProceduralMemory(db, provider_manager)
        
        # Local episodic and project memories as fallbacks
        self._local_episodic: List[Dict[str, Any]] = []
        self._local_projects: List[Dict[str, Any]] = []

    # Episodic memory methods
    def store_episode(self, job_id: str, prompt: str, events: List[str], outcome: str, metadata: Optional[Dict[str, Any]] = None):
        """Record a distinct experience episode."""
        summary = {
            "events": events,
            "metadata": metadata or {},
            "timestamp": time.time()
        }
        self.remember(job_id, prompt, metadata.get("template_id", "generic_scene") if metadata else "generic_scene", outcome, summary, metadata)
        
        # In-memory backup
        self._local_episodic.append({
            "job_id": job_id,
            "prompt": prompt,
            "outcome": outcome,
            "summary": summary,
            "created_at": time.time()
        })

    def recall_episodes(self, prompt: str, limit: int = 5, decay_rate: float = 0.05) -> List[Dict[str, Any]]:
        """Recalls episodes using semantic similarity and exponential time decay."""
        query_emb = self.client.get_embedding(prompt)
        
        # Pull from db memory
        rows = []
        if self.db:
            try:
                rows = self.db.query("SELECT * FROM memory")
            except Exception:
                pass
        
        if not rows:
            rows = [{"prompt": e["prompt"], "created_at": e["created_at"], "summary_json": json.dumps(e["summary"]), "outcome": e["outcome"]} for e in self._local_episodic]
            
        scored = []
        now = time.time()
        
        for row in rows:
            text = row.get("prompt", "")
            cand_emb = self.client.get_embedding(text)
            sim = EmbeddingClient.cosine_similarity(query_emb, cand_emb)
            
            # Memory decay calculation: similarity * exp(-decay_rate * age_in_days)
            age_days = (now - row.get("created_at", now)) / 86400.0
            decay_factor = math.exp(-decay_rate * age_days)
            final_score = sim * decay_factor
            
            row_copy = dict(row)
            row_copy["similarity_score"] = sim
            row_copy["decay_factor"] = decay_factor
            row_copy["ranking_score"] = final_score
            scored.append(row_copy)
            
        scored.sort(key=lambda x: x["ranking_score"], reverse=True)
        return scored[:limit]

    # Project memory methods
    def store_project_state(self, project_id: str, plan_state: Dict[str, Any]):
        """Record project plan state."""
        if self.db:
            try:
                self.db.add_world_model_entry(project_id, "project_plan_state", plan_state)
            except Exception:
                pass
        self._local_projects.append({
            "project_id": project_id,
            "plan_state": plan_state,
            "updated_at": time.time()
        })

    def get_project_state(self, project_id: str) -> Optional[Dict[str, Any]]:
        if self.db:
            try:
                rows = self.db.get_world_model_entries(project_id)
                for r in rows:
                    if r.get("key") == "project_plan_state":
                        return r.get("value")
            except Exception:
                pass
        
        for p in reversed(self._local_projects):
            if p["project_id"] == project_id:
                return p["plan_state"]
        return None

    # Memory consolidation & compression methods
    def consolidate_memories(self):
        """Consolidate/merge similar memories to prevent clutter."""
        # For simplicity, we prune highly redundant/low-quality items from strategy & failure memory
        if not self.db:
            return
        
        try:
            # Consolidate strategy memory
            rows = self.db.query("SELECT * FROM strategy_memory ORDER BY created_at DESC")
            # If strategy count is very high, keep only unique outcomes or high-scoring strategies
            if len(rows) > 100:
                seen = set()
                to_delete = []
                for r in rows:
                    key = (r.get("prompt"), r.get("outcome"))
                    if key in seen:
                        to_delete.append(r.get("id"))
                    else:
                        seen.add(key)
                if to_delete:
                    ids_str = ",".join(str(i) for i in to_delete[:50])
                    self.db.execute(f"DELETE FROM strategy_memory WHERE id IN ({ids_str})")
        except Exception:
            pass

    def compress_old_memories(self, age_days_threshold: float = 30.0):
        """Compress/summarize memories older than threshold days."""
        if not self.db:
            return
        now = time.time()
        sec_threshold = age_days_threshold * 86400.0
        
        try:
            # Find old job events or job results and compress/remove
            cutoff = now - sec_threshold
            self.db.execute("DELETE FROM job_events WHERE created_at < ?", (cutoff,))
        except Exception:
            pass

    # Delegate existing interface to maintain backward compatibility
    def remember(self, *args, **kwargs):
        return self.worker.remember(*args, **kwargs)

    def recall(self, *args, **kwargs):
        return self.worker.recall(*args, **kwargs)

    def recall_similar(self, *args, **kwargs):
        return self.worker.recall_similar(*args, **kwargs)

    def store_agent_strategy(self, *args, **kwargs):
        return self.agent.store_agent_strategy(*args, **kwargs)

    def recall_agent_strategy(self, *args, **kwargs):
        return self.agent.recall_agent_strategy(*args, **kwargs)

    # --- Autonomous Active Learning -----------------------------------------
    def discover_and_update_strategies(self) -> Dict[str, Any]:
        """Actively discovers recurring failures/successes, refines strategy records, and prunes ineffective rules."""
        stats = {
            "failures_discovered": 0,
            "successes_consolidated": 0,
            "strategies_retired": 0
        }
        if not self.db:
            return stats
            
        try:
            # 1. Discover recurring failures (group by error message prefix)
            fail_rows = self.db.query("SELECT error, count(*) as cnt FROM failure_memory GROUP BY error HAVING cnt >= 2")
            for row in fail_rows:
                err = row["error"]
                stats["failures_discovered"] += 1
                # Generate avoidance strategy and insert into strategy_memory
                avoidance_strategy = {
                    "rule": f"Avoid matching failure trigger: {err[:50]}",
                    "action": "Fallback to lower complexity template and prioritize local validators",
                    "preventive": True
                }
                self.db.add_strategy_memory(
                    prompt=f"Trigger recovery for error: {err[:60]}",
                    strategy=avoidance_strategy,
                    outcome="success"
                )
                
            # 2. Discover recurring successes and consolidate into procedural recipes
            success_rows = self.db.query(
                "SELECT template_id, prompt, count(*) as cnt FROM memory WHERE outcome = 'success' GROUP BY template_id HAVING cnt >= 2"
            )
            for row in success_rows:
                stats["successes_consolidated"] += 1
                recipe = {
                    "template_id": row["template_id"],
                    "proven_prompt": row["prompt"],
                    "confidence_multiplier": 1.10
                }
                self.db.add_procedural_memory(
                    task_type=row["template_id"],
                    recipe=recipe,
                    outcome="success"
                )
                
            # 3. Retire ineffective strategies (strategies linked to failed outcomes)
            failed_strategies = self.db.query("SELECT id FROM strategy_memory WHERE outcome = 'failure'")
            for row in failed_strategies:
                self.db.execute("DELETE FROM strategy_memory WHERE id = ?", (row["id"],))
                stats["strategies_retired"] += 1
                
        except Exception:
            pass
            
        return stats

