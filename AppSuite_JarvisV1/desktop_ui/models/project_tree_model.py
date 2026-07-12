import os
from pathlib import Path
from appsuite.config import load_config, PROJECT_ROOT


class ProjectNode:
    def __init__(self, name: str, is_dir: bool = True, path: str = ""):
        self.name = name
        self.is_dir = is_dir
        self.path = path
        self.children = []

    def add_child(self, child) -> None:
        self.children.append(child)


class ProjectTreeModel:
    def __init__(self) -> None:
        self.root = ProjectNode("AppSuite", is_dir=True, path=str(PROJECT_ROOT))
        self.setup_real_data()

    def setup_real_data(self) -> None:
        try:
            config = load_config()
            
            # 1. Output/Projects Folder
            projects_dir = config.abs_path("output_dir") / "projects"
            projects_node = ProjectNode("Projects (Generated)", is_dir=True, path=str(projects_dir))
            self._populate_dir_node(projects_node, projects_dir)
            self.root.add_child(projects_node)

            # 2. Data Assets Folder
            assets_dir = config.abs_path("assets_dir")
            assets_node = ProjectNode("Assets Cache", is_dir=True, path=str(assets_dir))
            self._populate_dir_node(assets_node, assets_dir)
            self.root.add_child(assets_node)

            # 3. Config/Templates
            config_dir = PROJECT_ROOT / "config"
            config_node = ProjectNode("Config & Templates", is_dir=True, path=str(config_dir))
            self._populate_dir_node(config_node, config_dir)
            self.root.add_child(config_node)
            
        except Exception as e:
            print(f"[ProjectTreeModel] Error reading project files: {e}")
            # Fallback mock data if bootstrapping fails
            self.setup_mock_data()

    def _populate_dir_node(self, node: ProjectNode, dir_path: Path) -> None:
        if not dir_path.exists() or not dir_path.is_dir():
            return
        try:
            for item in sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                # Avoid pycache and hidden paths
                if item.name.startswith(".") or item.name == "__pycache__":
                    continue
                child_node = ProjectNode(item.name, is_dir=item.is_dir(), path=str(item))
                node.add_child(child_node)
                # Recurse up to 2 directories deep to prevent lag on big directories
                if item.is_dir():
                    self._populate_dir_node(child_node, item)
        except Exception:
            pass

    def setup_mock_data(self) -> None:
        # Fallback Mock Data
        assets = ProjectNode("Assets Cache")
        assets.add_child(ProjectNode("scenes", is_dir=True))
        assets.add_child(ProjectNode("road_intersection.glb", is_dir=False))
        self.root.add_child(assets)

        jobs = ProjectNode("Projects (Generated)")
        jobs.add_child(ProjectNode("gta_street_block", is_dir=True))
        self.root.add_child(jobs)
