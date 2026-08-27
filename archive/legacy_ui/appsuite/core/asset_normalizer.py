"""Normalize provider assets into a stable package layout.

Real-world asset sources arrive as loose files, archives, nested folders, OBJ/MTL
pairs, GLTF + BIN + textures, or single binary files. The normalizer gives the
rest of AppSuite one predictable contract:

    NormalizedAsset/
        asset_manifest.json
        <primary model>
        <materials/textures/buffers>

Workers can still consume ``asset["file_path"]`` as before, but that path now
points at the normalized primary model inside a clean package folder.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

MODEL_EXTENSIONS = {".obj", ".fbx", ".gltf", ".glb", ".blend"}
MATERIAL_EXTENSIONS = {".mtl"}
TEXTURE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".webp"}
BUFFER_EXTENSIONS = {".bin"}
COMPANION_EXTENSIONS = MATERIAL_EXTENSIONS | TEXTURE_EXTENSIONS | BUFFER_EXTENSIONS


@dataclass
class NormalizedAsset:
    asset_id: str
    job_id: str
    role: str
    source: str
    source_prompt: str
    package_dir: str
    manifest_path: str
    primary_model: str
    original_file_path: str
    files: Dict[str, List[str]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "job_id": self.job_id,
            "role": self.role,
            "source": self.source,
            "source_prompt": self.source_prompt,
            "package_dir": self.package_dir,
            "manifest_path": self.manifest_path,
            "primary_model": self.primary_model,
            "original_file_path": self.original_file_path,
            "files": self.files,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class AssetNormalizer:
    """Create a clean, manifest-backed package for each asset."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def normalize_many(
        self,
        assets: List[Dict[str, Any]],
        job_id: str,
        prompt: str = "",
    ) -> List[Dict[str, Any]]:
        normalized = []
        for index, asset in enumerate(assets):
            normalized.append(self.normalize(asset, job_id, prompt, index))
        return normalized

    def normalize(
        self,
        asset: Dict[str, Any],
        job_id: str,
        prompt: str = "",
        index: int = 0,
    ) -> Dict[str, Any]:
        src = Path(asset.get("file_path", ""))
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(f"Cannot normalize missing asset file: {src}")

        package_dir = self.base_dir / self._package_name(asset, src, index)
        package_dir.mkdir(parents=True, exist_ok=True)

        warnings: List[str] = []
        primary_model = self._copy_unique(src, package_dir)
        companions = self._collect_companions(src)
        copied_companions = [self._copy_unique(path, package_dir) for path in companions]

        texture_map = self._name_map(copied_companions, TEXTURE_EXTENSIONS)
        material_map = self._name_map(copied_companions, MATERIAL_EXTENSIONS)
        buffer_map = self._name_map(copied_companions, BUFFER_EXTENSIONS)

        if primary_model.suffix.lower() == ".obj":
            self._repair_obj(primary_model, material_map, warnings)
            for material in copied_companions:
                if material.suffix.lower() == ".mtl":
                    self._repair_mtl(material, texture_map, warnings)
        elif primary_model.suffix.lower() == ".gltf":
            self._repair_gltf(primary_model, texture_map, buffer_map, warnings)

        files = {
            "models": self._relative_files(package_dir, MODEL_EXTENSIONS),
            "materials": self._relative_files(package_dir, MATERIAL_EXTENSIONS),
            "textures": self._relative_files(package_dir, TEXTURE_EXTENSIONS),
            "buffers": self._relative_files(package_dir, BUFFER_EXTENSIONS),
        }

        normalized = NormalizedAsset(
            asset_id=str(asset.get("id", "")),
            job_id=job_id,
            role=str(asset.get("role", "unknown")),
            source=str(asset.get("source", "unknown")),
            source_prompt=prompt,
            package_dir=str(package_dir),
            manifest_path=str(package_dir / "asset_manifest.json"),
            primary_model=str(primary_model),
            original_file_path=str(src),
            files=files,
            warnings=warnings,
            metadata={
                "original_name": asset.get("name", src.stem),
                "format": primary_model.suffix.lower().lstrip("."),
                "source_url": asset.get("source_url"),
            },
        )

        manifest = normalized.to_dict()
        Path(normalized.manifest_path).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        out = dict(asset)
        out["original_file_path"] = str(src)
        out["file_path"] = str(primary_model)
        out["format"] = primary_model.suffix.lower().lstrip(".")
        out["normalized_asset"] = manifest
        out["normalized_manifest"] = normalized.manifest_path
        out.setdefault("metadata", {})["normalized_asset"] = manifest
        if warnings:
            out.setdefault("metadata", {})["normalization_warnings"] = warnings
        return out

    def _package_name(self, asset: Dict[str, Any], src: Path, index: int) -> str:
        role = self._safe_name(str(asset.get("role", "asset")))
        name = self._safe_name(str(asset.get("name", src.stem)))
        asset_id = str(asset.get("id", ""))[:8] or f"{index:03d}"
        return f"{role}_{name}_{asset_id}"[:96]

    def _safe_name(self, value: str) -> str:
        safe = "".join(c if c.isalnum() else "_" for c in value).strip("_")
        return safe or "asset"

    def _copy_unique(self, src: Path, package_dir: Path) -> Path:
        dest = package_dir / src.name
        if dest.exists() and src.resolve() != dest.resolve():
            dest = package_dir / f"{src.stem}_{abs(hash(str(src))) & 0xffff:x}{src.suffix}"
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        return dest

    def _collect_companions(self, primary: Path) -> List[Path]:
        candidates: Dict[str, Path] = {}
        for path in primary.parent.rglob("*"):
            if not path.is_file() or path.resolve() == primary.resolve():
                continue
            if path.suffix.lower() in COMPANION_EXTENSIONS:
                candidates[str(path.resolve())] = path
        return list(candidates.values())

    def _name_map(self, files: Iterable[Path], extensions: set[str]) -> Dict[str, Path]:
        mapping: Dict[str, Path] = {}
        for path in files:
            if path.suffix.lower() in extensions:
                mapping[path.name.lower()] = path
                mapping[path.stem.lower()] = path
        return mapping

    def _relative_files(self, package_dir: Path, extensions: set[str]) -> List[str]:
        return [
            str(path.relative_to(package_dir))
            for path in sorted(package_dir.iterdir())
            if path.is_file() and path.suffix.lower() in extensions
        ]

    def _repair_obj(
        self,
        obj_path: Path,
        material_map: Dict[str, Path],
        warnings: List[str],
    ) -> None:
        lines = obj_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        repaired: List[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("mtllib "):
                original = stripped.split(None, 1)[1].strip()
                material = material_map.get(Path(original).name.lower()) or material_map.get(
                    Path(original).stem.lower()
                )
                if material:
                    repaired.append(f"mtllib {material.name}")
                else:
                    warnings.append(f"Missing material library referenced by OBJ: {original}")
                    repaired.append(line)
            else:
                repaired.append(line)
        obj_path.write_text("\n".join(repaired) + "\n", encoding="utf-8")

    def _repair_mtl(
        self,
        mtl_path: Path,
        texture_map: Dict[str, Path],
        warnings: List[str],
    ) -> None:
        lines = mtl_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        repaired: List[str] = []
        texture_keys = {
            "map_Ka",
            "map_Kd",
            "map_Ks",
            "map_Ke",
            "map_Bump",
            "map_bump",
            "bump",
            "disp",
            "decal",
        }
        for line in lines:
            stripped = line.strip()
            parts = stripped.split(None, 1)
            if len(parts) == 2 and parts[0] in texture_keys:
                original = self._strip_texture_options(parts[1])
                texture = texture_map.get(Path(original).name.lower()) or texture_map.get(
                    Path(original).stem.lower()
                )
                if texture:
                    repaired.append(f"{parts[0]} {texture.name}")
                else:
                    warnings.append(f"Missing texture referenced by MTL: {original}")
                    repaired.append(line)
            else:
                repaired.append(line)
        mtl_path.write_text("\n".join(repaired) + "\n", encoding="utf-8")

    def _strip_texture_options(self, value: str) -> str:
        # Handles simple MTL options like "-s 1 1 1 texture.png".
        tokens = value.split()
        if not tokens:
            return value
        return tokens[-1]

    def _repair_gltf(
        self,
        gltf_path: Path,
        texture_map: Dict[str, Path],
        buffer_map: Dict[str, Path],
        warnings: List[str],
    ) -> None:
        try:
            data = json.loads(gltf_path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError as exc:
            warnings.append(f"Could not parse GLTF JSON for URI repair: {exc}")
            return

        changed = False
        for image in data.get("images", []):
            uri = image.get("uri")
            if not uri or uri.startswith("data:"):
                continue
            texture = texture_map.get(Path(uri).name.lower()) or texture_map.get(
                Path(uri).stem.lower()
            )
            if texture:
                image["uri"] = texture.name
                changed = True
            else:
                warnings.append(f"Missing image referenced by GLTF: {uri}")

        for buffer in data.get("buffers", []):
            uri = buffer.get("uri")
            if not uri or uri.startswith("data:"):
                continue
            buf = buffer_map.get(Path(uri).name.lower()) or buffer_map.get(Path(uri).stem.lower())
            if buf:
                buffer["uri"] = buf.name
                changed = True
            else:
                warnings.append(f"Missing buffer referenced by GLTF: {uri}")

        if changed:
            gltf_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
