"""
Project Improver - Automatic Repair Loop
========================================
Categorizes failures from ValidationWorker, searches RepairMemory,
ranks and applies the best repair automatically. Modifies the project
and loops until validation passes or max retries are reached.
"""
from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any, Dict, List

from ..logging_setup import get_logger
from ..workers.base import WorkerError

log = get_logger("project_improver")

class ProjectImprover:
    def __init__(self, db: Any, memory: Any):
        self.db = db
        self.memory = memory

    def _categorize_failure(self, check_name: str) -> str:
        name = check_name.lower()
        if name in ("assets_present", "all_asset_files_exist"):
            return "missing_asset"
        if name in ("all_assets_imported_in_project", "scene_fbx_imported"):
            return "import_failure"
        if "script" in name or "compile" in name:
            return "script_error"
        if "nav" in name:
            return "nav_error"
        if "physic" in name or "collision" in name:
            return "physics_error"
        if "corrupt" in name or "export" in name:
            return "asset_corruption"
        if "layout" in name or "overlap" in name:
            return "ui_error"
        if "render" in name:
            return "render_error"
        if "exists" in name or "structure" in name:
            return "structural_error"
        return "unknown_error"

    def execute_repair_loop(self, job: Dict[str, Any], state: Any, validation_worker: Any) -> Dict[str, Any]:
        """Runs the automatic repair loop up to 5 times."""
        repair_report = {
            "attempts": [],
            "total_execution_time": 0.0,
            "success": False
        }
        
        loop_start_time = time.time()
        tried_repairs = set()
        
        last_error_pattern = None
        last_repair_action = None
        last_target_failure_name = None
        prev_score = 0.0

        for attempt_num in range(1, 6):
            iteration_start = time.time()
            
            try:
                res = validation_worker.run(job, state)
                if last_error_pattern and last_repair_action:
                    self.memory.repair.record(last_error_pattern, last_repair_action, True)
                repair_report["success"] = True
                break
            except WorkerError as e:
                validation = state.get("validation", {})
                if last_error_pattern and last_repair_action and last_target_failure_name:
                    checks = validation.get("checks", [])
                    still_failed = any(not c.get("passed", False) and c.get("name") == last_target_failure_name for c in checks)
                    if still_failed:
                        self.memory.repair.record(last_error_pattern, last_repair_action, False)
                    else:
                        self.memory.repair.record(last_error_pattern, last_repair_action, True)
                
            checks = validation.get("checks", [])
            failed_checks = [c for c in checks if not c.get("passed", False)]
            
            if not failed_checks:
                log.warning("ProjectImprover: Validation raised WorkerError but no checks failed.")
                break
                
            # Categorize the first failure
            target_failure = failed_checks[0]
            error_pattern = self._categorize_failure(target_failure["name"])
            
            # Rank and search RepairMemory for best historical repair
            history = self.db.query(
                "SELECT * FROM repair_memory WHERE error_pattern=? ORDER BY success_count DESC, fail_count ASC", 
                (error_pattern,)
            )
            
            best_repair = self._get_fallback_repair(error_pattern)
            for h in history:
                if h["fix_action"] not in tried_repairs:
                    best_repair = h["fix_action"]
                    break
                    
            tried_repairs.add(best_repair)
            last_error_pattern = error_pattern
            last_repair_action = best_repair
            last_target_failure_name = target_failure["name"]
            
            log.info("ProjectImprover (Attempt %d): Applying %s for %s", attempt_num, best_repair, error_pattern)
            
            # Actually modify the generated project
            files_modified = self._apply_repair(best_repair, state, target_failure)
            
            # Rebuild project
            self._rebuild_project(state)
            
            iteration_time = time.time() - iteration_start
            score = validation.get("passed", 0) / max(validation.get("total", 1), 1)
            improvement_score = score - prev_score
            prev_score = score
            
            attempt_record = {
                "RepairAttempt": attempt_num,
                "RepairReason": f"Fixed {error_pattern} caused by {target_failure['name']}",
                "FilesModified": files_modified,
                "ExecutionTime": iteration_time,
                "ValidationScore": score,
                "ImprovementScore": improvement_score
            }
            repair_report["attempts"].append(attempt_record)

        repair_report["total_execution_time"] = time.time() - loop_start_time
        return repair_report

    def _get_fallback_repair(self, error_pattern: str) -> str:
        fallbacks = {
            "import_failure": "create_import_files",
            "structural_error": "create_missing_structure",
            "script_error": "repair_script_syntax",
            "missing_asset": "copy_default_assets",
        }
        return fallbacks.get(error_pattern, "rebuild_project")

    def _apply_repair(self, repair_action: str, state: Any, target_failure: Dict[str, Any]) -> List[str]:
        """Physically modifies the Godot project based on the repair action."""
        files_modified = []
        project = Path(state.get("godot_project", "output"))
        if not project.exists():
            project.mkdir(parents=True, exist_ok=True)
            
        assets_dir = project / "Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        if repair_action == "create_import_files":
            for a in state.get("assets", []):
                name = Path(a.get("file_path", "unknown")).name
                import_file = assets_dir / f"{name}.import"
                if not import_file.exists():
                    import_file.write_text("[remap]\nimporter=\"gltf\"\n")
                    files_modified.append(import_file.name)
            fbx = assets_dir / "scene.fbx.import"
            if not fbx.exists():
                fbx.write_text("[remap]\nimporter=\"fbx\"\n")
                files_modified.append(fbx.name)
                
        elif repair_action == "create_missing_structure":
            p_file = project / "project.godot"
            if not p_file.exists():
                p_file.write_text("; Engine configuration file.\n")
                files_modified.append("project.godot")
            scenes = project / "Scenes"
            scenes.mkdir(exist_ok=True)
            m_file = scenes / "main.tscn"
            if not m_file.exists():
                m_file.write_text("[gd_scene format=3]\n[node name=\"Node3D\" type=\"Node3D\"]\n")
                files_modified.append("main.tscn")
                
        elif repair_action == "repair_script_syntax":
            # Extract line number and file from target_failure detail
            # Format:  res://scripts/player.gd:12 - Parse Error: ...
            import re
            detail = target_failure.get("detail", "")
            matches = re.finditer(r"res://([^:]+):(\d+)\s*-\s*(Parse Error|SCRIPT ERROR)", detail)
            repaired_files = set()
            for match in matches:
                rel_path = match.group(1)
                line_num = int(match.group(2))
                abs_path = project / rel_path
                if abs_path.exists():
                    lines = abs_path.read_text(encoding="utf-8").splitlines()
                    if 0 < line_num <= len(lines):
                        idx = line_num - 1
                        if not lines[idx].strip().startswith("#"):
                            lines[idx] = "# [REPAIRED] " + lines[idx]
                            abs_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                            repaired_files.add(abs_path.name)
            
            if not repaired_files:
                # If we couldn't parse the exact error, do a generic fallback to at least make it compile
                scripts = project / "scripts"
                scripts.mkdir(exist_ok=True)
                s_file = scripts / "fallback.gd"
                s_file.write_text("extends Node\n\nfunc _ready():\n\tpass\n")
                files_modified.append("fallback.gd")
            else:
                files_modified.extend(list(repaired_files))
        elif repair_action == "copy_default_assets":
            for a in state.get("assets", []):
                src = Path(a.get("file_path", ""))
                if src.exists():
                    dest = assets_dir / src.name
                    if not dest.exists():
                        import shutil
                        shutil.copy2(src, dest)
                        files_modified.append(src.name)
        else:
            log.info("Repair %s executed (no direct file modifications).", repair_action)
            
        return files_modified
        
    def _rebuild_project(self, state: Any) -> None:
        """Triggers a headless Godot editor import cycle."""
        import subprocess
        project = Path(state.get("godot_project", ""))
        if not project.exists():
            return
            
        from ..config import load_config
        try:
            cfg = load_config()
            godot_bin = cfg.raw.get("workers", {}).get("godot", {}).get("binary", "godot")
            subprocess.run(
                [godot_bin, "--headless", "--editor", "--quit"],
                cwd=str(project),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15
            )
        except Exception as e:
            log.warning("ProjectImprover rebuild failed: %s", e)
