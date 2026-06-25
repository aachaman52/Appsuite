"""Example AppSuite plugin.

Plugins expose `register(context)` and optional lifecycle hooks such as
`on_stage_complete(job, stage, state, output)`.
"""
from __future__ import annotations

from typing import Any, Dict


def register(context: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": "example_plugin", "version": "1.0.0",
            "description": "Logs pipeline stage completions."}


def on_stage_complete(job: Dict[str, Any], stage: str, state: Dict[str, Any],
                      output: Dict[str, Any]) -> None:
    # Hook fires after each pipeline stage. Extend this to post-process assets,
    # push notifications, upload artifacts, etc.
    print(f"[example_plugin] job={job['id'][:8]} stage={stage} -> {list(output.keys())}")