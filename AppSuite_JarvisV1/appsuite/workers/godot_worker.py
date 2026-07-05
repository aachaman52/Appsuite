"""Godot Worker - import FBX/GLB directly, generate scenes/prefabs, lighting, collisions.

Produces a real, openable Godot 4 project (project.godot + .tscn scenes) using
either the exported Blender scene or instancing direct assets.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List
import time
from ..core.state import WorkerStatus, WorkerResult

from .base import BaseWorker, WorkerError

_PROJECT_GODOT = """; AppSuite generated Godot project
config_version=5

[application]
config/name="{name}"
run/main_scene="res://Scenes/main.tscn"
config/features=PackedStringArray("4.6")

[rendering]
lights_and_shadows/use_physical_light_units=false
"""


class GodotWorker(BaseWorker):
    name = "godot"

    def __init__(self, *args, output_dir, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_dir = Path(output_dir)

    def _binary_available(self) -> bool:
        binary = self.config.get("binary", "godot")
        if binary and Path(binary).is_absolute() and Path(binary).exists():
            return True
        return shutil.which(binary) is not None

    def _node(self, obj: Dict[str, Any], hide_mesh: bool = False) -> str:
        loc = obj.get("location", [0, 0, 0])
        scale = obj.get("scale", [1, 1, 1])
        name = obj.get("name", obj.get("role", "mesh"))
        
        visible_str = "visible = false\n" if hide_mesh else ""
        
        # StaticBody3D (collision) -> CSGBox3D (visual) + CollisionShape3D
        return (
            f'[node name="{name}" type="StaticBody3D" parent="."]\n'
            f'transform = Transform3D({scale[0]}, 0, 0, 0, {scale[1]}, 0, 0, 0, {scale[2]}, '
            f'{loc[0]}, {loc[1]}, {loc[2]})\n\n'
            f'[node name="Mesh" type="CSGBox3D" parent="{name}"]\n'
            f'{visible_str}'
            f'use_collision = true\n\n'
        )

    def generate_main_scene(self, layout: Dict[str, Any], project_dir: Path, is_fps: bool = False) -> Path:
        lighting = layout.get("lighting", {})
        ground = layout.get("ground", {})
        ambient = lighting.get("ambient", 0.3)
        gsize = ground.get("size", 100)
        
        fbx_path = project_dir / "Assets" / "scene.fbx"
        fbx_exists = fbx_path.exists()
        use_blender_scene = False
        if fbx_exists:
            try:
                with open(fbx_path, "rb") as f:
                    use_blender_scene = f.read(18).startswith(b"Kaydara FBX Binary")
            except Exception:
                pass

        ext_resources = {}
        res_id = 1
        
        ext_parts: List[str] = []
        sub_parts: List[str] = []
        node_parts: List[str] = []
        
        if is_fps:
            ext_parts.append('[ext_resource type="Script" path="res://scripts/player.gd" id="1_player_script"]\n\n')
            sub_parts.append('[sub_resource type="CapsuleShape3D" id="CapsuleShape3D_player"]\n')
            sub_parts.append('radius = 0.5\n')
            sub_parts.append('height = 2.0\n\n')

        if use_blender_scene:
            ext_parts.append('[ext_resource type="PackedScene" path="res://Assets/scene.fbx" id="1_scene"]\n\n')
        
        # Map each unique GLB/GLTF/FBX asset to an ext_resource ID
        for obj in layout.get("objects", []):
            route = obj.get("route", "direct_godot")
            if route == "direct_godot" or not use_blender_scene:
                src_name = Path(obj.get("source_file", "")).name
                asset_path = project_dir / "Assets" / src_name
                if asset_path.exists():
                    rel_res_path = f"res://Assets/{src_name}"
                    if rel_res_path not in ext_resources:
                        ext_resources[rel_res_path] = res_id
                        res_id += 1

        for rel_res_path, rid in ext_resources.items():
            ext_parts.append(f'[ext_resource type="PackedScene" path="{rel_res_path}" id="{rid}_scene"]\n\n')
            
        # Sky and Environment resources
        sub_parts.append('[sub_resource type="ProceduralSkyMaterial" id="SkyMat"]\n')
        sub_parts.append('sky_top_color = Color(0.384, 0.455, 0.549, 1)\n')
        sub_parts.append('sky_horizon_color = Color(0.647, 0.655, 0.671, 1)\n\n')
        
        sub_parts.append('[sub_resource type="Sky" id="SkyRes"]\n')
        sub_parts.append('sky_material = SubResource("SkyMat")\n\n')
        
        sub_parts.append('[sub_resource type="Environment" id="Env"]\n')
        sub_parts.append('background_mode = 2\n')
        sub_parts.append('sky = SubResource("SkyRes")\n')
        sub_parts.append('ambient_light_source = 3\n')
        sub_parts.append(f'ambient_light_color = Color(0.6, 0.7, 0.8, 1)\n')
        sub_parts.append(f'ambient_light_energy = {ambient}\n\n')
        
        # Ground Material
        sub_parts.append('[sub_resource type="StandardMaterial3D" id="GroundMaterial"]\n')
        sub_parts.append('albedo_color = Color(0.2, 0.45, 0.25, 1)\n\n')
        
        node_parts.append('[node name="Main" type="Node3D"]\n\n')
        
        # Player / Camera
        if is_fps:
            node_parts.append('[node name="Player" type="CharacterBody3D" parent="."]\n')
            node_parts.append('transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 2.0, 0)\n')
            node_parts.append('script = ExtResource("1_player_script")\n\n')
            
            node_parts.append('[node name="CollisionShape3D" type="CollisionShape3D" parent="Player"]\n')
            node_parts.append('shape = SubResource("CapsuleShape3D_player")\n\n')
            
            node_parts.append('[node name="Camera3D" type="Camera3D" parent="Player"]\n')
            node_parts.append('transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.8, 0)\n\n')
        else:
            # Camera
            node_parts.append('[node name="Camera3D" type="Camera3D" parent="."]\n')
            node_parts.append('transform = Transform3D(1, 0, 0, 0, 0.7, 0.7, 0, -0.7, 0.7, 0, 40, 40)\n\n')
        
        # Ground with collision
        node_parts.append('[node name="Ground" type="StaticBody3D" parent="."]\n\n')
        node_parts.append('[node name="GroundMesh" type="CSGBox3D" parent="Ground"]\n')
        node_parts.append(f'size = Vector3({gsize}, 0.2, {gsize})\n')
        node_parts.append('material = SubResource("GroundMaterial")\n')
        node_parts.append('use_collision = true\n\n')
        
        # Lighting
        node_parts.append('[node name="Sun" type="DirectionalLight3D" parent="."]\n')
        node_parts.append('transform = Transform3D(1, 0, 0, 0, 0.5, 0.86, 0, -0.86, 0.5, 0, 50, 0)\n')
        node_parts.append(f'shadow_enabled = {str(lighting.get("shadows", True)).lower()}\n\n')
        node_parts.append('[node name="WorldEnvironment" type="WorldEnvironment" parent="."]\n')
        node_parts.append('environment = SubResource("Env")\n\n')
        
        # Blender Scene Instance
        if use_blender_scene:
            node_parts.append('[node name="BlenderScene" parent="." instance=ExtResource("1_scene")]\n\n')
            
        # Objects
        objects = layout.get("objects", [])
        for obj in objects:
            route = obj.get("route", "direct_godot")
            src_name = Path(obj.get("source_file", "")).name
            rel_res_path = f"res://Assets/{src_name}"
            
            if (route == "direct_godot" or not use_blender_scene) and rel_res_path in ext_resources:
                rid = ext_resources[rel_res_path]
                loc = obj.get("location", [0, 0, 0])
                scale = obj.get("scale", [1, 1, 1])
                name = obj.get("name", obj.get("role", "object"))
                node_parts.append(
                    f'[node name="{name}" parent="." instance=ExtResource("{rid}_scene")]\n'
                    f'transform = Transform3D({scale[0]}, 0, 0, 0, {scale[1]}, 0, 0, 0, {scale[2]}, '
                    f'{loc[0]}, {loc[1]}, {loc[2]})\n\n'
                )
            else:
                node_parts.append(self._node(obj, hide_mesh=use_blender_scene))
                
        parts = ['[gd_scene format=3]\n\n'] + ext_parts + sub_parts + node_parts
            
        scene = project_dir / "Scenes" / "main.tscn"
        scene.parent.mkdir(parents=True, exist_ok=True)
        scene_content = "".join(parts)
        self.validate_scene_content(scene_content)
        scene.write_text(scene_content, encoding="utf-8")
        return scene

    def validate_scene_content(self, content: str) -> None:
        if not content.startswith("[gd_scene"):
            raise ValueError("Generated Godot scene is missing the gd_scene header tag.")

    def generate_prefabs(self, layout: Dict[str, Any], project_dir: Path) -> List[str]:
        prefab_dir = project_dir / "Scenes" / "prefabs"
        prefab_dir.mkdir(parents=True, exist_ok=True)
        roles = {o.get("role", "unknown") for o in layout.get("objects", [])}
        made = []
        for role in roles:
            content = (
                '[gd_scene format=3]\n\n'
                f'[node name="{role}" type="StaticBody3D"]\n\n'
                f'[node name="Mesh" type="CSGBox3D" parent="."]\n'
                'use_collision = true\n'
            )
            self.validate_scene_content(content)
            f = prefab_dir / f"{role}.tscn"
            f.write_text(content, encoding="utf-8")
            made.append(str(f.relative_to(project_dir)))
        return made

    def _run_import(self, project_dir: Path) -> bool:
        binary = self.config.get("binary", "godot")
        proc = subprocess.run(
            [binary, "--headless", "--path", str(project_dir), "--import"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
        if proc.returncode != 0:
            raise WorkerError("ASSET_IMPORT_FAILURE")
        return True

    def verify_scene_loads(self, scene_path: Path, project_dir: Path) -> None:
        if not scene_path.exists():
            raise WorkerError("SCENE_LOAD_FAILURE")
        content = scene_path.read_text(encoding="utf-8")
        if not content.startswith("[gd_scene"):
            raise WorkerError("SCENE_LOAD_FAILURE")
        
        # Check that ext_resources refer to existing files
        import re
        ext_resources = re.findall(r'path="res://([^"]+)"', content)
        for rel_path in ext_resources:
            abs_path = project_dir / rel_path
            if not abs_path.exists():
                raise WorkerError("SCENE_LOAD_FAILURE")

    def _launch_editor(self, project_dir: Path) -> bool:
        binary = self.config.get("binary", "godot")
        try:
            # Launch the editor in a new console/process on Windows so it doesn't block
            proc = subprocess.Popen(
                [binary, "--editor", "--path", str(project_dir)],
                creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, "CREATE_NEW_CONSOLE") else 0
            )
            # Sleep briefly to verify it doesn't crash instantly
            time.sleep(1.5)
            if proc.poll() is not None:
                if proc.returncode != 0:
                    raise WorkerError("PROJECT_OPEN_FAILURE")
                return False
            
            # Try to bring the window to the foreground
            time.sleep(0.5)
            cmd = f'(New-Object -ComObject WScript.Shell).AppActivate("Godot")'
            subprocess.run(["powershell", "-Command", cmd], capture_output=True, timeout=5)
            return True
        except Exception as exc:
            if isinstance(exc, WorkerError):
                raise
            raise WorkerError(f"PROJECT_OPEN_FAILURE: {exc}")

    def run(self, job: Dict[str, Any], state: Any) -> 'WorkerResult':
        binary = self.config.get("binary", "godot")
        if not shutil.which(binary) and not Path(binary).exists():
            raise WorkerError("GODOT_NOT_FOUND")

        layout = state["scene_layout"]
        
        project_path = state.get("project_path")
        if project_path:
            project_dir = Path(project_path)
            assets_dir = Path(state["assets_path"])
            scenes_dir = Path(state["scenes_path"])
        else:
            project_dir = self.output_dir / job["id"] / "godot_project"
            assets_dir = project_dir / "Assets"
            scenes_dir = project_dir / "Scenes"
            
        project_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)
        scenes_dir.mkdir(parents=True, exist_ok=True)

        # Write project file
        (project_dir / "project.godot").write_text(
            _PROJECT_GODOT.format(name=f"AppSuite_{job['id'][:8]}"), encoding="utf-8")
        
        # Copy scene fbx if exists (from Blender Worker) and not already there
        fbx_path_str = state.get("fbx_path", "")
        if fbx_path_str:
            fbx = Path(fbx_path_str)
            if fbx.is_file() and fbx.exists() and fbx.resolve() != (assets_dir / "scene.fbx").resolve():
                shutil.copy(fbx, assets_dir / "scene.fbx")
            
        # Copy individual assets and companion files (textures, mtl)
        copied_assets = []
        for a in state.get("assets", []):
            src_path_str = a.get("file_path", "")
            if not src_path_str:
                continue
            src_path = Path(src_path_str)
            if src_path.is_file() and src_path.exists():
                dest_path = assets_dir / src_path.name
                if src_path.resolve() != dest_path.resolve():
                    shutil.copy(src_path, dest_path)
                copied_assets.append(dest_path)
                
                # Check recursively for companion files (textures, materials) preserving relative layout
                for sibling in src_path.parent.rglob("*"):
                    if sibling.is_file() and sibling.name != src_path.name:
                        ext = sibling.suffix.lower()
                        if ext in {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".webp", ".mtl"}:
                            try:
                                rel_path = sibling.relative_to(src_path.parent)
                                sib_dest = assets_dir / rel_path
                            except ValueError:
                                sib_dest = assets_dir / sibling.name
                            sib_dest.parent.mkdir(parents=True, exist_ok=True)
                            if sibling.resolve() != sib_dest.resolve():
                                shutil.copy(sibling, sib_dest)

        is_fps = "fps" in str(job.get("prompt", "")).lower() or "shooter" in str(job.get("prompt", "")).lower() or layout.get("fps_mode", False)
        scene = self.generate_main_scene(layout, project_dir, is_fps=is_fps)
        prefabs = self.generate_prefabs(layout, project_dir)

        # Validate that the generated project resources exist on disk
        if not scene.exists() or not (project_dir / "project.godot").exists():
            raise WorkerError("RESOURCE_GENERATION_FAILURE")

        # Headless import
        imported = self._run_import(project_dir)

        # Verification of imported assets
        for copied_path in copied_assets:
            import_file = Path(str(copied_path) + ".import")
            if not import_file.exists():
                raise WorkerError("ASSET_IMPORT_FAILURE")
                
        # Verification of texture imports
        for file in assets_dir.glob("**/*"):
            if file.is_file() and file.suffix.lower() in {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".webp"}:
                import_file = Path(str(file) + ".import")
                if not import_file.exists():
                    raise WorkerError("TEXTURE_IMPORT_FAILURE")
                
        # Also check imported scene.fbx if expected
        if fbx_path_str:
            fbx = Path(fbx_path_str)
            if fbx.is_file() and fbx.exists():
                if not (assets_dir / "scene.fbx.import").exists():
                    raise WorkerError("ASSET_IMPORT_FAILURE")

        # Check compiled resources inside .godot/imported
        imported_dir = project_dir / ".godot" / "imported"
        if not imported_dir.exists() or not list(imported_dir.glob("*")):
            raise WorkerError("ASSET_IMPORT_FAILURE")

        # Verify scene loads
        self.verify_scene_loads(scene, project_dir)

        # Editor launch (non-headless)
        launched = self._launch_editor(project_dir)

        state["godot_project"] = str(project_dir)
        state["main_scene"] = str(scene)
        
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={
                "project": str(project_dir),
                "main_scene": str(scene.relative_to(project_dir)),
                "prefabs": prefabs,
                "godot_binary_used": imported,
                "editor_launched": launched,
                "assets_imported": len(copied_assets),
                "import_files": len(list(assets_dir.glob("*.import"))),
            },
            reason="",
            metadata={}
        )

    def plan(self, job: Dict[str, Any], state: Any) -> List[str]:
        return [
            "initialize_godot_project",
            "generate_main_scene",
            "import_assets_headless",
            "verify_scene_loadability"
        ]

    def verify(self, job: Dict[str, Any], state: Any, result: WorkerResult) -> Tuple[bool, str]:
        if result.status != WorkerStatus.SUCCESS:
            return False, f"status: {result.status.value}"
        proj_path = state.get("godot_project", "")
        if not proj_path or not Path(proj_path).exists():
            return False, "Godot project path does not exist"
        main_scene = state.get("main_scene", "")
        if not main_scene or not Path(main_scene).exists():
            return False, "Godot main scene does not exist"
        try:
            content = Path(main_scene).read_text(encoding="utf-8")
            if not content.startswith("[gd_scene"):
                return False, "Main scene file is missing the [gd_scene] tag"
        except Exception as exc:
            return False, f"Failed to read main scene file: {exc}"
        return True, "ok"

    def recover(self, job: Dict[str, Any], state: Any, exception: Exception) -> WorkerResult:
        self.log.warning("[godot] Recovery initiated. Creating basic procedural scene due to: %s", exception)
        project_dir = self.output_dir / job["id"] / "godot_project"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "Scenes").mkdir(parents=True, exist_ok=True)
        (project_dir / "Assets").mkdir(parents=True, exist_ok=True)
        
        (project_dir / "project.godot").write_text(
            _PROJECT_GODOT.format(name=f"AppSuite_{job['id'][:8]}"), encoding="utf-8")
        
        fallback_scene = (
            '[gd_scene format=3]\n\n'
            '[node name="Main" type="Node3D"]\n\n'
            '[node name="Ground" type="StaticBody3D" parent="."]\n\n'
            '[node name="GroundMesh" type="CSGBox3D" parent="Ground"]\n'
            'size = Vector3(100, 0.2, 100)\n'
            'use_collision = true\n\n'
            '[node name="Sun" type="DirectionalLight3D" parent="."]\n'
            'transform = Transform3D(1, 0, 0, 0, 0.5, 0.86, 0, -0.86, 0.5, 0, 50, 0)\n'
        )
        (project_dir / "Scenes" / "main.tscn").write_text(fallback_scene, encoding="utf-8")
        
        state["godot_project"] = str(project_dir)
        state["main_scene"] = str(project_dir / "Scenes" / "main.tscn")
        
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={
                "project": str(project_dir),
                "main_scene": "Scenes/main.tscn",
                "recovered": True
            },
            reason="Re-generated basic procedural project as fallback.",
            metadata={"recovered": True}
        )

    def report(self, job: Dict[str, Any], state: Any) -> Dict[str, Any]:
        proj_path = state.get("godot_project", "")
        scene_path = state.get("main_scene", "")
        scene_size = Path(scene_path).stat().st_size if scene_path and Path(scene_path).exists() else 0
        return {
            "worker": self.name,
            "project_path": proj_path,
            "main_scene_path": scene_path,
            "main_scene_size_bytes": scene_size,
            "timestamp": time.time()
        }