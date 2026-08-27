from __future__ import annotations
import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

class BasePlugin:
    """Base class for all Jarvis OS dynamic plugins."""
    @property
    def plugin_name(self) -> str:
        raise NotImplementedError
        
    @property
    def plugin_type(self) -> str:
        # e.g., 'worker', 'agent', 'provider', 'planner', 'validator', 'deploy'
        raise NotImplementedError


class PluginManager:
    """Discovers, loads, and registers plugins dynamically from the plugins folder."""
    
    def __init__(self, plugins_dir: Path, event_bus: Optional[Any] = None) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.event_bus = event_bus
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_plugins: Dict[str, BasePlugin] = {}
        
    def discover_and_load(self) -> List[BasePlugin]:
        """Scans plugins directory, imports all module files, and instantiates any BasePlugin subclasses."""
        sys_path_added = False
        if str(self.plugins_dir) not in sys.path:
            sys.path.insert(0, str(self.plugins_dir))
            sys_path_added = True
            
        loaded = []
        for file_path in self.plugins_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue
                
            module_name = file_path.stem
            try:
                # Import module dynamically
                module = importlib.import_module(module_name)
                
                # Scan for BasePlugin subclasses
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        inspect.isclass(attr)
                        and issubclass(attr, BasePlugin)
                        and attr is not BasePlugin
                    ):
                        # Instantiate plugin
                        plugin_instance = attr()
                        name = plugin_instance.plugin_name
                        self._loaded_plugins[name] = plugin_instance
                        loaded.append(plugin_instance)
                        
                        if self.event_bus:
                            self.event_bus.publish(
                                "plugin_loaded",
                                {"name": name, "type": plugin_instance.plugin_type}
                            )
            except Exception as e:
                # Log or handle exception gracefully
                pass
                
        return loaded

    def get_plugins_by_type(self, plugin_type: str) -> List[BasePlugin]:
        return [p for p in self._loaded_plugins.values() if p.plugin_type == plugin_type]

    def register_plugin(self, plugin: BasePlugin) -> None:
        """Allows manual registration of dynamic plugins."""
        self._loaded_plugins[plugin.plugin_name] = plugin
        if self.event_bus:
            self.event_bus.publish("plugin_loaded", {"name": plugin.plugin_name, "type": plugin.plugin_type})
