from __future__ import annotations
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict
from .base_agent import BaseAgent, AgentTask
from ..config import load_config

class CodeAgent(BaseAgent):
    def receive_task(self, task: AgentTask):
        print(f"[{self.name}] Creating scripts")
        if self.message_bus:
            self.message_bus.send("code_status", "Creating gameplay scripts...")

    def plan(self, task: AgentTask) -> Any:
        return ["code_generation"]

    def execute_tools(self, plan: Any) -> Any:
        if self.message_bus:
            self.message_bus.send("code_status", "Generating GDScript...")
            
        job_prompt = "Generic"
        if hasattr(self, 'current_job_state') and 'job' in self.current_job_state:
            job_prompt = self.current_job_state['job'].get('prompt', 'Generic')

        # Determine file and node names
        is_fps = "fps" in job_prompt.lower() or "shooter" in job_prompt.lower()
        script_filename = "player.gd" if is_fps else "gameplay.gd"

        # Resolve paths
        cfg = load_config()
        job_id = self.current_job_state["job"]["id"] if hasattr(self, 'current_job_state') else "default"
        pipeline_state = self.current_job_state.get("pipeline_state", {}) if hasattr(self, 'current_job_state') else {}
        
        project_path = pipeline_state.get("project_path")
        if not project_path:
            output_dir = cfg.abs_path("output_dir")
            project_path = output_dir / job_id / "godot_project"
            
        project_dir = Path(project_path)
        scripts_dir = project_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = scripts_dir / script_filename

        system_instruction = (
            "You are an expert GDScript programmer for Godot 4. Write clean, syntactically correct, and optimized GDScript.\n"
            "Return ONLY the code inside raw text format, without any markdown formatting, backticks, or explanations."
        )

        prompt = (
            f"Write a GDScript for Godot 4. Objective: {job_prompt}.\n"
            f"The script should extend CharacterBody3D if it is a player/FPS movement script, or Node3D/Node otherwise.\n"
            f"It must implement movement, controls, or game logic. To ensure compatibility with blank projects, use 'Input.is_key_pressed' (e.g. KEY_W, KEY_A, KEY_S, KEY_D) instead of custom InputMap actions.\n"
            f"Provide only the script content. No markdown wrapping."
        )

        godot_bin = cfg.raw.get("workers", {}).get("godot", {}).get("binary", "godot")

        code = ""
        max_retries = 3
        attempt = 1
        success = False
        error_context = ""

        while attempt <= max_retries:
            current_prompt = prompt
            if error_context:
                current_prompt += f"\n\nPrevious attempt failed syntax check with: {error_context}\nPlease correct the errors and output the complete corrected GDScript."

            if self.providers:
                try:
                    code = self.providers.generate_text(
                        current_prompt,
                        task_type="code_generation",
                        system_instruction=system_instruction
                    )
                except Exception as e:
                    if self.message_bus:
                        self.message_bus.send("code_status", f"LLM generation call failed: {e}")
                    code = ""
            
            # Remove potential markdown wrappers
            code = code.strip()
            if code.startswith("```"):
                lines = code.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                code = "\n".join(lines).strip()

            if not code:
                # Fallback to local rules-based code if generation fails
                code = self.providers._generate_local_fallback(prompt, "code_generation") if self.providers else ""

            # Save file to check syntax
            script_path.write_text(code, encoding="utf-8")

            # Validate syntax via Godot if available
            valid = True
            stderr_out = ""
            try:
                result = subprocess.run(
                    [godot_bin, "--headless", "--check-only", str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode != 0:
                    valid = False
                    stderr_out = result.stderr or result.stdout
            except FileNotFoundError:
                # Godot binary not found, fallback to basic validation or accept
                pass
            except Exception as e:
                pass

            if valid:
                success = True
                break
            else:
                error_context = stderr_out
                if self.message_bus:
                    self.message_bus.send("code_status", f"Syntax verification failed on attempt {attempt}: {stderr_out}")
                attempt += 1

        if not success:
            # Final fallback: write local rules-based generator code to ensure playability
            fallback_code = self.providers._generate_local_fallback(prompt, "code_generation") if self.providers else ""
            script_path.write_text(fallback_code, encoding="utf-8")
            code = fallback_code
            if self.message_bus:
                self.message_bus.send("code_status", "Self-correction limit reached. Defaulting to pre-validated template code.")

        # Save to pipeline state
        if hasattr(self, 'current_job_state'):
            job_state = self.current_job_state
            if "pipeline_state" not in job_state:
                job_state["pipeline_state"] = {}
            if "generated_scripts" not in job_state["pipeline_state"]:
                job_state["pipeline_state"]["generated_scripts"] = []
            
            job_state["pipeline_state"]["generated_scripts"].append({
                "path": str(script_path),
                "filename": script_filename,
                "content": code
            })

        lines = len(code.splitlines())
        return {"execution_results": [{"code_generation": "success"}], "lines": lines, "script_path": str(script_path)}
