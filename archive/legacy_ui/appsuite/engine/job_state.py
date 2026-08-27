from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from ..core.state import JobState, WorkerResult, WorkerStatus

@dataclass
class UnifiedJobState(JobState):
    job: Dict[str, Any] = field(default_factory=dict)
    current_node: str = "start"
    worker_result: Optional[WorkerResult] = None
    history: List[str] = field(default_factory=list)
    
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    checkpoints: List[str] = field(default_factory=list)
    failures: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def pipeline_state(self) -> UnifiedJobState:
        return self

    @pipeline_state.setter
    def pipeline_state(self, val):
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to a dictionary for checkpointing."""
        # Convert JobState fields
        pstate = self.as_dict()
        # Avoid serialization of project object itself
        if "project" in pstate:
            pstate.pop("project")
            
        wr_dict = None
        if self.worker_result:
            wr_dict = {
                "status": self.worker_result.status.value,
                "data": self.worker_result.data,
                "reason": self.worker_result.reason,
                "retry_count": self.worker_result.retry_count,
                "metadata": self.worker_result.metadata
            }
        
        return {
            "job": self.job,
            "current_node": self.current_node,
            "worker_result": wr_dict,
            "history": self.history,
            "metadata": self.metadata,
            "pipeline_state": pstate,
            "execution_history": self.execution_history,
            "metrics": self.metrics,
            "checkpoints": self.checkpoints,
            "failures": self.failures
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UnifiedJobState:
        """Create a UnifiedJobState instance from serialized data."""
        job = data.get("job", {})
        pstate_data = data.get("pipeline_state", {})
        template = pstate_data.get("template", {"id": "generic_scene"})
        
        wr = None
        if data.get("worker_result") and isinstance(data["worker_result"], dict):
            wdata = data["worker_result"]
            wr = WorkerResult(
                status=WorkerStatus(wdata["status"]),
                data=wdata.get("data", {}),
                reason=wdata.get("reason", ""),
                retry_count=wdata.get("retry_count", 0),
                metadata=wdata.get("metadata", {})
            )
            
        # Initialize
        state = cls(
            template=template,
            job=job,
            current_node=data.get("current_node", "start"),
            worker_result=wr,
            history=data.get("history", []),
            metadata=data.get("metadata", {}),
            execution_history=data.get("execution_history", []),
            metrics=data.get("metrics", {}),
            checkpoints=data.get("checkpoints", []),
            failures=data.get("failures", [])
        )
        
        # Update inherited JobState fields
        clean_pstate_data = {k: v for k, v in pstate_data.items() if hasattr(state, k) and k != "template"}
        state.update(clean_pstate_data)
        if pstate_data.get("world_model_state") is not None:
            state.world_model = pstate_data["world_model_state"]
        return state
