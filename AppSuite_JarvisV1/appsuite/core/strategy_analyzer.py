"""
Strategy Analyzer (Execution Knowledge Graph)
=============================================
Analyzes complete execution graphs to determine the best full-pipeline strategies.
"""
from typing import Any, Dict, List
import json

class StrategyAnalyzer:
    def __init__(self, db: Any):
        self.db = db

    def _get_graphs(self) -> List[Dict[str, Any]]:
        return self.db.get_execution_graphs(limit=5000)

    def highest_success_rate_strategy(self) -> Dict[str, Any]:
        """Which planner strategy has highest success rate?"""
        graphs = self._get_graphs()
        stats = {}
        for g in graphs:
            strat = g.get("planner_strategy", "unknown")
            if strat not in stats:
                stats[strat] = {"runs": 0, "successes": 0}
            stats[strat]["runs"] += 1
            if g.get("final_success"):
                stats[strat]["successes"] += 1
                
        best_strat = None
        best_rate = -1.0
        for strat, data in stats.items():
            rate = data["successes"] / max(1, data["runs"])
            if rate > best_rate and data["runs"] >= 3: # min threshold
                best_rate = rate
                best_strat = strat
                
        # Fallback if no strategy has 3 runs
        if not best_strat and stats:
            for strat, data in stats.items():
                rate = data["successes"] / max(1, data["runs"])
                if rate > best_rate:
                    best_rate = rate
                    best_strat = strat
                    
        return {"strategy": best_strat, "success_rate": best_rate}

    def best_asset_provider_for_genre(self, genre: str) -> str:
        """Which asset provider works best for a specific genre (e.g., FPS)?"""
        graphs = self._get_graphs()
        stats = {}
        for g in graphs:
            if genre.lower() in (g.get("genre") or "").lower() or genre.lower() in (g.get("prompt") or "").lower():
                prov = g.get("asset_provider", "unknown")
                if prov not in stats:
                    stats[prov] = {"runs": 0, "successes": 0}
                stats[prov]["runs"] += 1
                if g.get("final_success"):
                    stats[prov]["successes"] += 1
                    
        best_prov = "kenney" # safe default
        best_rate = -1.0
        for prov, data in stats.items():
            rate = data["successes"] / max(1, data["runs"])
            if rate > best_rate:
                best_rate = rate
                best_prov = prov
        return best_prov

    def best_repair_action(self) -> str:
        """Which repair action improves validation most?"""
        graphs = self._get_graphs()
        stats = {}
        for g in graphs:
            repairs = g.get("repair_actions", [])
            for r in repairs:
                if r not in stats:
                    stats[r] = {"runs": 0, "val_sum": 0.0}
                stats[r]["runs"] += 1
                stats[r]["val_sum"] += g.get("validation_score", 0.0)
                
        best_repair = None
        best_avg = -1.0
        for r, data in stats.items():
            avg = data["val_sum"] / max(1, data["runs"])
            if avg > best_avg:
                best_avg = avg
                best_repair = r
        return best_repair or "create_import_files"

    def failing_worker_combinations(self) -> List[tuple]:
        """Which worker combinations fail together?"""
        graphs = self._get_graphs()
        combo_fails = {}
        for g in graphs:
            if not g.get("final_success"):
                combo = tuple(sorted(g.get("workers_used", [])))
                combo_fails[combo] = combo_fails.get(combo, 0) + 1
        # Sort by most frequent failures
        return sorted(combo_fails.items(), key=lambda x: x[1], reverse=True)

    def average_execution_time(self, strategy: str) -> float:
        """Average execution time per strategy."""
        graphs = self._get_graphs()
        times = [g.get("execution_time", 0.0) for g in graphs if g.get("planner_strategy") == strategy]
        if not times:
            return 0.0
        return sum(times) / len(times)

    def confidence_score(self, strategy: str) -> float:
        """Confidence score for every strategy."""
        graphs = self._get_graphs()
        runs = 0
        successes = 0
        for g in graphs:
            if g.get("planner_strategy") == strategy:
                runs += 1
                if g.get("final_success"):
                    successes += 1
        if runs == 0:
            return 0.5 # Unknown
        return successes / runs
