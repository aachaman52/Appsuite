"""Asset Registry - stores asset IDs, metadata, hashes, sources, dependencies."""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..db import Database
from ..logging_setup import get_logger

log = get_logger("asset_registry")


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class AssetRegistry:
    def __init__(self, db: Database):
        self.db = db

    def register(
        self,
        job_id: str,
        role: str,
        name: str,
        source: str,
        file_path: Path,
        source_url: Optional[str] = None,
        fmt: Optional[str] = None,
        quality_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        file_hash = hash_file(file_path) if file_path.exists() else None
        existing = self.db.get_asset_by_hash(file_hash) if file_hash else None
        asset_id = existing["id"] if existing else str(uuid.uuid4())
        asset = {
            "id": asset_id,
            "job_id": job_id,
            "role": role,
            "name": name,
            "source": source,
            "source_url": source_url,
            "file_path": str(file_path),
            "file_hash": file_hash,
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
            "format": fmt or file_path.suffix.lstrip("."),
            "quality_score": quality_score,
            "metadata": metadata or {},
            "dependencies": dependencies or [],
        }
        self.db.add_asset(asset)
        if existing:
            log.info("Asset cache hit for hash %s (%s)", file_hash[:12], name)
            asset["cache_hit"] = True
        return asset

    def cached_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        return self.db.get_asset_by_hash(file_hash)

    def for_job(self, job_id: str) -> List[Dict[str, Any]]:
        return self.db.get_assets_for_job(job_id)