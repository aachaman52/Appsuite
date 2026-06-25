"""Graph Nodes wrapping existing workers."""
from __future__ import annotations
import time
from typing import Any, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from pathlib import Path

from .state import GraphState
from ..core.state import WorkerResult, WorkerStatus
from ..core.health import WorkerHealthMonitor

class BaseNode:
    def __init__(self, name: str, worker: Any):
        self.name = name
        self.worker = worker

    def process(self, state: GraphState) -> GraphState:
        t0 = time.time()
        try:
            # Pre-flight health check
            worker_type = self.name.split('_')[0]
            is_healthy, h_reason = WorkerHealthMonitor.preflight_check(worker_type)
            if not is_healthy:
                result = WorkerResult(
                    status=WorkerStatus.FAILED,
                    data={},
                    reason=h_reason,
                    metadata={"error_type": "HealthCheckFailed"}
                )
            else:
                # We pass state.pipeline_state since existing workers expect it
                result = self.worker.run(state.job, state.pipeline_state)
        except Exception as e:
            result = WorkerResult(
                status=WorkerStatus.FAILED,
                data={},
                reason=str(e),
                metadata={"error_type": type(e).__name__}
            )
        
        result.metadata["execution_time"] = time.time() - t0
        
        state.worker_result = result
        state.current_node = self.name
        state.history.append(self.name)
        return state


class ParallelInternetNode(BaseNode):
    """
    Overrides the sequential fetch inside InternetWorker.run()
    by directly calling search_and_fetch in parallel!
    """
    def __init__(self, name: str, worker: Any):
        super().__init__(name, worker)
        
    def process(self, state: GraphState) -> GraphState:
        t0 = time.time()
        try:
            template = state.pipeline_state.get("template", {})
            job_id = state.job["id"]
            
            tasks = []
            seen_tasks = set()
            # Gather all needed assets
            for slot in template.get("asset_slots", []):
                role = slot["role"]
                terms = slot.get("search_terms", [role])
                count = slot.get("count", 1)
                for i in range(count):
                    term = terms[i % len(terms)]
                    if (role, term) not in seen_tasks:
                        seen_tasks.add((role, term))
                        tasks.append((role, term))
                    
            assets = []
            cache_hits = 0
            real_downloads = 0
            
            def fetch_with_retry(job_id, role, term):
                # 3 retries
                last_err = None
                for attempt in range(3):
                    try:
                        asset = self.worker.search_and_fetch(job_id, role, term)
                        # Checksum validation: reject empty files
                        if "file_path" in asset and asset["file_path"]:
                            fpath = Path(asset["file_path"])
                            if fpath.exists():
                                if fpath.stat().st_size == 0:
                                    fpath.unlink()
                                    raise ValueError(f"Corrupted 0-byte file downloaded for {role}")
                        return asset
                    except Exception as e:
                        last_err = e
                        time.sleep(1)
                raise last_err
            
            # Parallel execution
            # Max concurrent downloads can be configured via worker config, default 5
            max_workers = getattr(self.worker, 'config', {}).get('max_concurrent_downloads', 5)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_task = {
                    executor.submit(fetch_with_retry, job_id, role, term): (role, term)
                    for role, term in tasks
                }
                
                for future in as_completed(future_to_task):
                    role, term = future_to_task[future]
                    try:
                        asset = future.result()
                        assets.append(asset)
                        if asset.get("cache_hit"):
                            cache_hits += 1
                        if asset.get("source") in ("kenney", "poly_pizza"):
                            real_downloads += 1
                    except Exception as e:
                        # Fail the entire node if a critical fetch fails
                        raise e
            
            # Save assets back to pipeline_state just like the original worker did
            state.pipeline_state["assets"] = assets
            
            result = WorkerResult(
                status=WorkerStatus.SUCCESS,
                data={
                    "assets_fetched": len(assets),
                    "cache_hits": cache_hits,
                    "real_downloads": real_downloads
                },
                reason="",
                metadata={"assets_created": len(assets)}
            )
            
        except Exception as e:
            result = WorkerResult(
                status=WorkerStatus.FAILED,
                data={},
                reason=str(e),
                metadata={"error_type": type(e).__name__}
            )
            
        result.metadata["execution_time"] = time.time() - t0
        state.worker_result = result
        state.current_node = self.name
        state.history.append(self.name)
        return state
