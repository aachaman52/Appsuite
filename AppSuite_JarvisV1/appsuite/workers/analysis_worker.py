"""Analysis Worker - asset inspection, quality validation, dependency validation.

Supports OBJ geometry scanning (vertex/face counting).
For FBX/GLTF/GLB: validates structure via header checks since these are
binary or JSON formats that cannot be line-scanned like OBJ.
Provides structured failure reasons for each validation failure.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from ..core.state import WorkerStatus, WorkerResult

from .base import BaseWorker, WorkerError

MODEL_EXTENSIONS = {".obj", ".fbx", ".gltf", ".glb"}


class AnalysisWorker(BaseWorker):
    name = "analysis"

    def inspect_obj(self, path: Path) -> Dict[str, Any]:
        verts = faces = 0
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped.startswith("v "):
                        verts += 1
                    elif stripped.startswith("f "):
                        faces += 1
        except Exception as exc:
            raise WorkerError(f"Failed to read OBJ file {path.name}: {exc}") from exc
        return {"vertices": verts, "faces": faces}

    def inspect_fbx(self, path: Path) -> Dict[str, Any]:
        """Basic FBX validation: check magic bytes or FBXHeaderExtension keyword."""
        try:
            with open(path, "rb") as fh:
                header = fh.read(23)
            if header[:20] == b"Kaydara FBX Binary  ":
                return {"vertices": 0, "faces": 0, "format": "fbx_binary"}
            # Try ASCII FBX
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                sample = fh.read(512)
            if "FBXHeaderExtension" in sample or "FBXVersion" in sample:
                return {"vertices": 0, "faces": 0, "format": "fbx_ascii"}
            raise WorkerError(f"FBX header not recognized in {path.name}")
        except WorkerError:
            raise
        except Exception as exc:
            raise WorkerError(f"FBX read error in {path.name}: {exc}") from exc

    def inspect_gltf(self, path: Path) -> Dict[str, Any]:
        """Basic GLTF/GLB validation."""
        ext = path.suffix.lower()
        try:
            if ext == ".glb":
                with open(path, "rb") as fh:
                    magic = fh.read(4)
                if magic != b"glTF":
                    raise WorkerError(f"GLB magic bytes not found in {path.name}")
                return {"vertices": 0, "faces": 0, "format": "glb"}
            else:
                import json
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    data = json.load(fh)
                if "asset" not in data:
                    raise WorkerError(f"GLTF missing 'asset' field in {path.name}")
                mesh_count = len(data.get("meshes", []))
                return {"vertices": 0, "faces": 0, "format": "gltf", "mesh_count": mesh_count}
        except WorkerError:
            raise
        except Exception as exc:
            raise WorkerError(f"GLTF read error in {path.name}: {exc}") from exc

    def validate_materials(self, obj_path: Path) -> Dict[str, Any]:
        mtl_libs = []
        use_mtls = []
        for line in obj_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("mtllib "):
                parts = stripped.split(None, 1)
                if len(parts) > 1:
                    mtl_libs.append(parts[1].strip())
            elif stripped.startswith("usemtl "):
                parts = stripped.split(None, 1)
                if len(parts) > 1:
                    use_mtls.append(parts[1].strip())

        valid = True
        missing_mtls: List[str] = []
        if mtl_libs:
            for lib in mtl_libs:
                if not (obj_path.parent / lib).exists():
                    missing_mtls.append(lib)
            valid = len(missing_mtls) == 0

        return {
            "mtl_libs": mtl_libs,
            "use_mtls": use_mtls,
            "valid": valid,
            "missing_mtls": missing_mtls,
        }

    def quality_score(self, stats: Dict[str, Any], size: int) -> float:
        score = 0.0
        verts = stats.get("vertices", 0)
        faces = stats.get("faces", 0)
        # Non-OBJ formats get a pass on geometry counts
        if stats.get("format") in ("fbx_binary", "fbx_ascii", "glb", "gltf"):
            score = 0.8 if size > 1024 else 0.5
        else:
            if verts >= 8:
                score += 0.4
            if faces >= 6:
                score += 0.4
            if size > 0:
                score += 0.2
        return round(min(score, 1.0), 2)

    def analyze_textures_and_materials(self, path: Path) -> Dict[str, Any]:
        import json
        import re
        ext = path.suffix.lower()
        textures = []
        textures_external = []
        materials = []
        mat_to_tex = {}
        
        if ext == ".obj":
            obj_content = path.read_text(encoding="utf-8", errors="ignore")
            mtl_files = []
            for line in obj_content.splitlines():
                line = line.strip()
                if line.startswith("mtllib "):
                    parts = line.split(None, 1)
                    if len(parts) > 1:
                        mtl_files.append(parts[1].strip())
                elif line.startswith("usemtl "):
                    parts = line.split(None, 1)
                    if len(parts) > 1:
                        materials.append(parts[1].strip())
            
            for mtl_name in mtl_files:
                mtl_path = path.parent / mtl_name
                if mtl_path.exists():
                    mtl_content = mtl_path.read_text(encoding="utf-8", errors="ignore")
                    current_mat = None
                    for line in mtl_content.splitlines():
                        line = line.strip()
                        if line.startswith("newmtl "):
                            parts = line.split(None, 1)
                            if len(parts) > 1:
                                current_mat = parts[1].strip()
                        elif line.startswith("map_Kd ") and current_mat:
                            parts = line.split(None, 1)
                            if len(parts) > 1:
                                tex_path = parts[1].strip()
                                tex_name = Path(tex_path).name
                                textures.append(tex_name)
                                textures_external.append(tex_name)
                                mat_to_tex[current_mat] = tex_name

        elif ext in (".gltf", ".glb"):
            if ext == ".gltf":
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                    for img in data.get("images", []):
                        uri = img.get("uri")
                        if uri:
                            img_name = Path(uri).name
                            textures.append(img_name)
                            if not uri.startswith("data:") and "bufferView" not in img:
                                textures_external.append(img_name)
                    for mat in data.get("materials", []):
                        mat_name = mat.get("name", "unnamed")
                        materials.append(mat_name)
                        pbr = mat.get("pbrMetallicRoughness", {})
                        base_tex = pbr.get("baseColorTexture", {})
                        if "index" in base_tex:
                            tex_idx = base_tex["index"]
                            textures_list = data.get("textures", [])
                            if tex_idx < len(textures_list):
                                img_idx = textures_list[tex_idx].get("source")
                                images_list = data.get("images", [])
                                if img_idx is not None and img_idx < len(images_list):
                                    uri = images_list[img_idx].get("uri")
                                    if uri:
                                        mat_to_tex[mat_name] = Path(uri).name
                except Exception:
                    pass
            else:
                content = path.read_bytes()
                for m in re.finditer(rb'[\w\-_\.\/]+\.(png|jpg|jpeg|tga|bmp|webp)', content, re.IGNORECASE):
                    tex_name = m.group(0).decode("utf-8", errors="ignore")
                    textures.append(Path(tex_name).name)
                try:
                    header = content[:12]
                    if header[:4] == b"glTF":
                        offset = 12
                        while offset < len(content):
                            chunk_header = content[offset:offset+8]
                            if len(chunk_header) < 8:
                                break
                            chunk_length = int.from_bytes(chunk_header[:4], "little")
                            chunk_type = chunk_header[4:]
                            if chunk_type == b"JSON":
                                json_data = json.loads(content[offset+8:offset+8+chunk_length].decode("utf-8"))
                                for img in json_data.get("images", []):
                                    uri = img.get("uri")
                                    img_name = None
                                    if uri:
                                        img_name = Path(uri).name
                                    elif "name" in img:
                                        img_name = img["name"]
                                    
                                    if img_name:
                                        textures.append(img_name)
                                        if uri and not uri.startswith("data:") and "bufferView" not in img:
                                            textures_external.append(img_name)
                                for mat in json_data.get("materials", []):
                                    mat_name = mat.get("name", "unnamed")
                                    materials.append(mat_name)
                                    pbr = mat.get("pbrMetallicRoughness", {})
                                    if "baseColorTexture" in pbr:
                                        tex_idx = pbr["baseColorTexture"]["index"]
                                        textures_list = json_data.get("textures", [])
                                        if tex_idx < len(textures_list):
                                            img_idx = textures_list[tex_idx].get("source")
                                            images_list = json_data.get("images", [])
                                            if img_idx is not None and img_idx < len(images_list):
                                                img_obj = images_list[img_idx]
                                                img_name = img_obj.get("name") or Path(img_obj.get("uri", "")).name
                                                if img_name:
                                                    mat_to_tex[mat_name] = img_name
                                break
                            offset += 8 + chunk_length
                except Exception:
                    pass
                
        elif ext == ".fbx":
            content = path.read_bytes()
            for m in re.finditer(rb'Material::(\w+)', content):
                materials.append(m.group(1).decode("utf-8", errors="ignore"))
            for m in re.finditer(rb'[\w\-_\.\/]+\.(png|jpg|jpeg|tga|bmp|webp)', content, re.IGNORECASE):
                tex_name = m.group(0).decode("utf-8", errors="ignore")
                textures.append(Path(tex_name).name)
            
            # For FBX: if any image file exists in the directory, we consider the expected textures external.
            # Otherwise, we assume they are embedded (or absent).
            has_local_images = False
            for p in path.parent.rglob("*"):
                if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".tga", ".bmp", ".webp"):
                    has_local_images = True
                    break
            if has_local_images:
                textures_external = list(set(textures))

        textures = list(set(textures))
        textures_external = list(set(textures_external))
        materials = list(set(materials))
        return {
            "textures_expected": textures,
            "textures_external": textures_external,
            "materials_expected": materials,
            "material_to_texture": mat_to_tex,
            "has_textures": len(textures) > 0
        }

    def run(self, job: Dict[str, Any], state: Any) -> 'WorkerResult':
        min_q = float(self.config.get("min_quality_score", 0.4))
        analysed: List[Dict[str, Any]] = []
        rejected = 0

        for asset in state.get("assets", []):
            path = Path(asset["file_path"])
            if not path.exists():
                raise WorkerError(
                    f"Asset file missing: {path} "
                    f"(source={asset.get('source')}, role={asset.get('role')})"
                )

            ext = path.suffix.lower()
            stats: Dict[str, Any] = {}
            try:
                if ext == ".obj":
                    stats = self.inspect_obj(path)
                    mat_info = self.validate_materials(path)
                    asset["dependencies_ok"] = mat_info["valid"]
                    asset.setdefault("metadata", {}).update({
                        "mtl_libs": mat_info["mtl_libs"],
                        "use_mtls": mat_info["use_mtls"],
                        "missing_mtls": mat_info["missing_mtls"],
                    })
                elif ext == ".fbx":
                    stats = self.inspect_fbx(path)
                    asset["dependencies_ok"] = True
                elif ext in (".gltf", ".glb"):
                    stats = self.inspect_gltf(path)
                    asset["dependencies_ok"] = True
                else:
                    # Unknown format - pass with low score
                    stats = {"vertices": 0, "faces": 0}
                    asset["dependencies_ok"] = True
            except WorkerError as exc:
                self.log.warning("Asset failed inspection (%s): %s", path.name, exc)
                rejected += 1
                continue

            # Complete texture and material diagnostics
            diag = self.analyze_textures_and_materials(path)
            asset.setdefault("metadata", {}).update(diag)
            
            # Verify external texture files exist on disk
            missing_textures = []
            for tex in diag.get("textures_external", []):
                # Check path.parent or recursively in path.parent
                found = False
                for p in path.parent.rglob("*"):
                    if p.is_file() and (p.name.lower() == tex.lower() or p.stem.lower() == tex.lower()):
                        found = True
                        break
                if not found:
                    missing_textures.append(tex)
            
            if missing_textures:
                self.log.error(f"Asset {path.name} is missing textures: {missing_textures}")
                raise WorkerError("TEXTURE_NOT_FOUND")

            score = self.quality_score(stats, asset.get("file_size", path.stat().st_size))
            asset["quality_score"] = score
            asset.setdefault("metadata", {}).update(stats)

            if score < min_q:
                self.log.info(
                    "Asset rejected (score=%.2f < %.2f): %s", score, min_q, path.name
                )
                rejected += 1
                continue

            analysed.append(asset)

        if not analysed:
            raise WorkerError(
                f"No assets passed quality validation (rejected={rejected}). "
                "Check that model files are valid and not empty."
            )

        state["assets"] = analysed
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={
                "analysed": len(analysed),
                "rejected": rejected,
                "min_quality": min_q
            },
            reason="",
            metadata={}
        )