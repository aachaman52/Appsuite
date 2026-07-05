"""Blender Worker - import assets, materials, scale/transform fixes, scene + FBX export.

If a Blender binary is available it runs a generated headless script that performs
a real import + FBX export. Otherwise it computes the scene layout deterministically
and writes a scene manifest plus an ASCII FBX stub so downstream stages always
have inputs (graceful degradation).
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

from .base import BaseWorker, WorkerError
from ..core.asset_router import AssetRouter
from ..core.state import WorkerStatus, WorkerResult


def _grid_layout(count: int, spacing: float) -> List[List[float]]:
    """Place `count` items on a centred square grid."""
    side = max(1, math.ceil(math.sqrt(count)))
    positions = []
    offset = (side - 1) * spacing / 2.0
    for i in range(count):
        row, col = divmod(i, side)
        positions.append([col * spacing - offset, 0.0, row * spacing - offset])
    return positions


class BlenderWorker(BaseWorker):
    name = "blender"

    def __init__(self, *args, output_dir, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_dir = Path(output_dir)

    def _binary_available(self) -> bool:
        binary = self.config.get("binary", "blender")
        if binary and Path(binary).is_absolute() and Path(binary).exists():
            return True
        return shutil.which(binary) is not None

    def build_scene_layout(self, assets: List[Dict[str, Any]], template: Dict[str, Any]
                           ) -> Dict[str, Any]:
        # Group by role, then lay each role out on its own grid ring.
        by_role: Dict[str, List[Dict[str, Any]]] = {}
        for a in assets:
            by_role.setdefault(a["role"], []).append(a)
        objects = []
        ring = 0
        for role, items in by_role.items():
            spacing = 4.0 + ring * 2.0
            for pos, asset in zip(_grid_layout(len(items), spacing), items):
                objects.append({
                    "asset_id": asset["id"],
                    "name": f"{role}_{asset['id'][:6]}",
                    "role": role,
                    "source_file": asset["file_path"],
                    "route": asset.get("route", "direct_godot"),
                    "location": [round(pos[0] + ring * 1.5, 3), 0.0, round(pos[2], 3)],
                    "rotation": [0.0, 0.0, 0.0],
                    # fix scale: normalise everything to 1 unit, role-specific tweaks
                    "scale": [1.0, 1.0, 1.0],
                    "material": {"role": role, "base_color": _role_color(role)},
                })
            ring += 1
        return {
            "ground": template.get("ground", {}),
            "lighting": template.get("lighting", {}),
            "objects": objects,
        }

    def _render_blender_script(self, layout: Dict[str, Any], fbx_path: Path) -> str:
        payload = {
            "layout": layout,
            "fbx_path": str(fbx_path)
        }
        return f"""import json
import bpy
import os
payload = json.loads({repr(json.dumps(payload))})
layout = payload["layout"]
fbx_path = payload["fbx_path"]

bpy.ops.wm.read_factory_settings(use_empty=True)
for obj in layout["objects"]:
    if obj.get("route", "direct_godot") != "blender_to_godot":
        continue
    filepath = obj["source_file"]
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=filepath)
        elif ext in (".gltf", ".glb"):
            bpy.ops.import_scene.gltf(filepath=filepath)
        elif ext == ".obj":
            try:
                bpy.ops.import_scene.obj(filepath=filepath)
            except Exception:
                bpy.ops.wm.obj_import(filepath=filepath)
        else:
            bpy.ops.wm.obj_import(filepath=filepath)
    except Exception as e:
        print("Error importing " + str(filepath) + ": " + str(e))
    imported = bpy.context.selected_objects
    for o in imported:
        o.location = obj["location"]
        o.scale = obj["scale"]
        
        # Geometry repair / optimization
        if o.type == 'MESH':
            # Name normalization
            clean_name = "".join(c if c.isalnum() else "_" for c in o.name).lower()
            o.name = obj["role"] + "_" + clean_name
            
            # Select object to make it active for operations
            bpy.ops.object.select_all(action='DESELECT')
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            
            # Edit mode geometry cleanups: remove doubles, fix normals
            try:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.remove_doubles()
                bpy.ops.mesh.normals_make_consistent(inside=False)
                # Auto UV unwrapping if missing
                if not o.data.uv_layers:
                    bpy.ops.uv.smart_project()
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception as e:
                print("Repair failed on " + o.name + ": " + str(e))
                try:
                    bpy.ops.object.mode_set(mode='OBJECT')
                except Exception:
                    pass

            # Decimate / polygon reduction (e.g. reduction ratio of 0.8)
            try:
                decimate_mod = o.modifiers.new(name="Jarvis_Decimate", type='DECIMATE')
                decimate_mod.ratio = 0.8
                bpy.ops.object.modifier_apply(modifier="Jarvis_Decimate")
            except Exception as e:
                print("Decimation failed on " + o.name + ": " + str(e))

