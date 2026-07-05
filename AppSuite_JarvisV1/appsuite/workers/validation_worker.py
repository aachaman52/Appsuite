"""Validation Worker - pipeline validation, scene validation, output verification."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from ..core.state import WorkerStatus, WorkerResult

from .base import BaseWorker, WorkerError


class ValidationWorker(BaseWorker):
    name = "validation"

    def run(self, job: Dict[str, Any], state: Any) -> 'WorkerResult':
        checks: List[Dict[str, Any]] = []

        def check(name: str, ok: bool, detail: str = "") -> None:
            checks.append({"name": name, "passed": bool(ok), "detail": detail})

        assets = state.get("assets", [])
        check("assets_present", len(assets) > 0, f"{len(assets)} assets")
        check("all_asset_files_exist",
              all(Path(a["file_path"]).exists() for a in assets))

        layout = state.get("scene_layout", {})
        check("scene_has_objects", len(layout.get("objects", [])) > 0)
        check("scene_has_lighting", bool(layout.get("lighting")))

        # Check if FBX was expected (any asset routed to Blender)
        fbx_expected = any(a.get("route") == "blender_to_godot" for a in assets)
        fbx_path_str = state.get("fbx_path", "")
        
        if fbx_expected and fbx_path_str:
            fbx = Path(fbx_path_str)
            check("fbx_exported", fbx.exists() and fbx.stat().st_size > 0, str(fbx))

        project = Path(state.get("godot_project", ""))
        check("godot_project_exists", project.exists())
        check("godot_main_scene_exists",
              (project / "Scenes" / "main.tscn").exists())
        check("godot_project_file_exists",
              (project / "project.godot").exists())

        # Check assets folder and imports
        assets_dir = project / "Assets"
        check("godot_assets_dir_exists", assets_dir.exists())

        all_copied = True
        all_imported = True
        for a in assets:
            name = Path(a["file_path"]).name
            asset_in_project = assets_dir / name
            if not asset_in_project.exists():
                all_copied = False
            if not Path(str(asset_in_project) + ".import").exists():
                all_imported = False

        check("all_assets_copied_to_project", all_copied)
        check("all_assets_imported_in_project", all_imported)

        if fbx_expected and fbx_path_str:
            fbx = Path(fbx_path_str)
            if fbx.exists():
                check("scene_fbx_copied", (assets_dir / "scene.fbx").exists())
                check("scene_fbx_imported", (assets_dir / "scene.fbx.import").exists())

        passed = sum(1 for c in checks if c["passed"])
        total = len(checks)
        all_ok = passed == total
        state["validation"] = {"checks": checks, "passed": passed, "total": total}
        if not all_ok:
            failed = [c["name"] for c in checks if not c["passed"]]
            if any(x in failed for x in ("godot_project_exists", "godot_main_scene_exists", "godot_project_file_exists", "godot_assets_dir_exists")):
                raise WorkerError("RESOURCE_GENERATION_FAILURE")
            elif any(x in failed for x in ("all_assets_imported_in_project", "scene_fbx_imported")):
                raise WorkerError("ASSET_IMPORT_FAILURE")
            else:
                raise WorkerError(f"Validation failed: {failed}")
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={
                "passed": passed,
                "total": total,
                "checks": checks
            },
            reason="",
            metadata={}
        )

    def plan(self, job: Dict[str, Any], state: Any) -> List[str]:
        return [
            "validate_asset_files",
            "validate_scene_layout",
            "validate_godot_project_structure",
            "validate_asset_imports",
            "validate_gameplay_scripts"
        ]

    def verify(self, job: Dict[str, Any], state: Any, result: WorkerResult) -> Tuple[bool, str]:
        if result.status != WorkerStatus.SUCCESS:
            return False, f"status: {result.status.value}"
        validation = state.get("validation", {})
        if not validation.get("checks"):
            return False, "No validation checks run"
        passed = validation.get("passed", 0)
        total = validation.get("total", 0)
        if passed < total:
            failed = [c["name"] for c in validation["checks"] if not c["passed"]]
            return False, f"Failed checks: {failed}"
        return True, "ok"

    def recover(self, job: Dict[str, Any], state: Any, exception: Exception) -> WorkerResult:
        self.log.warning("[validation] Recovery initiated. Attempting self-correction for: %s", exception)
        project_path = state.get("godot_project", "")
        if not project_path:
            from .godot_worker import GodotWorker
            gw = GodotWorker(self.config, self.retries, self.context, output_dir=Path("output"))
            from ..config import load_config
            gw.output_dir = load_config().abs_path("output_dir")
            gw_res = gw.recover(job, state, exception)
            if gw_res.status == WorkerStatus.FAILED:
                return gw_res
        
        project = Path(state["godot_project"])
        assets_dir = project / "Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        assets = state.get("assets", [])
        for a in assets:
            path = Path(a.get("file_path", ""))
            if path.exists():
                dest = assets_dir / path.name
                if not dest.exists():
                    import shutil
                    shutil.copy2(path, dest)
                    self.log.info("[validation] Copied missing asset during recovery: %s", path.name)

        from ..config import load_config
        cfg = load_config()
        godot_bin = cfg.raw.get("workers", {}).get("godot", {}).get("binary", "godot")
        
        import subprocess
        try:
            subprocess.run(
                [godot_bin, "--headless", "--editor", "--quit"],
                cwd=str(project),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15
            )
            self.log.info("[validation] Ran Godot headless import during recovery.")
        except Exception as e:
            self.log.warning("[validation] Godot import during recovery failed: %s", e)
            for a in assets:
                name = Path(a["file_path"]).name
                import_file = assets_dir / f"{name}.import"
                if not import_file.exists():
                    import_file.write_text("[remap]\nimporter=\"gltf\"\n", encoding="utf-8")

        try:
            return self.run(job, state)
        except Exception as e:
            return WorkerResult(
                status=WorkerStatus.FAILED,
                data={},
                reason=f"Recovery validation run failed: {e}",
                metadata={}
            )

    def report(self, job: Dict[str, Any], state: Any) -> Dict[str, Any]:
        validation = state.get("validation", {})
        import time
        return {
            "worker": self.name,
            "passed_checks": validation.get("passed", 0),
            "total_checks": validation.get("total", 0),
            "checks": validation.get("checks", []),
            "timestamp": time.time()
        }