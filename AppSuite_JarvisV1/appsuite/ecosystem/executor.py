"""Safe Ecosystem Command Executor for PyFlare Jarvis."""
from __future__ import annotations

import webbrowser
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .client import AachmanEcosystemClient, get_ecosystem_client
from .constants import (
    ECOSYSTEM_URLS,
    JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS,
)
from .interpreter import JarvisEcosystemIntent
from ..logging_setup import get_logger

log = get_logger("ecosystem.executor")


@dataclass
class ExecutionResult:
    command_id: str
    status: str  # "preview" | "success" | "failed" | "rejected" | "cancelled"
    message: str
    requires_confirmation: bool = False
    preview_data: Dict[str, Any] = field(default_factory=dict)
    deep_link: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status,
            "message": self.message,
            "requires_confirmation": self.requires_confirmation,
            "preview_data": self.preview_data,
            "deep_link": self.deep_link,
        }


class EcosystemExecutor:
    """Dispatches validated ecosystem commands safely."""

    def __init__(self, client: Optional[AachmanEcosystemClient] = None):
        self.client = client or get_ecosystem_client()

    def execute_intent(
        self,
        intent: JarvisEcosystemIntent,
        confirm: bool = False,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """Execute a structured Jarvis ecosystem intent."""
        # 1. Verify against central allowlist
        if intent.command_id not in JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS:
            log.warning(f"Rejected unallowed command ID: {intent.command_id}")
            return ExecutionResult(
                command_id=intent.command_id,
                status="rejected",
                message=f"Command '{intent.command_id}' is not an authorized ecosystem action.",
            )

        # 2. Navigation Commands (app.open.*) -> Immediate safe launch
        if intent.command_id in ECOSYSTEM_URLS:
            target_url = ECOSYSTEM_URLS[intent.command_id]
            try:
                webbrowser.open(target_url)
                return ExecutionResult(
                    command_id=intent.command_id,
                    status="success",
                    message=f"Launched {intent.summary} ({target_url})",
                    deep_link=target_url,
                )
            except Exception as e:
                log.error(f"Failed to open browser for {target_url}: {e}")
                return ExecutionResult(
                    command_id=intent.command_id,
                    status="failed",
                    message=f"Could not open browser URL: {e}",
                )

        # 3. Write Commands -> Preview or Confirmed Execution
        params = dict(intent.parameters)
        if overrides:
            params.update(overrides)

        # If confirmation is not yet given, return structured preview
        if intent.requires_confirmation and not confirm:
            return ExecutionResult(
                command_id=intent.command_id,
                status="preview",
                message=f"Preview ready for: {intent.summary}. Confirm to execute.",
                requires_confirmation=True,
                preview_data={
                    "command_id": intent.command_id,
                    "summary": intent.summary,
                    "parameters": params,
                    "missing_fields": intent.missing_fields,
                },
            )

        # Map to Supabase RPC action type
        rpc_action_type = ""
        if intent.command_id == "action.daymentor.create_task":
            rpc_action_type = "daymentor.create_task"
        elif intent.command_id == "action.cricket.create_match":
            rpc_action_type = "cricket_scorer.create_match"
        elif intent.command_id == "action.hackathon.start_simulation":
            rpc_action_type = "hackathon_simulator.start_simulation"
        else:
            return ExecutionResult(
                command_id=intent.command_id,
                status="rejected",
                message=f"Unknown write action: {intent.command_id}",
            )

        import uuid
        if not intent.idempotency_key:
            intent.idempotency_key = str(uuid.uuid4())

        # 4. Authorized Execution via Supabase RPC with Idempotency Key
        res = self.client.execute_ecosystem_action(
            rpc_action_type, params, idempotency_key=intent.idempotency_key
        )
        if res.get("success"):
            deep_link = res.get("deep_link")
            return ExecutionResult(
                command_id=intent.command_id,
                status="success",
                message=f"Successfully executed {intent.summary} via Aachman Ecosystem RPC.",
                deep_link=deep_link,
            )
        else:
            err = res.get("error", "Unknown error during ecosystem execution.")
            return ExecutionResult(
                command_id=intent.command_id,
                status="failed",
                message=f"Execution failed: {err}",
            )
