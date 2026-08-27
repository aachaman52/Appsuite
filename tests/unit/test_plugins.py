from __future__ import annotations
from pathlib import Path
from appsuite.plugins.plugin_manager import PluginManager, BasePlugin

def test_plugin_manager_lifecycle(tmp_path):
    pm = PluginManager(tmp_path)
    
    # Create a dynamic plugin file on the fly
    plugin_src = """from appsuite.plugins.plugin_manager import BasePlugin

class DynamicCustomPlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "custom_test_plugin"
    @property
    def plugin_type(self) -> str:
        return "validator"
"""
    plugin_file = tmp_path / "custom_test_plugin.py"
    with open(plugin_file, "w") as f:
        f.write(plugin_src)
        
    # Discover and load
    loaded = pm.discover_and_load()
    assert len(loaded) == 1
    assert loaded[0].plugin_name == "custom_test_plugin"
    assert loaded[0].plugin_type == "validator"
    
    # Get by type
    validators = pm.get_plugins_by_type("validator")
    assert len(validators) == 1
    assert validators[0].plugin_name == "custom_test_plugin"
