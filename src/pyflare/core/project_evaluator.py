"""
Project Evaluator
=================
Evaluates a generated project across multiple metrics: Visual Quality, Gameplay Completeness,
Missing Features, Code Quality, Asset Quality, Performance, and Reliability.
Outputs a 0-100 score.
"""
from __future__ import annotations

from typing import Any, Dict, List
from .project_analyzer import ProjectAnalyzer

class ProjectEvaluator:
    def __init__(self, analyzer: ProjectAnalyzer):
        self.analyzer = analyzer

    def evaluate(self, project_path: str, prompt: str) -> Dict[str, Any]:
        """Evaluates a project and returns a detailed scoring report."""
        analysis = self.analyzer.analyze_project(project_path)
        
        # In a full implementation, this would use the ValidationWorker (LLM) to inspect code
        # For now, we use rule-based heuristics based on the analyzer's output.
        
        visual_quality = min(100, len(analysis.assets) * 10 + 40)
        gameplay_completeness = min(100, len(analysis.scripts) * 15 + 30)
        
        missing_features = []
        if len(analysis.scripts) < 2:
            missing_features.append("Core gameplay loop scripts")
        if len(analysis.scenes) == 0:
            missing_features.append("Main scene file")
            
        code_quality = 85 if len(analysis.scripts) > 0 else 0
        asset_quality = 80 if len(analysis.assets) > 0 else 0
        performance = 90 if analysis.complexity in ["Low", "Medium"] else 70
        reliability = 85
        
        # Calculate overall score (0-100)
        weights = {
            "visual": 0.2,
            "gameplay": 0.3,
            "code": 0.15,
            "asset": 0.15,
            "perf": 0.1,
            "rel": 0.1
        }
        
        overall_score = (
            visual_quality * weights["visual"] +
            gameplay_completeness * weights["gameplay"] +
            code_quality * weights["code"] +
            asset_quality * weights["asset"] +
            performance * weights["perf"] +
            reliability * weights["rel"]
        )
        
        # Penalty for missing features
        overall_score -= (len(missing_features) * 10)
        overall_score = max(0, min(100, overall_score))
        
        return {
            "score": round(overall_score, 1),
            "metrics": {
                "visual_quality": visual_quality,
                "gameplay_completeness": gameplay_completeness,
                "code_quality": code_quality,
                "asset_quality": asset_quality,
                "performance": performance,
                "reliability": reliability
            },
            "missing_features": missing_features,
            "problems": analysis.suggested_improvements + missing_features
        }
