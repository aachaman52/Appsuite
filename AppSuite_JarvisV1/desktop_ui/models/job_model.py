from typing import Dict, Any

class JobModel:
    def __init__(self, job_id: str, prompt: str, status: str = "pending") -> None:
        self.job_id = job_id
        self.prompt = prompt
        self.status = status
        self.stage = "planning"
        self.retry_count = 0
        self.error = None
        self.results = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.job_id,
            "prompt": self.prompt,
            "status": self.status,
            "stage": self.stage,
            "retry_count": self.retry_count,
            "error": self.error,
            "results": self.results
        }
