"""Template system - resolves a prompt to a scene template + asset slots."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class TemplateEngine:
    def __init__(self, templates: List[Dict[str, Any]]):
        self._templates = {t["id"]: t for t in templates}
        self._ordered = templates

    def get(self, template_id: str) -> Optional[Dict[str, Any]]:
        return self._templates.get(template_id)

    def resolve(self, prompt: str, forced_id: Optional[str] = None) -> Dict[str, Any]:
        if forced_id and forced_id in self._templates:
            return self._templates[forced_id]
        text = prompt.lower()
        best, best_score = None, 0
        for tpl in self._ordered:
            kws = tpl.get("keywords", [])
            score = sum(1 for kw in kws if kw in text)
            if score > best_score:
                best, best_score = tpl, score
        if best is not None:
            return best
        return self._templates.get("generic_scene", self._ordered[-1])

    def list(self) -> List[Dict[str, Any]]:
        return self._ordered