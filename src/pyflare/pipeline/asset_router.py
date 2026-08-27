from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("appsuite.asset_router")

class AssetRouter:
    """Smart Asset Router selecting the optimal pipeline path based on format.
    - GLB/GLTF: Skip Blender entirely, direct Godot import and scene instancing.
    - FBX: Direct Godot import (skips Blender by default unless Blender is requested).
    - OBJ: Blender processing then Godot import.
    - BLEND: Blender processing.
    """
    @staticmethod
    def get_route(file_path: str) -> str:
        suffix = Path(file_path).suffix.lower()
        if suffix in (".glb", ".gltf"):
            return "direct_godot"
        elif suffix == ".fbx":
            return "direct_godot"
        elif suffix in (".obj", ".blend"):
            return "blender_to_godot"
        else:
            # Fallback
            return "direct_godot"

    @classmethod
    def route_assets(cls, assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for a in assets:
            fp = a.get("file_path", "")
            route = cls.get_route(fp)
            a["route"] = route
            logger.info("Asset Router: Asset %s (%s) routed via %s", a.get("name", "unnamed"), Path(fp).name, route)
        return assets
