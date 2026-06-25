"""Jarvis Planner v1.

This is the first practical decision layer above the pipeline. It does not try
to be a general AI agent yet; it turns a prompt into a clear scene plan the
rest of AppSuite can execute and explain.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AssetNeed:
    role: str
    count: int
    search_terms: List[str]
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "count": self.count,
            "search_terms": self.search_terms,
            "required": self.required,
        }


@dataclass
class ScenePlan:
    prompt: str
    template_id: str
    template_name: str
    needed_assets: List[AssetNeed] = field(default_factory=list)
    strategy: Dict[str, Any] = field(default_factory=dict)
    workers_to_run: List[str] = field(default_factory=list)
    cache: Dict[str, Any] = field(default_factory=dict)
    resources: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "needed_assets": [asset.to_dict() for asset in self.needed_assets],
            "strategy": self.strategy,
            "workers_to_run": self.workers_to_run,
            "cache": self.cache,
            "resources": self.resources,
            "reasons": self.reasons,
        }


class JarvisPlanner:
    """Rule-based planner for Jarvis Core v1."""

    def __init__(self, templates, memory=None, registry=None, pipeline=None):
        self.templates = templates
        self.memory = memory
        self.registry = registry
        self.pipeline = pipeline

    def build(
        self,
        prompt: str,
        template_id: Optional[str] = None,
        resources: Optional[Dict[str, Any]] = None,
    ) -> ScenePlan:
        resources = resources or {}
        template = self._resolve_template(prompt, template_id)
        needed_assets = self._asset_needs(template)
        cache_info = self._cache_info(prompt)
        workers = self._workers(cache_info["use_cached_assets"])
        strategy = self._strategy(cache_info["use_cached_assets"])
        reasons = self._reasons(template, needed_assets, cache_info, resources)

        return ScenePlan(
            prompt=prompt,
            template_id=template["id"],
            template_name=template.get("name", template["id"]),
            needed_assets=needed_assets,
            strategy=strategy,
            workers_to_run=workers,
            cache=cache_info,
            resources=self._resource_summary(resources),
            reasons=reasons,
        )

    def _resolve_template(self, prompt: str, template_id: Optional[str]) -> Dict[str, Any]:
        if self.templates is None:
            return {"id": template_id or "generic_scene", "name": "Generic Scene", "asset_slots": []}
        return self.templates.resolve(prompt, template_id)

    def _asset_needs(self, template: Dict[str, Any]) -> List[AssetNeed]:
        needs = []
        for slot in template.get("asset_slots", []):
            role = str(slot.get("role", "prop"))
            terms = slot.get("search_terms") or [role]
            needs.append(
                AssetNeed(
                    role=role,
                    count=int(slot.get("count", 1)),
                    search_terms=[str(term) for term in terms],
                    required=bool(slot.get("required", True)),
                )
            )
        return needs

    def _cache_info(self, prompt: str) -> Dict[str, Any]:
        info = {
            "use_cached_assets": False,
            "cached_job_id": None,
            "cached_asset_count": 0,
            "prior_outcome": None,
        }
        if self.memory is None:
            return info

        prior = self.memory.recall_similar(prompt)
        if not prior:
            return info

        info["prior_outcome"] = prior.get("outcome")
        if prior.get("outcome") != "success":
            return info

        prior_job_id = prior.get("job_id")
        if not prior_job_id:
            return info

        assets = self.registry.for_job(prior_job_id) if self.registry else []
        valid_assets = [
            asset for asset in assets
            if asset.get("file_path") and Path(asset["file_path"]).exists()
        ]
        if valid_assets:
            info.update({
                "use_cached_assets": True,
                "cached_job_id": prior_job_id,
                "cached_asset_count": len(valid_assets),
            })
        return info

    def _workers(self, use_cached_assets: bool) -> List[str]:
        if self.pipeline is not None and getattr(self.pipeline, "stages", None):
            workers = [worker_key for _stage, worker_key in self.pipeline.stages]
        else:
            workers = ["internet", "analysis", "blender", "godot", "validation"]
        if use_cached_assets:
            workers = [worker for worker in workers if worker not in {"internet", "analysis"}]
        return workers

    def _strategy(self, use_cached_assets: bool) -> Dict[str, Any]:
        return {
            "reuse_cached_assets": use_cached_assets,
            "download_missing_assets": not use_cached_assets,
            "normalize_assets": True,
            "validate_assets": not use_cached_assets,
            "send_to_blender": True,
            "send_to_godot": True,
            "deploy_if_configured": True,
        }

    def _reasons(
        self,
        template: Dict[str, Any],
        needs: List[AssetNeed],
        cache_info: Dict[str, Any],
        resources: Dict[str, Any],
    ) -> List[str]:
        reasons = [
            f"Template resolved to '{template['id']}'",
            f"Planning {sum(asset.count for asset in needs)} assets across {len(needs)} roles",
        ]
        if cache_info["use_cached_assets"]:
            job_id = str(cache_info["cached_job_id"])
            reasons.append(
                f"Reusing {cache_info['cached_asset_count']} cached assets from job {job_id[:8]}"
            )
            reasons.append("Skipping internet + analysis (cached assets)")
        elif cache_info.get("prior_outcome"):
            reasons.append(f"Prior similar prompt outcome was {cache_info['prior_outcome']}; full run planned")
        else:
            reasons.append("No reusable cached result found; full asset acquisition planned")

        cpu = resources.get("cpu_percent")
        ram = resources.get("ram_percent")
        if cpu is not None and cpu > 75:
            reasons.append(f"WARNING: CPU at {cpu}% - job may be slow")
        if ram is not None and ram > 75:
            reasons.append(f"WARNING: RAM at {ram}%")
        return reasons

    def _resource_summary(self, resources: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "cpu_percent": resources.get("cpu_percent"),
            "ram_percent": resources.get("ram_percent"),
            "disk_free_gb": (resources.get("disk") or {}).get("free_gb"),
            "gpu_available": (resources.get("gpu") or {}).get("available", False),
        }
