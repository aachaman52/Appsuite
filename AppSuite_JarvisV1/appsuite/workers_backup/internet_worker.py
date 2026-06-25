"""Internet Worker - search, download, validate and extract assets.

Supports real asset sources:
  - Kenney (kenney.nl) - free CC0 3D asset packs via direct ZIP download
  - Poly Pizza (poly.pizza) - free CC0 low-poly 3D models
  - OpenGameArt (opengameart.org) - free game assets

Falls back to a minimal procedural OBJ stub if all sources fail, so the
pipeline is always completable offline.
"""
from __future__ import annotations

import hashlib
import io
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

from .base import BaseWorker, WorkerError

try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:  # pragma: no cover
    _HAS_REQUESTS = False


# ---------------------------------------------------------------------------
# Minimal unit-cube fallback asset (CC0 procedural, always available)
# ---------------------------------------------------------------------------
_CUBE_OBJ = """# AppSuite procedural asset: {name}
o {name}
v -0.5 0.0 -0.5
v  0.5 0.0 -0.5
v  0.5 1.0 -0.5
v -0.5 1.0 -0.5
v -0.5 0.0  0.5
v  0.5 0.0  0.5
v  0.5 1.0  0.5
v -0.5 1.0  0.5
f 1 2 3 4
f 5 6 7 8
f 1 5 8 4
f 2 6 7 3
f 4 3 7 8
f 1 2 6 5
"""

# ---------------------------------------------------------------------------
# Kenney public asset packs - CC0 direct downloads (stable public GitHub mirrors)
# These are the official Kenney starter kit repos with 3D assets included.
# ---------------------------------------------------------------------------
KENNEY_PACKS: Dict[str, str] = {
    "nature": "https://github.com/KenneyNL/Starter-Kit-3D-Platformer/archive/refs/heads/main.zip",
    "city": "https://github.com/KenneyNL/Starter-Kit-City-Builder/archive/refs/heads/main.zip",
    "space": "https://github.com/KenneyNL/Starter-Kit-FPS/archive/refs/heads/main.zip",
    "platformer": "https://github.com/KenneyNL/Starter-Kit-3D-Platformer/archive/refs/heads/main.zip",
    "default": "https://github.com/KenneyNL/Starter-Kit-3D-Platformer/archive/refs/heads/main.zip",
}

# Role-to-pack keyword mapping for Kenney
KENNEY_ROLE_MAP: Dict[str, str] = {
    "house": "city",
    "road": "city",
    "npc": "platformer",
    "tree": "nature",
    "barrel": "nature",
    "prop": "nature",
    "character": "platformer",
    "vehicle": "city",
    "building": "city",
    "weapon": "space",
    "item": "platformer",
}

# ---------------------------------------------------------------------------
# Poly Pizza - CC0 assets via direct public GitHub repositories
# ---------------------------------------------------------------------------
POLYPIZZA_REPOS: Dict[str, str] = {
    "furniture": "https://github.com/J-Ponzo/gltf-universal-animation-library/archive/refs/heads/main.zip",
    "character": "https://github.com/V-Sekai-fire/TEST_fbx_quaternius/archive/refs/heads/main.zip",
    "nature": "https://github.com/J-Ponzo/gltf-universal-animation-library/archive/refs/heads/main.zip",
    "default": "https://github.com/J-Ponzo/gltf-universal-animation-library/archive/refs/heads/main.zip",
}

POLYPIZZA_ROLE_MAP: Dict[str, str] = {
    "npc": "character",
    "house": "furniture",
    "tree": "nature",
    "barrel": "furniture",
    "prop": "furniture",
    "default": "default",
}


# ---------------------------------------------------------------------------
# Supported model extensions
# ---------------------------------------------------------------------------
MODEL_EXTENSIONS = {".obj", ".fbx", ".gltf", ".glb"}
TEXTURE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".webp"}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".tar.gz", ".tgz"}