# ─── FALLBACK MATERIAL CREATION ───────────────────────────────────────
# If a mesh was imported without materials, automatically create and assign Jarvis_Fallback_Mat
fallback_material = None
for o in bpy.data.objects:
    if o.type == 'MESH' and (len(o.data.materials) == 0 or o.data.materials[0] is None):
        # Create fallback material on first use
        if fallback_material is None:
            fallback_material = bpy.data.materials.new(name="Jarvis_Fallback_Mat")
            fallback_material.use_nodes = True
            fallback_material.node_tree.nodes["Principled BSDF"].inputs[0].default_value = (0.8, 0.8, 0.8, 1.0)
        # Assign fallback material to mesh
        if len(o.data.materials) == 0:
            o.data.materials.append(fallback_material)
        else:
            o.data.materials[0] = fallback_material
        print("Auto-assigned Jarvis_Fallback_Mat to '" + o.name + "'")

# Blender validation checks before export
validation_errors = []
for o in bpy.data.objects:
    if o.type == 'MESH':
        if len(o.data.materials) == 0 or o.data.materials[0] is None:
            validation_errors.append("MATERIAL_NOT_ASSIGNED: Mesh '" + o.name + "' has no material assigned.")
            continue
        for mat in o.data.materials:
            if mat is None:
                continue
            has_texture = False
            # Check Blender Internal slots
            for slot in getattr(mat, "texture_slots", []):
                if slot is not None and slot.texture is not None:
                    if slot.texture.type == 'IMAGE':
                        has_texture = True
                        if slot.texture.image is not None:
                            tex_path = bpy.path.abspath(slot.texture.image.filepath)
                            if not os.path.exists(tex_path):
                                validation_errors.append("TEXTURE_NOT_FOUND: Texture file '" + tex_path + "' not found on disk.")
                        else:
                            validation_errors.append("TEXTURE_NOT_ASSIGNED: Texture slot exists but has no image assigned.")
            # Check Cycles nodes
            if getattr(mat, "use_nodes", False) and mat.node_tree is not None:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE':
                        has_texture = True
                        if node.image is not None:
                            tex_path = bpy.path.abspath(node.image.filepath)
                            if not os.path.exists(tex_path):
                                validation_errors.append("TEXTURE_NOT_FOUND: Texture file '" + tex_path + "' not found on disk.")
                        else:
                            validation_errors.append("TEXTURE_NOT_ASSIGNED: Texture node exists but has no image assigned.")

if validation_errors:
    err_file = os.path.join(os.path.dirname(fbx_path), "blender_validation_errors.json")
    with open(err_file, "w") as fh:
        json.dump(validation_errors, fh)
    import sys
    sys.exit(1)

