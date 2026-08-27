from __future__ import annotations
from .plugin_manager import BasePlugin

class TestWorkerPlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "test_worker_plugin"
        
    @property
    def plugin_type(self) -> str:
        return "worker"

def register(context):
    return {
        "name": "test_worker_plugin",
        "type": "worker",
        "workers": {"test_worker": TestWorkerPlugin()}
    }