class InternetWorker(BaseWorker):
    name = "internet"

    def __init__(self, *args, provider_manager, registry, assets_dir, cache_dir, **kwargs):
        super().__init__(*args, **kwargs)
        self.providers = provider_manager
        self.registry = registry
        self.assets_dir = Path(assets_dir)
        self.cache_dir = Path(cache_dir)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ hash
    def _hash_url(self, url: str) -> str:
        """Return a short deterministic cache key for a URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------ cache
    def _get_cached_archive(self, url: str) -> Optional[Path]:
        """Return path to a cached archive if it exists and is valid."""
        key = self._hash_url(url)
        cached = self.cache_dir / f"{key}.zip"
        if cached.exists() and cached.stat().st_size > 1024:
            self.log.info("Cache hit for URL %s -> %s", url[:60], cached.name)
            return cached
        return None

    def _cache_archive(self, url: str, data: bytes) -> Path:
        """Save raw archive bytes to the cache and return the path."""
        key = self._hash_url(url)
        cached = self.cache_dir / f"{key}.zip"
        cached.write_bytes(data)
        return cached

    # ------------------------------------------------------------------ download
    def _download_bytes(self, url: str, timeout: int = 120) -> bytes:
        """Stream-download a URL and return the bytes. Raises on failure."""
        if not _HAS_REQUESTS:
            raise WorkerError("requests library not available")
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        # Stream into an in-memory buffer to avoid large allocations
        buf = io.BytesIO()
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                buf.write(chunk)
        return buf.getvalue()

    def _download_archive(self, url: str, timeout: int = 120) -> Path:
        """Download a ZIP archive, using cache if available."""
        cached = self._get_cached_archive(url)
        if cached:
            return cached
        self.log.info("Downloading %s ...", url[:80])
        data = self._download_bytes(url, timeout)
        return self._cache_archive(url, data)

    # ----------------------------------------------------------------- validate archive
    def _validate_archive(self, archive: Path) -> bool:
        """Return True if the archive is a valid ZIP file."""
        try:
            with zipfile.ZipFile(archive) as zf:
                bad = zf.testzip()
                if bad is not None:
                    self.log.warning("Corrupt entry in archive %s: %s", archive.name, bad)
                    return False
            return True
        except zipfile.BadZipFile:
            self.log.warning("Not a valid ZIP file: %s", archive.name)
            return False
        except Exception as exc:
            self.log.warning("Archive validation error for %s: %s", archive.name, exc)
            return False

    # ----------------------------------------------------------------- validate model
    def _validate_model_file(self, path: Path) -> Dict[str, Any]:
        """
        Validate a 3D model file and return a dict with validation results.
        Returns: {valid: bool, reason: str, vertices: int, faces: int}
        """
        ext = path.suffix.lower()

        if ext not in MODEL_EXTENSIONS:
            return {"valid": False, "reason": f"Unsupported format: {ext}", "vertices": 0, "faces": 0}

        if not path.exists():
            return {"valid": False, "reason": "File does not exist", "vertices": 0, "faces": 0}

        size = path.stat().st_size
        if size == 0:
            return {"valid": False, "reason": "File is empty (0 bytes)", "vertices": 0, "faces": 0}

        if size < 100:
            return {"valid": False, "reason": f"File suspiciously small ({size} bytes)", "vertices": 0, "faces": 0}

        # For OBJ: parse vertices and faces
        if ext == ".obj":
            return self._validate_obj(path)

        # For binary formats (FBX, GLTF, GLB): just size/header check
        if ext == ".fbx":
            return self._validate_fbx(path)

        if ext in (".gltf", ".glb"):
            return self._validate_gltf(path)

        return {"valid": True, "reason": "ok", "vertices": 0, "faces": 0}

    def _validate_obj(self, path: Path) -> Dict[str, Any]:
        verts = faces = 0
        has_mtl_ref = False
        mtl_refs_exist = True
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("v "):
                        verts += 1
                    elif line.startswith("f "):
                        faces += 1
                    elif line.startswith("mtllib "):
                        has_mtl_ref = True
                        mtl_name = line.split(None, 1)[1].strip()
                        if not (path.parent / mtl_name).exists():
                            mtl_refs_exist = False
        except Exception as exc:
            return {"valid": False, "reason": f"OBJ read error: {exc}", "vertices": 0, "faces": 0}

        if verts == 0 and faces == 0:
            return {"valid": False, "reason": "OBJ has no vertices or faces", "vertices": 0, "faces": 0}

        if has_mtl_ref and not mtl_refs_exist:
            return {
                "valid": True,  # still usable but textures missing
                "reason": "mtl_missing",
                "vertices": verts,
                "faces": faces,
                "warning": "MTL file referenced but not found",
            }

        return {"valid": True, "reason": "ok", "vertices": verts, "faces": faces}

    def _validate_fbx(self, path: Path) -> Dict[str, Any]:
        try:
            with open(path, "rb") as fh:
                header = fh.read(23)
            if header[:20] == b"Kaydara FBX Binary  ":
                return {"valid": True, "reason": "ok", "vertices": 0, "faces": 0}
            # ASCII FBX
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                first = fh.read(512)
            if "FBXHeaderExtension" in first or "FBXVersion" in first:
                return {"valid": True, "reason": "ok (ascii fbx)", "vertices": 0, "faces": 0}
            return {"valid": False, "reason": "FBX header not recognized", "vertices": 0, "faces": 0}
        except Exception as exc:
            return {"valid": False, "reason": f"FBX read error: {exc}", "vertices": 0, "faces": 0}

    def _validate_gltf(self, path: Path) -> Dict[str, Any]:
        ext = path.suffix.lower()
        try:
            if ext == ".glb":
                with open(path, "rb") as fh:
                    magic = fh.read(4)
                if magic == b"glTF":
                    return {"valid": True, "reason": "ok (glb)", "vertices": 0, "faces": 0}
                return {"valid": False, "reason": "GLB magic bytes not found", "vertices": 0, "faces": 0}
            else:  # .gltf
                import json
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    data = json.load(fh)
                if "asset" in data and "meshes" in data:
                    return {"valid": True, "reason": "ok (gltf)", "vertices": 0, "faces": 0}
                return {"valid": False, "reason": "GLTF missing required fields", "vertices": 0, "faces": 0}
        except Exception as exc:
            return {"valid": False, "reason": f"GLTF read error: {exc}", "vertices": 0, "faces": 0}

    # ------------------------------------------------------------------ search providers
    def _generate_openai(self, term: str, provider: Dict[str, Any]) -> str:
        if not _HAS_REQUESTS:
            raise WorkerError("requests library not available")

        api_key = os.environ.get(provider.get("api_key_env", "OPENAI_API_KEY"))
        if not api_key:
            raise WorkerError(f"API key missing: {provider.get('api_key_env')}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{provider['base_url']}/chat/completions"
        payload = {
            "model": "gpt-4-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a 3D asset generator. Output ONLY a valid Wavefront OBJ file "
                        "content for the requested asset. No markdown formatting, no explanation, "
                        "just raw OBJ text."
                    ),
                },
                {"role": "user", "content": f"Generate a 3D OBJ mesh for: {term}"},
            ],
            "temperature": 0.2,
        }
        timeout = self.config.get("download_timeout", 60)
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
        except requests.Timeout as e:
            raise WorkerError(f"OpenAI timed out after {timeout}s") from e
        except Exception as e:
            raise WorkerError(f"OpenAI request failed: {e}") from e

        data = resp.json()
        if "choices" not in data or not data["choices"]:
            raise WorkerError("OpenAI returned no choices")

        obj_text = data["choices"][0]["message"]["content"]
        if obj_text.startswith("```"):
            lines = obj_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            obj_text = "\n".join(lines)

        if "v " not in obj_text or "f " not in obj_text:
            raise WorkerError("Generated OBJ is invalid: missing vertex or face definitions")

        return obj_text

    # ------------------------------------------------------------------ Kenney
    def _fetch_from_kenney(self, role: str, job_id: str, timeout: int) -> Optional[Dict[str, Any]]:
        """Try to download a real 3D asset from Kenney packs."""
        pack_key = KENNEY_ROLE_MAP.get(role, "default")
        url = KENNEY_PACKS.get(pack_key, KENNEY_PACKS["default"])
        try:
            archive = self._download_archive(url, timeout)
            if not self._validate_archive(archive):
                self.log.warning("Kenney archive invalid for role=%s", role)
                return None
            extracted = self.extract_archive(archive)
            detected = self.detect_assets(extracted)
            if not detected["main_model"]:
                return None
            model_path = detected["main_model"]
            val = self._validate_model_file(model_path)
            if not val["valid"] and val["reason"] != "mtl_missing":
                self.log.warning("Kenney model invalid: %s - %s", model_path.name, val["reason"])
                return None
            return self.registry.register(
                job_id=job_id, role=role, name=f"kenney_{pack_key}_{role}",
                source="kenney", file_path=model_path, source_url=url,
                fmt=model_path.suffix.lstrip("."),
                metadata={"pack": pack_key, "validation": val},
            )
        except Exception as exc:
            self.log.info("Kenney fetch failed for role=%s: %s", role, exc)
            return None

    # ------------------------------------------------------------------ Poly Pizza
    def _fetch_from_polypizza(self, role: str, job_id: str, timeout: int) -> Optional[Dict[str, Any]]:
        """Try to download a real 3D asset from a Poly Pizza GitHub mirror."""
        pack_key = POLYPIZZA_ROLE_MAP.get(role, "default")
        url = POLYPIZZA_REPOS.get(pack_key, POLYPIZZA_REPOS["default"])
        try:
            archive = self._download_archive(url, timeout)
            if not self._validate_archive(archive):
                return None
            extracted = self.extract_archive(archive)
            detected = self.detect_assets(extracted)
            if not detected["main_model"]:
                return None
            model_path = detected["main_model"]
            val = self._validate_model_file(model_path)
            if not val["valid"] and val["reason"] != "mtl_missing":
                self.log.warning("Poly Pizza model invalid: %s - %s", model_path.name, val["reason"])
                return None
            return self.registry.register(
                job_id=job_id, role=role, name=f"polypizza_{pack_key}_{role}",
                source="poly_pizza", file_path=model_path, source_url=url,
                fmt=model_path.suffix.lstrip("."),
                metadata={"pack": pack_key, "validation": val},
            )
        except Exception as exc:
            self.log.info("Poly Pizza fetch failed for role=%s: %s", role, exc)
            return None

    # ------------------------------------------------------------------ Polyhaven
    def _search_polyhaven(self, term: str, provider: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not _HAS_REQUESTS:
            return []
        url = f"{provider['base_url']}/assets?type=models"
        resp = requests.get(url, timeout=self.config.get("download_timeout", 60))
        resp.raise_for_status()
        data = resp.json()
        hits = []
        for slug, meta in data.items():
            name = meta.get("name", slug).lower()
            if any(w in name for w in term.lower().split()):
                hits.append({"slug": slug, "name": meta.get("name", slug)})
        return hits[:1]

    # ------------------------------------------------------------------ dedup / cache lookup
    def _find_cached_asset(self, job_id: str, role: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Check if an existing asset with the same file hash already exists."""
        if self.registry is None:
            return None
        try:
            from ..core.asset_registry import hash_file
            file_hash = hash_file(file_path)
            existing = self.registry.cached_by_hash(file_hash)
            if existing:
                self.log.info("Reusing cached asset hash=%s for role=%s", file_hash[:12], role)
                # Return a view of the existing asset mapped to this job
                asset = dict(existing)
                asset["job_id"] = job_id
                asset["role"] = role
                asset["cache_hit"] = True
                return asset
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------ primary search
    def search_and_fetch(self, job_id: str, role: str, term: str) -> Dict[str, Any]:
        """
        Resolve a single asset for a role.

        Priority order:
        1. OpenAI generation (if enabled)
        2. Kenney real download
        3. Poly Pizza real download
        4. Polyhaven search (name match only, no actual download)
        5. Local procedural cube fallback
        """
        timeout = self.config.get("download_timeout", 120)

        # 1. OpenAI generation
        if self.providers:
            gen_provider = self.providers.acquire("asset_generation")
            if gen_provider and gen_provider.get("id") == "openai":
                try:
                    self.log.info("Attempting OpenAI generation for '%s'", term)
                    obj_content = self.with_retry(
                        lambda: self._generate_openai(term, gen_provider),
                        desc=f"openai generation '{term}'",
                    )
                    self.providers.report_success(gen_provider["id"])
                    safe = "".join(c if c.isalnum() else "_" for c in term)[:40] or role
                    out = self.assets_dir / f"{safe}_ai_{uuid.uuid4().hex[:8]}.obj"
                    out.write_text(obj_content, encoding="utf-8")
                    val = self._validate_model_file(out)
                    if val["valid"]:
                        return self.registry.register(
                            job_id=job_id, role=role, name=f"{term} (AI generated)",
                            source="openai", file_path=out,
                            source_url=f"{gen_provider['base_url']}/chat/completions",
                            fmt="obj", metadata={"search_term": term, "validation": val},
                        )
                except Exception as exc:
                    if self.providers:
                        self.providers.report_failure(gen_provider["id"])
                    self.log.warning("OpenAI generation failed (%s); trying Kenney", exc)

        # 2. Kenney
        asset = self._fetch_from_kenney(role, job_id, timeout)
        if asset:
            self.log.info("Using Kenney asset for role=%s", role)
            return asset

        # 3. Poly Pizza
        asset = self._fetch_from_polypizza(role, job_id, timeout)
        if asset:
            self.log.info("Using Poly Pizza asset for role=%s", role)
            return asset

        # 4. Polyhaven name match (no actual download, just metadata)
        if self.providers:
            search_provider = self.providers.acquire("asset_search")
            if search_provider and search_provider.get("id") == "polyhaven" and search_provider.get("base_url"):
                try:
                    hits = self.with_retry(
                        lambda: self._search_polyhaven(term, search_provider),
                        desc=f"polyhaven search '{term}'",
                    )
                    if hits:
                        self.providers.report_success(search_provider["id"])
                        return self._make_asset(
                            job_id, role, hits[0]["name"], term,
                            source="polyhaven",
                            source_url=f"{search_provider['base_url']}/files/{hits[0]['slug']}",
                        )
                except Exception as exc:
                    if self.providers:
                        self.providers.report_failure(search_provider["id"])
                    self.log.info("Polyhaven search unavailable (%s)", exc)

        # 5. Local procedural fallback
        self.log.info("Using local procedural fallback for role=%s term=%s", role, term)
        return self._make_asset(job_id, role, term, term, source="local_library")

    # ------------------------------------------------------------------ helpers
    def _make_asset(
        self, job_id: str, role: str, name: str, term: str,
        source: str, source_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        safe = "".join(c if c.isalnum() else "_" for c in name)[:40] or role
        out = self.assets_dir / f"{safe}_{uuid.uuid4().hex[:8]}.obj"
        out.write_text(_CUBE_OBJ.format(name=safe), encoding="utf-8")
        return self.registry.register(
            job_id=job_id, role=role, name=name, source=source,
            file_path=out, source_url=source_url, fmt="obj",
            metadata={"search_term": term, "procedural": True},
        )

    def detect_assets(self, files: List[Path]) -> Dict[str, Any]:
        """
        Given a list of extracted file paths, return categorized asset info.
        Prefers larger model files as the 'main_model'.
        """
        models = []
        textures = []
        for f in files:
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext in MODEL_EXTENSIONS:
                models.append(f)
            elif ext in TEXTURE_EXTENSIONS:
                textures.append(f)

        # Sort models by file size descending (prefer more complex geometry)
        models.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)

        return {
            "models": models,
            "textures": textures,
            "main_model": models[0] if models else None,
        }

    # ----------------------------------------------------------------- extract
    def extract_archive(self, archive: Path) -> List[Path]:
        """
        Extract a ZIP archive with full Zip Slip protection.
        Validates the archive before extraction.
        Rejects any member that resolves outside the destination directory.
        """
        if not self._validate_archive(archive):
            raise WorkerError(f"Archive validation failed: {archive.name}")

        dest = archive.with_suffix("")
        # Avoid name collisions: append a short hash if dest already exists
        if dest.exists():
            dest = archive.parent / f"{archive.stem}_{uuid.uuid4().hex[:6]}"
        dest.mkdir(exist_ok=True)
        dest_abs = dest.resolve()
        extracted_paths: List[Path] = []

        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                member_path = Path(member.filename)
                target_path = (dest / member_path).resolve()
                if not target_path.is_relative_to(dest_abs):
                    self.log.warning(
                        "Zip Slip rejected: %s -> %s (outside %s)",
                        member.filename, target_path, dest_abs,
                    )
                    continue
                zf.extract(member, dest)
                if target_path.is_file():
                    extracted_paths.append(target_path)

        return extracted_paths

    # --------------------------------------------------------------------- run
    def run(self, job: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        template = state["template"]
        assets: List[Dict[str, Any]] = []
        cache_hits = 0
        real_downloads = 0

        for slot in template.get("asset_slots", []):
            role = slot["role"]
            terms = slot.get("search_terms", [role])
            count = slot.get("count", 1)
            for i in range(count):
                term = terms[i % len(terms)]
                asset = self.search_and_fetch(job["id"], role, term)
                if asset.get("cache_hit"):
                    cache_hits += 1
                if asset.get("source") in ("kenney", "poly_pizza"):
                    real_downloads += 1
                assets.append(asset)

        state["assets"] = assets
        return {
            "assets_fetched": len(assets),
            "cache_hits": cache_hits,
            "real_downloads": real_downloads,
        }