"""
Project Analyzer
================
Allows Jarvis to inspect old projects, understand scenes, inspect assets and scripts,
and suggest improvements or component reuse.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..logging_setup import get_logger

log = get_logger("project_analyzer")

@dataclass
class ProjectAnalysis:
    project_path: str
    scenes: List[str]
    assets: List[str]
    scripts: List[str]
    complexity: str
    suggested_improvements: List[str]
    reusable_components: List[str]


class ProjectAnalyzer:
    def __init__(self, db: Any):
        self.db = db

    def analyze_project(self, project_path: str) -> ProjectAnalysis:
        """Deep inspects a project directory to understand its structure and content."""
        log.info("ProjectAnalyzer: Inspecting %s", project_path)
        
        scenes = []
        assets = []
        scripts = []
        
        if os.path.exists(project_path):
            for root, _, files in os.walk(project_path):
                for f in files:
                    if f.endswith(".tscn"):
                        scenes.append(os.path.relpath(os.path.join(root, f), project_path))
                    elif f.endswith((".glb", ".gltf", ".fbx", ".obj", ".png", ".jpg")):
                        assets.append(os.path.relpath(os.path.join(root, f), project_path))
                    elif f.endswith((".gd", ".cs")):
                        scripts.append(os.path.relpath(os.path.join(root, f), project_path))
        
        # Analyze complexity
        complexity = "Low"
        if len(scenes) > 3 or len(scripts) > 5:
            complexity = "High"
        elif len(scenes) > 1 or len(scripts) > 2:
            complexity = "Medium"
            
        improvements = self._suggest_improvements(scenes, assets, scripts)
        components = self._identify_reusable_components(scenes, scripts)
        
        return ProjectAnalysis(
            project_path=project_path,
            scenes=scenes,
            assets=assets,
            scripts=scripts,
            complexity=complexity,
            suggested_improvements=improvements,
            reusable_components=components
        )
        
    def _suggest_improvements(self, scenes: List[str], assets: List[str], scripts: List[str]) -> List[str]:
        suggestions = []
        if len(scripts) == 0 and len(scenes) > 0:
            suggestions.append("Add central GameController script for state management.")
        if len(assets) > 20:
            suggestions.append("Consider packing textures or using a resource atlas.")
        return suggestions
        
    def _identify_reusable_components(self, scenes: List[str], scripts: List[str]) -> List[str]:
        reusable = []
        for scene in scenes:
            if "player" in scene.lower() or "character" in scene.lower():
                reusable.append(scene)
            if "ui" in scene.lower() or "menu" in scene.lower():
                reusable.append(scene)
        return reusable