bpy.ops.export_scene.fbx(filepath=fbx_path, path_mode='COPY', embed_textures=True)
"""

    def _run_blender(self, layout: Dict[str, Any], fbx_path: Path) -> bool:
        binary = self.config.get("binary", "blender")
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
            fh.write(self._render_blender_script(layout, fbx_path))
            script = fh.name
        proc = subprocess.run(
            [binary, "--background", "--python", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
        )
        print("BLENDER STDOUT:", proc.stdout)
        print("BLENDER STDERR:", proc.stderr)
        
        # Check validation errors from Blender
        err_file = fbx_path.parent / "blender_validation_errors.json"
        if err_file.exists():
            errors = json.loads(err_file.read_text(encoding="utf-8"))
            err_file.unlink()
            first_err = errors[0]
            if "MATERIAL_NOT_ASSIGNED" in first_err:
                raise WorkerError("MATERIAL_NOT_ASSIGNED")
            elif "TEXTURE_NOT_FOUND" in first_err:
                raise WorkerError("TEXTURE_NOT_FOUND")
            elif "TEXTURE_NOT_ASSIGNED" in first_err:
                raise WorkerError("TEXTURE_NOT_ASSIGNED")
            else:
                raise WorkerError(f"Blender validation failed: {first_err}")
                
        if proc.returncode != 0:
            print("--- Blender execution failed ---")
            print("STDOUT:", proc.stdout)
            print("STDERR:", proc.stderr)
            self.log.warning("Blender failed: %s", proc.stderr[-500:])
            return False
        return fbx_path.exists()

    def _verify_fbx_export(self, fbx_path: Path, expected_materials: List[str], expected_textures: List[str]) -> None:
        """Scan the exported FBX file to ensure materials and texture references survived."""
        if not fbx_path.exists() or fbx_path.stat().st_size == 0:
            raise WorkerError("RESOURCE_GENERATION_FAILURE")
            
        content = fbx_path.read_bytes()
        
        missing_materials = []
        for mat in expected_materials:
            mat_bytes = mat.encode("utf-8", errors="ignore")
            if mat_bytes not in content and mat_bytes.lower() not in content.lower():
                missing_materials.append(mat)
                
        missing_textures = []
        for tex in expected_textures:
            tex_bytes = tex.encode("utf-8", errors="ignore")
            if tex_bytes not in content and tex_bytes.lower() not in content.lower():
                missing_textures.append(tex)
                
        diagnostics = {
            "fbx_path": str(fbx_path),
            "size_bytes": fbx_path.stat().st_size,
            "expected_materials": expected_materials,
            "expected_textures": expected_textures,
            "materials_survived": [m for m in expected_materials if m not in missing_materials],
            "textures_survived": [t for t in expected_textures if t not in missing_textures],
            "missing_materials": missing_materials,
            "missing_textures": missing_textures
        }
        
        diag_path = fbx_path.parent / "fbx_diagnostics.json"
        diag_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
        
        if missing_materials:
            raise WorkerError("MATERIAL_NOT_ASSIGNED")
        if missing_textures:
            raise WorkerError("TEXTURE_NOT_ASSIGNED")

    def _write_fbx_stub(self, layout: Dict[str, Any], fbx_path: Path) -> None:
        """Write a minimal ASCII FBX header + object list (valid text FBX)."""
        lines = ["; FBX 7.4.0 project file generated by AppSuite",
                 "; ----------------------------------------------------",
                 "FBXHeaderExtension:  {", "  FBXVersion: 7400", "}",
                 "Objects:  {"]
        for o in layout.get("objects", []):
            name = o.get("name", o.get("role", "mesh"))
            location = o.get("location", [0, 0, 0])
            scale = o.get("scale", [1, 1, 1])
            lines.append(f'  Model: "Model::{name}", "Mesh" {{')
            lines.append(f'    Location: {location}')
            lines.append(f'    Scale: {scale}')
            lines.append("  }")
        lines.append("}")
        fbx_path.parent.mkdir(parents=True, exist_ok=True)
        fbx_path.write_text("\n".join(lines), encoding="utf-8")

    def run(self, job: Dict[str, Any], state: Any) -> 'WorkerResult':
        # Determine output directories based on Project system if present
        project_path = state.get("project_path")
        if project_path:
            project_dir = Path(project_path)
            assets_dir = Path(state["assets_path"])
            outputs_dir = Path(state["outputs_path"])
        else:
            project_dir = self.output_dir / job["id"] / "godot_project"
            assets_dir = self.output_dir / job["id"] / "assets"
            outputs_dir = self.output_dir / job["id"]
            
        assets_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)

        # Route assets if not already routed
        AssetRouter.route_assets(state.get("assets", []))

        # Convert only GLB/GLTF assets to OBJ that are routed via blender_to_godot
        for a in state.get("assets", []):
            if a.get("route", "direct_godot") != "blender_to_godot":
                continue
            path = Path(a["file_path"])
            if path.suffix.lower() in (".glb", ".gltf"):
                converted_obj = path.with_suffix(".obj")
                from appsuite.utils.gltf_converter import convert_glb_to_obj
                conv_diag = convert_glb_to_obj(path, converted_obj)
                a["file_path"] = str(converted_obj)
                a.setdefault("metadata", {}).update({
                    "materials_expected": conv_diag["materials"],
                    "textures_expected": conv_diag["textures"],
                    "material_to_texture": conv_diag["material_to_texture"],
                    "has_textures": len(conv_diag["textures"]) > 0
                })
        
        layout = self.build_scene_layout(state["assets"], state["template"])
        (outputs_dir / "scene.json").write_text(json.dumps(layout, indent=2), encoding="utf-8")
        
        state["scene_layout"] = layout
        
        # Check if Blender processing is actually required
        blender_required = any(a.get("route") == "blender_to_godot" for a in state.get("assets", []))
        
        if not blender_required:
            state["fbx_path"] = ""
            self.log.info("Asset Router: Skipping Blender stage since all assets route directly to Godot.")
            return WorkerResult(
                status=WorkerStatus.SUCCESS,
                data={
                    "objects": len(layout["objects"]),
                    "fbx": "",
                    "blender_binary_used": False,
                    "skipped_blender": True
                },
                reason="",
                metadata={}
            )

        fbx_path = assets_dir / "scene.fbx"
        used_blender = False
        if self._binary_available():
            try:
                used_blender = self.with_retry(
                    lambda: self._run_blender(layout, fbx_path), desc="blender export")
            except WorkerError as exc:
                if str(exc) in ("MATERIAL_NOT_ASSIGNED", "TEXTURE_NOT_FOUND", "TEXTURE_NOT_ASSIGNED"):
                    self.log.warning("Blender missing asset dependency: %s", exc)
                    return WorkerResult(
                        status=WorkerStatus.NEED_ASSET,
                        data={},
                        reason=str(exc),
                        metadata={}
                    )
                raise
            except Exception as exc:
                self.log.warning("Blender export error: %s", exc)
                
        if not fbx_path.exists() or fbx_path.stat().st_size == 0:
            self._write_fbx_stub(layout, fbx_path)
        else:
            # Perform FBX validation for assets that went through Blender
            expected_materials = []
            expected_textures = []
            for a in state.get("assets", []):
                if a.get("route") != "blender_to_godot":
                    continue
                meta = a.get("metadata", {})
                expected_materials.extend(meta.get("materials_expected", []))
                expected_textures.extend(meta.get("textures_expected", []))
            try:
                self._verify_fbx_export(fbx_path, expected_materials, expected_textures)
            except WorkerError as exc:
                if str(exc) in ("MATERIAL_NOT_ASSIGNED", "TEXTURE_NOT_ASSIGNED"):
                    self.log.warning("FBX validation missing asset dependency: %s", exc)
                    return WorkerResult(
                        status=WorkerStatus.NEED_ASSET,
                        data={},
                        reason=str(exc),
                        metadata={}
                    )
                raise

        state["fbx_path"] = str(fbx_path)
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={
                "objects": len(layout["objects"]),
                "fbx": str(fbx_path),
                "blender_binary_used": used_blender,
                "skipped_blender": False
            },
            reason="",
            metadata={}
        )

    def plan(self, job: Dict[str, Any], state: Any) -> List[str]:
        plan_tasks = []
        if any(a.get("route") == "blender_to_godot" for a in state.get("assets", [])):
            plan_tasks.append("optimize_assets_in_blender")
            plan_tasks.append("export_fbx_scene")
        else:
            plan_tasks.append("skip_blender_route_directly")
        return plan_tasks

    def verify(self, job: Dict[str, Any], state: Any, result: WorkerResult) -> Tuple[bool, str]:
        if result.status != WorkerStatus.SUCCESS:
            return False, f"status: {result.status.value}"
        blender_required = any(a.get("route") == "blender_to_godot" for a in state.get("assets", []))
        if blender_required:
            fbx_path_str = state.get("fbx_path", "")
            if not fbx_path_str:
                return False, "Blender was required but fbx_path is empty"
            fbx_path = Path(fbx_path_str)
            if not fbx_path.exists() or fbx_path.stat().st_size == 0:
                return False, f"FBX file does not exist or is empty: {fbx_path_str}"
        return True, "ok"

    def recover(self, job: Dict[str, Any], state: Any, exception: Exception) -> WorkerResult:
        self.log.warning("[blender] Recovery initiated. Falling back to ASCII FBX stub due to error: %s", exception)
        project_path = state.get("project_path")
        if project_path:
            assets_dir = Path(state["assets_path"])
        else:
            assets_dir = self.output_dir / job["id"] / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        fbx_path = assets_dir / "scene.fbx"
        layout = state.get("scene_layout", {})
        self._write_fbx_stub(layout, fbx_path)
        state["fbx_path"] = str(fbx_path)
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={
                "objects": len(layout.get("objects", [])),
                "fbx": str(fbx_path),
                "blender_binary_used": False,
                "skipped_blender": False,
                "recovered": True
            },
            reason="Recovered via ASCII FBX stub.",
            metadata={"recovered": True}
        )

    def report(self, job: Dict[str, Any], state: Any) -> Dict[str, Any]:
        fbx_path_str = state.get("fbx_path", "")
        fbx_size = Path(fbx_path_str).stat().st_size if fbx_path_str and Path(fbx_path_str).exists() else 0
        return {
            "worker": self.name,
            "fbx_path": fbx_path_str,
            "fbx_size_bytes": fbx_size,
            "timestamp": time.time()
        }


def _role_color(role: str) -> List[float]:
    palette = {
        "house": [0.55, 0.35, 0.2], "barrel": [0.45, 0.3, 0.15],
        "tree": [0.15, 0.5, 0.2], "road": [0.4, 0.4, 0.42],
        "npc": [0.8, 0.6, 0.5], "prop": [0.6, 0.6, 0.6],
    }
    return palette.get(role, [0.7, 0.7, 0.7])