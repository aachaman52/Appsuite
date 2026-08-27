from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from .job_state import UnifiedJobState
from ..logging_setup import get_logger

log = get_logger("engine.checkpoint")

class CheckpointManager:
    def __init__(self, directory: Optional[Path] = None):
        self.directory = directory or Path(".")

    def _get_path(self, job_id: str) -> Path:
        return self.directory / f"{job_id}_checkpoint.json"

    def save(self, job_id: str, completed: Set[str], pending: Set[str], state: UnifiedJobState) -> str:
        path = self._get_path(job_id)
        ckpt_data = {
            "job_id": job_id,
            "completed": list(completed),
            "pending": list(pending),
            "state": state.to_dict() if hasattr(state, "to_dict") else state,
            "timestamp": os.path.getmtime(path) if path.exists() else 0.0 # Will be updated after write
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ckpt_data, f, indent=2)
            log.info(f"Saved checkpoint for job {job_id} at {path}")
        except Exception as e:
            log.error(f"Failed to save checkpoint: {e}")
        return str(path)

    def load(self, job_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_path(job_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            log.info(f"Loaded checkpoint for job {job_id} from {path}")
            return data
        except Exception as e:
            log.error(f"Failed to load checkpoint: {e}")
            return None

    def cleanup(self, job_id: str) -> None:
        path = self._get_path(job_id)
        if path.exists():
            try:
                path.unlink()
                log.info(f"Cleaned up checkpoint for job {job_id}")
            except Exception as e:
                log.error(f"Failed to cleanup checkpoint: {e}")
