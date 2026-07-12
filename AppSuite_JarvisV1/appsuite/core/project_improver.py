"""
Project Improver
================
Interprets problems found by the Project Evaluator and generates a repair/improvement plan.
Capabilities:
- add missing assets
- replace poor assets
- add missing scripts
- reorganize project structure
- improve templates
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..logging_setup import get_logger

log = get_logger("project_improver")

class ProjectImprover:
    def __init__(self, db: Any):
        self.db = db

    def generate_improvement_plan(self, evaluation: Dict[str, Any], prompt: str) -> List[Dict[str, Any]]:
        """
        Reads the evaluation report and schedules worker tasks to fix the problems.
        Returns a list of tasks.
        """
        plan = []
        problems = evaluation.get("problems", [])
        
        log.info("ProjectImprover: Generating improvement plan for %d problems.", len(problems))
        
        for problem in problems:
            problem_lower = problem.lower()
            
            # Capability: add missing scripts
            if "script" in problem_lower or "gameplay" in problem_lower:
                plan.append({
                    "action": "add_missing_scripts",
                    "worker": "code",
                    "reasoning": f"Addressing: {problem}"
                })
                
            # Capability: add/replace assets
            elif "asset" in problem_lower or "texture" in problem_lower or "model" in problem_lower:
                plan.append({
                    "action": "replace_poor_assets" if "poor" in problem_lower else "add_missing_assets",
                    "worker": "asset",
                    "reasoning": f"Addressing: {problem}"
                })
                
            # Capability: reorganize project structure
            elif "organize" in problem_lower or "structure" in problem_lower:
                plan.append({
                    "action": "reorganize_project_structure",
                    "worker": "godot",
                    "reasoning": f"Addressing: {problem}"
                })
                
            # Capability: improve templates
            elif "template" in problem_lower or "scene" in problem_lower:
                plan.append({
                    "action": "improve_templates",
                    "worker": "validation", # or template engine
                    "reasoning": f"Addressing: {problem}"
                })
                
        # Deduplicate actions
        unique_plan = {f"{t['action']}_{t['worker']}": t for t in plan}.values()
        
        # Save improvements into memory (stub)
        if hasattr(self.db, "add_event"):
            try:
                self.db.add_event(
                    "IMPROVE", 
                    f"Generated {len(unique_plan)} improvements for score {evaluation['score']}", 
                    level="info"
                )
            except Exception:
                pass
                
        return list(unique_plan)
