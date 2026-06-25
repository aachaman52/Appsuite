"""Graph State definition."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from ..core.state import WorkerResult

@dataclass
class GraphState:
    """
    Holds the state of the graph during execution.
    Compatible with existing JobState.
    """
    job: Dict[str, Any]
    current_node: str = "start"
    worker_result: Optional[WorkerResult] = None
    history: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # We also carry a global dictionary for generic pipeline state
    # This is identical to the 'state' passed to legacy workers
    pipeline_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        wr_dict = None
        if self.worker_result:
            wr_dict = {
                "status": self.worker_result.status.value,
                "data": self.worker_result.data,
                "reason": self.worker_result.reason,
                "retry_count": self.worker_result.retry_count,
                "metadata": self.worker_result.metadata
            }
        
        if hasattr(self.pipeline_state, "as_dict"):
            clean_pipeline_state = self.pipeline_state.as_dict()
        elif isinstance(self.pipeline_state, dict):
            clean_pipeline_state = {k: v for k, v in self.pipeline_state.items() if k != "project"}
        else:
            clean_pipeline_state = {}
        
        return {
            "job": self.job,
            "current_node": self.current_node,
            "worker_result": wr_dict,
            "history": self.history,
            "metadata": self.metadata,
            "pipeline_state": clean_pipeline_state
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GraphState:
        from ..core.state import WorkerResult, WorkerStatus, JobState
        
        wr = None
        if data.get("worker_result"):
            wdata = data["worker_result"]
            wr = WorkerResult(
                status=WorkerStatus(wdata["status"]),
                data=wdata.get("data", {}),
                reason=wdata.get("reason", ""),
                retry_count=wdata.get("retry_count", 0),
                metadata=wdata.get("metadata", {})
            )
            
        pstate_data = data.get("pipeline_state", {})
        pstate = pstate_data
        if isinstance(pstate_data, dict) and "template" in pstate_data:
            pstate = JobState(template=pstate_data["template"])
            clean_pstate_data = {k: v for k, v in pstate_data.items() if hasattr(pstate, k)}
            pstate.update(clean_pstate_data)
            
        return cls(
            job=data.get("job", {}),
            current_node=data.get("current_node", "start"),
            worker_result=wr,
            history=data.get("history", []),
            metadata=data.get("metadata", {}),
            pipeline_state=pstate
        )
