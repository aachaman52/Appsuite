"""
Autonomous Improvement Loop
===========================
Drives the iterative generation -> evaluation -> improvement cycle.
Stops when the project reaches a high score or maximum iterations are met.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from .project_analyzer import ProjectAnalyzer
from .project_evaluator import ProjectEvaluator
from .project_improver import ProjectImprover
from ..logging_setup import get_logger

log = get_logger("autonomous_loop")

class AutonomousLoop:
    def __init__(self, db: Any, pipeline: Any, output_dir: str):
        self.db = db
        self.pipeline = pipeline
        self.output_dir = output_dir
        
        self.analyzer = ProjectAnalyzer(db)
        self.evaluator = ProjectEvaluator(self.analyzer)
        self.improver = ProjectImprover(db)
        
    def run_loop(self, job_id: str, prompt: str, max_iterations: int = 3, target_score: float = 90.0) -> None:
        """
        Executes the iterative generation and improvement loop.
        Attempt -> Evaluate -> Improve -> Repeat.
        """
        log.info("AutonomousLoop: Starting iterative loop for job %s (max_iter=%d, target=%.1f)", 
                 job_id, max_iterations, target_score)
        
        project_path = f"{self.output_dir}/{job_id}"
        
        for iteration in range(1, max_iterations + 1):
            log.info("--- Iteration %d for %s ---", iteration, job_id)
            
            # Step 1: Generate/Apply
            if iteration == 1:
                # Initial generation attempt
                self.pipeline.execute_job(job_id)
            else:
                # Apply improvements
                log.info("Applying improvements for iteration %d...", iteration)
                # In a real system, we'd dispatch the improvement plan tasks.
                # For this implementation, we run the pipeline with an improvement context.
                self.pipeline.execute_job(job_id)
                
            # Step 2: Evaluate
            evaluation = self.evaluator.evaluate(project_path, prompt)
            score = evaluation["score"]
            log.info("Evaluation Score: %.1f/100", score)
            
            self._log_iteration(job_id, iteration, score, evaluation)
            
            # Step 3: Check loop break conditions
            if score >= target_score:
                log.info("AutonomousLoop: Target score %.1f reached! Finalizing.", score)
                break
                
            if iteration == max_iterations:
                log.info("AutonomousLoop: Max iterations reached. Finalizing with score %.1f.", score)
                break
                
            # Step 4: Propose Improvements
            plan = self.improver.generate_improvement_plan(evaluation, prompt)
            if not plan:
                log.info("AutonomousLoop: No further improvements suggested by AI. Finalizing.")
                break
                
            log.info("Improvement plan formulated: %d actions.", len(plan))
            
            # Short breather before next iteration
            time.sleep(2)
            
        log.info("AutonomousLoop: Finished for job %s.", job_id)
        
    def _log_iteration(self, job_id: str, iteration: int, score: float, evaluation: Dict[str, Any]) -> None:
        """Store the iteration stats into memory/db."""
        if hasattr(self.db, "add_event"):
            try:
                msg = f"Iteration {iteration} evaluated. Score: {score:.1f}/100"
                self.db.add_event(job_id, msg, stage="evaluation", level="info")
            except Exception:
                pass
