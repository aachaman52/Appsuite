"""Jarvis Brain - Intelligent Orchestrator Decision Layer."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .hardware_manager import HardwareManager
from .provider_manager import ProviderManager
from .semantic_memory import SemanticMemory
from .token_banker import TokenBanker
from .worker_scorer import WorkerScoreRegistry
from ..logging_setup import get_logger

log = get_logger("core.brain")


@dataclass
class ExecutionPlan:
    stages: List[str]
    reasoning: str
    reused_assets: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent_tasks: List[Any] = field(default_factory=list)  # List of AgentTask
    template_id: Optional[str] = None
    
    # V2 Advanced Planning fields
    alternative_stages: List[str] = field(default_factory=list)
    estimated_cost_usd: float = 0.05
    estimated_duration_seconds: float = 120.0
    probabilistic_success_rate: float = 0.95

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stages": self.stages,
            "reasoning": self.reasoning,
            "reused_assets": self.reused_assets,
            "metadata": self.metadata,
            "template_id": self.template_id,
            "agent_tasks": [t.__dict__ for t in self.agent_tasks] if self.agent_tasks else [],
            "alternative_stages": self.alternative_stages,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "probabilistic_success_rate": self.probabilistic_success_rate,
        }


class JarvisBrain:
    """Intelligent decision layer replacing the static planner."""

    def __init__(
        self,
        semantic_memory: SemanticMemory,
        provider_manager: ProviderManager,
        token_banker: TokenBanker,
        hardware_manager: HardwareManager,
        templates: Any
    ):
        self.memory = semantic_memory
        self.providers = provider_manager
        self.banker = token_banker
        self.hardware = hardware_manager
        self.templates = templates

    def plan_execution(self, prompt: str, template_id: Optional[str] = None) -> ExecutionPlan:
        """Analyze the job and generate an optimal execution plan."""
        from ..agents.base_agent import AgentTask

        # 1. Retrieve failure history context from Semantic Memory (Long-Term Memory)
        past_failures = []
        if hasattr(self.memory, "failure") and hasattr(self.memory.failure, "get_failures_for_prompt"):
            past_failures = self.memory.failure.get_failures_for_prompt(prompt)
        
        failure_hints = ""
        if past_failures:
            failure_hints = "\nAvoid the following past errors/failures:\n" + "\n".join(
                [f"- Node/Error: {f.get('error')} in context: {f.get('context')}" for f in past_failures]
            )

        # 1b. Check for highly similar successful strategy in memory to reuse (similarity >= 0.85)
        similar_strategy = None
        if hasattr(self.memory, "strategy") and hasattr(self.memory.strategy, "get_similar_strategies"):
            try:
                matches = self.memory.strategy.get_similar_strategies(prompt, limit=3, threshold=0.85)
                # Filter to only successful strategies that have valid files on disk
                for m in matches:
                    if m.get("outcome") == "success":
                        json_plan = m.get("strategy", {})
                        matched_job_id = json_plan.get("job_id") or m.get("job_id")
                        has_files = False
                        if matched_job_id and hasattr(self.memory, "db") and self.memory.db:
                            prior_assets = self.memory.db.get_assets_for_job(matched_job_id)
                            if prior_assets:
                                from pathlib import Path
                                for a in prior_assets:
                                    fp = Path(a.get("file_path", ""))
                                    if fp.exists() and fp.stat().st_size > 0:
                                        has_files = True
                                        break
                        if has_files:
                            similar_strategy = m
                            break
            except Exception as e:
                log.warning("Failed to retrieve similar strategies: %s", e)

        if similar_strategy:
            json_plan = similar_strategy.get("strategy")
            if json_plan and "template_id" in json_plan and "agent_tasks" in json_plan:
                log.info("Found highly similar successful strategy in memory (score %.2f). Reusing plan directly.",
                         similar_strategy.get("similarity_score", 1.0))
                
                duration_defaults = {
                    "AssetAgent": 15.0,
                    "BlenderAgent": 120.0,
                    "GodotAgent": 90.0,
                    "CodeAgent": 10.0,
                    "BrowserAgent": 5.0,
                }
                score_registry = WorkerScoreRegistry(self.memory)
                worker_scores = score_registry.score_workers()
                agent_tasks = []
                for task_data in json_plan.get("agent_tasks", []):
                    agent_type = task_data.get("agent_type", "AssetAgent")
                    agent_tasks.append(
                        AgentTask(
                            task_id=task_data.get("task_id", "task_id"),
                            agent_type=agent_type,
                            objective=task_data.get("objective", ""),
                            dependencies=task_data.get("dependencies", []),
                            priority=task_data.get("priority", 1),
                            estimated_duration_seconds=float(task_data.get("estimated_duration_seconds", duration_defaults.get(agent_type, 10.0))),
                            metadata={
                                "preferred_worker_config": task_data.get("preferred_worker_config", {}),
                                "worker_score": worker_scores.get(agent_type, 0.0)
                            }
                        )
                    )

                stages = ["output_validation"]
                agent_types = {t.agent_type for t in agent_tasks}
                if "AssetAgent" in agent_types:
                    stages.insert(0, "asset_search")
                    stages.insert(1, "asset_processing")
                if "BlenderAgent" in agent_types:
                    stages.append("blender_import")
                if "CodeAgent" in agent_types:
                    stages.append("code")
                if "GodotAgent" in agent_types:
                    stages.append("godot_import")
                if "BrowserAgent" in agent_types:
                    stages.insert(0, "browser")
                stages.append("cloud_deploy")

                return ExecutionPlan(
                    stages=stages,
                    agent_tasks=agent_tasks,
                    reasoning=f"Found high-confidence semantic match (score {similar_strategy.get('similarity_score', 1.0):.2f}) from strategy memory. Reusing plan directly.",
                    reused_assets=True,
                    metadata={"matched_job": similar_strategy.get("id"), "memory_hit": True},
                    template_id=json_plan.get("template_id", template_id),
                )

        # 1c. If similarity is intermediate (0.50-0.85), retrieve successful plan for in-context example
        similar_examples_str = ""
        if hasattr(self.memory, "strategy") and hasattr(self.memory.strategy, "get_similar_strategies"):
            try:
                matches = self.memory.strategy.get_similar_strategies(prompt, limit=3, threshold=0.5)
                success_matches = [m for m in matches if m.get("outcome") == "success"]
                if success_matches:
                    example_strat = success_matches[0]
                    similar_examples_str = (
                        "\nHere is a previous successful plan for a similar task as reference/inspiration:\n"
                        f"Task: {example_strat.get('prompt')}\n"
                        f"Plan: {json.dumps(example_strat.get('strategy'))}\n"
                    )
            except Exception:
                pass

        # 1d. Retrieve failed strategies to avoid
        failed_examples_str = ""
        if hasattr(self.memory, "strategy") and hasattr(self.memory.strategy, "get_similar_strategies"):
            try:
                matches = self.memory.strategy.get_similar_strategies(prompt, limit=3, threshold=0.5)
                fail_matches = [m for m in matches if m.get("outcome") == "failure"]
                if fail_matches:
                    failed_examples_str = (
                        "\nAvoid reproducing the following past plans that FAILED:\n" +
                        "\n".join([f"- Prompt: {m.get('prompt')}\n  Plan to avoid: {json.dumps(m.get('strategy'))}" for m in fail_matches])
                    )
            except Exception:
                pass

        system_instruction = (
            "You are Jarvis, the Autonomous Game Engineer Planner.\n"
            "Given a user description of a game scene, design a structured execution plan.\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            "  \"template_id\": \"generic_scene\" or \"medieval_village\" or appropriate,\n"
            "  \"reasoning\": \"Detailed reasoning for your decisions\",\n"
            "  \"needed_assets\": [\n"
            "    {\"role\": \"asset_role_name\", \"count\": 1, \"search_terms\": [\"term1\", \"term2\"], \"required\": true}\n"
            "  ],\n"
            "  \"agent_tasks\": [\n"
            "    {\n"
            "      \"task_id\": \"task_unique_id\",\n"
            "      \"agent_type\": \"AssetAgent\" | \"BlenderAgent\" | \"CodeAgent\" | \"GodotAgent\" | \"BrowserAgent\",\n"
            "      \"objective\": \"Clear objective for the agent\",\n"
            "      \"dependencies\": [\"other_task_id\"],\n"
            "      \"priority\": 1\n"
            "    }\n"
            "  ]\n"
            "}\n"
            f"{failure_hints}"
            f"{similar_examples_str}"
            f"{failed_examples_str}"
        )

        # 2. Try LLM Planning
        json_plan = None
        has_llm = False
        try:
            # Check if any live LLM providers are enabled
            has_llm = any(p.get("enabled") and p.get("type") == "llm" for p in self.providers._providers)
        except Exception:
            pass

        if has_llm:
            attempt = 0
            current_prompt = f"Goal: {prompt}"
            while attempt < 2 and json_plan is None:
                attempt += 1
                try:
                    response_text = self.providers.generate_text(
                        prompt=current_prompt,
                        task_type="plan",
                        system_instruction=system_instruction,
                        timeout=15.0
                    )
                    
                    if response_text:
                        clean_response = response_text.strip()
                        if clean_response.startswith("```json"):
                            clean_response = clean_response[7:]
                        if clean_response.endswith("```"):
                            clean_response = clean_response[:-3]
                        clean_response = clean_response.strip()
                        
                        parsed = json.loads(clean_response)
                        if isinstance(parsed, dict) and "template_id" in parsed and "agent_tasks" in parsed:
                            json_plan = parsed
                            break
                except Exception as parse_err:
                    current_prompt = f"Goal: {prompt}\nYour previous response was invalid JSON: {parse_err}. Please output valid JSON only."

        # 3. If LLM planning succeeded, return the plan
        if json_plan:
            duration_defaults = {
                "AssetAgent": 15.0,
                "BlenderAgent": 120.0,
                "GodotAgent": 90.0,
                "CodeAgent": 10.0,
                "BrowserAgent": 5.0,
            }
            score_registry = WorkerScoreRegistry(self.memory)
            worker_scores = score_registry.score_workers()
            agent_tasks = []
            for task_data in json_plan.get("agent_tasks", []):
                agent_type = task_data.get("agent_type", "AssetAgent")
                agent_tasks.append(
                    AgentTask(
                        task_id=task_data.get("task_id", "task_id"),
                        agent_type=agent_type,
                        objective=task_data.get("objective", ""),
                        dependencies=task_data.get("dependencies", []),
                        priority=task_data.get("priority", 1),
                        estimated_duration_seconds=float(task_data.get("estimated_duration_seconds", duration_defaults.get(agent_type, 10.0))),
                        metadata={
                            "preferred_worker_config": task_data.get("preferred_worker_config", {}),
                            "worker_score": worker_scores.get(agent_type, 0.0)
                        }
                    )
                )

            # Map agent types to pipeline stages
            stages = ["output_validation"]
            agent_types = {t.agent_type for t in agent_tasks}
            if "AssetAgent" in agent_types:
                stages.insert(0, "asset_search")
                stages.insert(1, "asset_processing")
            if "BlenderAgent" in agent_types:
                stages.append("blender_import")
            if "GodotAgent" in agent_types:
                stages.append("godot_import")
            if "BrowserAgent" in agent_types:
                stages.insert(0, "browser")
            stages.append("cloud_deploy")

            # Store in strategy memory (Long-Term Memory)
            if hasattr(self.memory, "strategy") and hasattr(self.memory.strategy, "add_strategy"):
                self.memory.strategy.add_strategy(prompt, json_plan, "success")

            metadata = {
                "llm_planned": True,
                "needed_assets": json_plan.get("needed_assets", []),
                "scene_plan": json_plan.get("scene_plan", {"needed_assets": json_plan.get("needed_assets", [])}),
            }

            return ExecutionPlan(
                stages=stages,
                agent_tasks=agent_tasks,
                reasoning=json_plan.get("reasoning", "LLM-generated plan"),
                reused_assets=bool(json_plan.get("reused_assets", False)),
                metadata=metadata,
                template_id=json_plan.get("template_id", template_id),
                alternative_stages=["asset_processing", "code", "godot_import", "output_validation"],
                estimated_cost_usd=0.08,
                estimated_duration_seconds=150.0,
                probabilistic_success_rate=0.92,
            )

        # 4. Fallback to Rules-based Planner
        similar_job = None
        if hasattr(self.memory, "strategy") and hasattr(self.memory.strategy, "get_similar_strategies"):
            try:
                similar_strategies = self.memory.strategy.get_similar_strategies(prompt, limit=3, threshold=0.35)
                for s in similar_strategies:
                    if s.get("outcome") == "success":
                        matched_job_id = s.get("job_id") or (s.get("strategy") or {}).get("job_id") or s.get("id")
                        has_files = False
                        if matched_job_id and hasattr(self.memory, "db") and self.memory.db:
                            prior_assets = self.memory.db.get_assets_for_job(matched_job_id)
                            if prior_assets:
                                from pathlib import Path
                                for a in prior_assets:
                                    fp = Path(a.get("file_path", ""))
                                    if fp.exists() and fp.stat().st_size > 0:
                                        has_files = True
                                        break
                        if has_files:
                            similar_job = s
                            break
            except Exception as e:
                log.warning("Failed to verify fallback similar strategies: %s", e)

        if not similar_job:
            try:
                candidates = self.memory.recall_similar(prompt, threshold=0.7)
                if candidates:
                    cand_list = candidates if isinstance(candidates, list) else [candidates]
                    for c in cand_list:
                        if c.get("outcome") == "success":
                            matched_job_id = c.get("job_id") or (c.get("strategy") or {}).get("job_id") or c.get("id")
                            has_files = False
                            if matched_job_id and hasattr(self.memory, "db") and self.memory.db:
                                prior_assets = self.memory.db.get_assets_for_job(matched_job_id)
                                if prior_assets:
                                    from pathlib import Path
                                    for a in prior_assets:
                                        fp = Path(a.get("file_path", ""))
                                        if fp.exists() and fp.stat().st_size > 0:
                                            has_files = True
                                            break
                            if has_files:
                                similar_job = c
                                break
            except Exception as e:
                log.warning("Failed recall_similar validation: %s", e)

        agent_tasks = []
        if similar_job and similar_job.get("outcome") == "success":
            t1 = AgentTask(task_id="blender_1", agent_type="BlenderAgent", objective="Optimize cached models", priority=1)
            t2 = AgentTask(task_id="code_1", agent_type="CodeAgent", objective="Generate scripts", priority=2)
            t3 = AgentTask(task_id="godot_1", agent_type="GodotAgent", objective="Build scene", dependencies=["blender_1", "code_1"], priority=1)
            agent_tasks.extend([t1, t2, t3])
            
            matched_job_id = similar_job.get("job_id") or (similar_job.get("strategy") or {}).get("job_id") or similar_job.get("id")
            return ExecutionPlan(
                stages=["asset_processing", "code", "blender_import", "godot_import", "output_validation", "cloud_deploy"],
                agent_tasks=agent_tasks,
                reasoning=f"Found high-confidence semantic match (score {similar_job.get('similarity_score', 0):.2f}) from job {matched_job_id or 'unknown'}. Reusing assets and bypassing search.",
                reused_assets=True,
                metadata={"matched_job": matched_job_id},
                template_id=template_id,
                alternative_stages=["asset_processing", "code", "godot_import", "output_validation"],
                estimated_cost_usd=0.02,
                estimated_duration_seconds=60.0,
                probabilistic_success_rate=0.98,
            )
            
        res = self.hardware.resources()
        if res.get("ram_percent", 0) > 90.0:
            reasoning = "Standard pipeline scheduled, but RAM is critically high. Heavy workers may be delayed."
        else:
            reasoning = "Standard pipeline scheduled. Full asset acquisition planned. (Fallback)"
            
        t1 = AgentTask(task_id="asset_1", agent_type="AssetAgent", objective="Find and process assets", priority=1)
        t2 = AgentTask(task_id="blender_1", agent_type="BlenderAgent", objective="Optimize models", dependencies=["asset_1"], priority=2)
        t3 = AgentTask(task_id="code_1", agent_type="CodeAgent", objective="Generate scripts", priority=3)
        t4 = AgentTask(task_id="godot_1", agent_type="GodotAgent", objective="Build scene", dependencies=["blender_1", "code_1"], priority=1)
        agent_tasks.extend([t1, t2, t3, t4])
            
        return ExecutionPlan(
            stages=["asset_search", "asset_processing", "blender_import", "godot_import", "output_validation", "cloud_deploy"],
            agent_tasks=agent_tasks,
            reasoning=reasoning,
            reused_assets=False,
            template_id=template_id,
            alternative_stages=["asset_processing", "code", "godot_import", "output_validation"],
            estimated_cost_usd=0.05,
            estimated_duration_seconds=120.0,
            probabilistic_success_rate=0.95,
        )
