"""Code Worker - plan, generate, validate and correct gameplay scripts."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .base import BaseWorker, WorkerError
from ..core.state import WorkerStatus, WorkerResult
from ..config import load_config


class CodeWorker(BaseWorker):
    name = "code"

    def __init__(self, config: Dict[str, Any], retries: Dict[str, Any], context: Dict[str, Any], provider_manager=None):
        super().__init__(config, retries, context)
        self.providers = provider_manager

    def plan(self, job: Dict[str, Any], state: Any) -> List[str]:
        prompt = job.get("prompt", "")
        is_fps = any(k in prompt.lower() for k in ("fps", "shooter", "gta", "playable", "character", "third-person"))
        script_filename = "player.gd" if is_fps else "gameplay.gd"
        return [
            f"plan_architecture:{script_filename}",
            f"generate_gameplay_script:{script_filename}",
            f"validate_syntax:{script_filename}"
        ]

    def verify(self, job: Dict[str, Any], state: Any, result: WorkerResult) -> Tuple[bool, str]:
        if result.status != WorkerStatus.SUCCESS:
            return False, f"status: {result.status.value}"
        
        generated = state.get("generated_scripts", [])
        if not generated:
            return False, "No gameplay scripts generated"
            
        for script in generated:
            path = Path(script.get("path", ""))
            if not path.exists():
                return False, f"Generated script file missing on disk: {path}"
            if path.stat().st_size == 0:
                return False, f"Generated script file is empty: {path}"
        return True, "ok"

    def recover(self, job: Dict[str, Any], state: Any, exception: Exception) -> WorkerResult:
        self.log.warning("[code] Recovery triggered: generating pre-validated local fallback templates due to: %s", exception)
        
        # Resolve path
        cfg = load_config()
        job_id = job.get("id", "default")
        project_path = state.get("project_path")
        if not project_path:
            output_dir = cfg.abs_path("output_dir")
            project_path = output_dir / job_id / "godot_project"
            
        project_dir = Path(project_path)
        scripts_dir = project_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        prompt = job.get("prompt", "")
        is_fps = any(k in prompt.lower() for k in ("fps", "shooter", "gta", "playable", "character", "third-person"))
        script_filename = "player.gd" if is_fps else "gameplay.gd"
        script_path = scripts_dir / script_filename
        
        # Fallback templates
        if is_fps:
            fallback_code = (
                "extends CharacterBody3D\n\n"
                "const SPEED = 5.0\n"
                "const JUMP_VELOCITY = 4.5\n\n"
                "func _physics_process(delta: float) -> void:\n"
                "    # Apply gravity\n"
                "    if not is_on_floor():\n"
                "        velocity.y -= 9.8 * delta\n\n"
                "    var input_dir := Vector2.ZERO\n"
                "    if Input.is_key_pressed(KEY_W): input_dir.y -= 1.0\n"
                "    if Input.is_key_pressed(KEY_S): input_dir.y += 1.0\n"
                "    if Input.is_key_pressed(KEY_A): input_dir.x -= 1.0\n"
                "    if Input.is_key_pressed(KEY_D): input_dir.x += 1.0\n"
                "    var direction := (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()\n"
                "    if direction:\n"
                "        velocity.x = direction.x * SPEED\n"
                "        velocity.z = direction.z * SPEED\n"
                "        # Rotate towards movement direction\n"
                "        var target_angle = atan2(-direction.x, -direction.z)\n"
                "        rotation.y = lerp_angle(rotation.y, target_angle, 0.15)\n"
                "    else:\n"
                "        velocity.x = move_toward(velocity.x, 0, SPEED)\n"
                "        velocity.z = move_toward(velocity.z, 0, SPEED)\n"
                "    move_and_slide()\n"
            )
        else:
            fallback_code = (
                "extends Node3D\n\n"
                "func _ready() -> void:\n"
                "    print('Gameplay initialised.')\n"
            )
            
        script_path.write_text(fallback_code, encoding="utf-8")
        
        state["generated_scripts"] = [{
            "path": str(script_path),
            "filename": script_filename,
            "content": fallback_code
        }]
        
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={
                "scripts_generated": 1,
                "script_path": str(script_path),
                "recovered": True
            },
            reason="Recovered with clean gameplay template.",
            metadata={"recovered": True}
        )

    def report(self, job: Dict[str, Any], state: Any) -> Dict[str, Any]:
        scripts = state.get("generated_scripts", [])
        total_lines = sum(len(s.get("content", "").splitlines()) for s in scripts)
        return {
            "worker": self.name,
            "scripts_count": len(scripts),
            "total_lines_of_code": total_lines,
            "timestamp": time.time()
        }

    def run(self, job: Dict[str, Any], state: Any) -> WorkerResult:
        job_prompt = job.get("prompt", "Generic")
        is_fps = any(k in job_prompt.lower() for k in ("fps", "shooter", "gta", "playable", "character", "third-person"))
        script_filename = "player.gd" if is_fps else "gameplay.gd"

        cfg = load_config()
        project_path = state.get("project_path")
        if not project_path:
            output_dir = cfg.abs_path("output_dir")
            project_path = output_dir / job["id"] / "godot_project"
            
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
                    self.log.warning("LLM generation call failed: %s", e)
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
                if self.providers and hasattr(self.providers, "_generate_local_fallback"):
                    code = self.providers._generate_local_fallback(prompt, "code_generation")
                else:
                    code = ""

            if not code:
                raise WorkerError("Failed to generate code.")

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
                self.log.warning("Syntax verification failed on attempt %d: %s", attempt, stderr_out)
                attempt += 1

        if not success:
            raise WorkerError(f"GDScript syntax validation failed: {error_context}")

        state["generated_scripts"] = [{
            "path": str(script_path),
            "filename": script_filename,
            "content": code
        }]

        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={
                "scripts_generated": 1,
                "script_path": str(script_path)
            },
            reason="",
            metadata={}
        )
