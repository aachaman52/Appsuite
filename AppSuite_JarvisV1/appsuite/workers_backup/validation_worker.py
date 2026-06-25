"""Validation Worker - pipeline validation, scene validation, output verification."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .base import BaseWorker, WorkerError


class ValidationWorker(BaseWorker):
    name = "validation"

    def run(self, job: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
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
        return {"passed": passed, "total": total, "checks": checks}