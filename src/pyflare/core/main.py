"""PyFlare application entrypoint - wires all singletons and services together."""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI

from .. import __version__
from ..api.middleware import configure_middleware
from ..api.routes import build_router
from .config import AppConfig, load_config
from ..pipeline.asset_registry import AssetRegistry
from .jarvis import JarvisCore
from ..memory.semantic_memory import SemanticMemory
from ..memory.jarvis_memory import JarvisMemory
from .jarvis_brain import JarvisBrain
from .hardware_manager import HardwareManager
from .token_banker import TokenBanker
from ..plugins.plugin_manager import PluginManager
from ..providers.provider_manager import ProviderManager
from .supervisor import Supervisor
from .templates import TemplateEngine
from .browser_agent import BrowserSupervisor
from .project_analyzer import ProjectAnalyzer
from .hardening import SessionManager, WatchdogManager
from .health_monitor import WorkerHealthMonitor
from .db import Database
from .logging_setup import get_logger, setup_logging
from ..pipeline.pipeline import Pipeline
from ..workers.analysis_worker import AnalysisWorker
from ..workers.blender_worker import BlenderWorker
from ..workers.deploy_worker import DeployWorker
from ..workers.godot_worker import GodotWorker
from ..workers.internet_worker import InternetWorker
from ..workers.validation_worker import ValidationWorker
from ..workers.code_worker import CodeWorker


class AppContext:
    """Holds all wired singletons."""

    def __init__(self, config: AppConfig):
        self.version = __version__
        self.config = config
        setup_logging(config.abs_path("log_dir"), config.get("log_level", "INFO"))
        self.log = get_logger("pyflare")

        self.db = Database(config.abs_path("database_path"))
        self.registry = AssetRegistry(self.db)
        self.memory = SemanticMemory(self.db)
        self.jarvis_memory = JarvisMemory(self.db)
        self.templates = TemplateEngine(config.templates)
        self.token_banker = TokenBanker(config.get("token_banker", {}))
        self.provider_manager = ProviderManager(config.providers, token_banker=self.token_banker)
        self.memory.provider_manager = self.provider_manager
        self.hardware = HardwareManager(config.scheduler, str(config.abs_path("output_dir")))
        self.brain = JarvisBrain(self.memory, self.provider_manager, self.token_banker, self.hardware, self.templates)
        
        from .project_manager import ProjectManager
        self.project_manager = ProjectManager(self.db, self.brain)
        
        self.browser_agent = BrowserSupervisor(self.db)
        self.project_analyzer = ProjectAnalyzer(self.db)
        
        self.session_manager = SessionManager(self.db, str(config.abs_path("output_dir")))
        self.watchdog = WatchdogManager(timeout_secs=600, memory_limit_mb=8192)
        self.watchdog.start()
        
        self.health_monitor = WorkerHealthMonitor(config)
        
        self.jarvis = JarvisCore(config.scheduler, str(config.abs_path("output_dir")))

        retries = config.retries
        worker_ctx: Dict[str, Any] = {"registry": self.registry, "db": self.db}
        wcfg = config.workers
        self.workers = {
            "internet": InternetWorker(
                wcfg.get("internet", {}), retries, worker_ctx,
                provider_manager=self.provider_manager, registry=self.registry,
                assets_dir=config.abs_path("assets_dir"), cache_dir=config.abs_path("cache_dir"),
            ),
            "analysis": AnalysisWorker(wcfg.get("analysis", {}), retries, worker_ctx),
            "blender": BlenderWorker(
                wcfg.get("blender", {}), retries, worker_ctx,
                output_dir=config.abs_path("output_dir")),
            "godot": GodotWorker(
                wcfg.get("godot", {}), retries, worker_ctx,
                output_dir=config.abs_path("output_dir")),
            "validation": ValidationWorker(wcfg.get("validation", {}), retries, worker_ctx),
            "deploy": DeployWorker(
                wcfg.get("deploy", {}), retries, worker_ctx,
                output_dir=config.abs_path("output_dir")),
            "code": CodeWorker(
                wcfg.get("code", {}), retries, worker_ctx,
                provider_manager=self.provider_manager),
        }

        from .config import PROJECT_ROOT
        plugins_cfg = config.get("plugins", {})
        plugins_dir = PROJECT_ROOT / plugins_cfg.get("directory", "plugins")
        self.plugins = PluginManager(plugins_dir, enabled=plugins_cfg.get("enabled", True))
        self.plugins.load({"db": self.db, "registry": self.registry})

        self.pipeline = Pipeline(
            self.db, self.registry, self.memory, self.templates, self.plugins,
            self.workers, config.abs_path("output_dir"),
        )
        self.supervisor = Supervisor(
            self.db, self.jarvis, self.pipeline, self.memory,
            config.scheduler, config.retries, brain=self.brain,
            jarvis_memory=self.jarvis_memory
        )

        from .event_bus import EventBus
        from .goal_manager import GoalManager
        from .task_queue import PersistentTaskQueue
        from ..memory.knowledge_graph import KnowledgeGraph
        from .benchmark_engine import BenchmarkEngine
        from .project_workspace import ProjectWorkspaceManager
        from ..scheduler.background_scheduler import BackgroundScheduler
        from .bug_hunter import AutonomousBugHunter
        from ..plugins.plugin_manager import PluginManager as DynamicPluginManager
        from .dashboard import DashboardApp

        self.event_bus = EventBus()
        self.goal_manager = GoalManager(self.db, self.event_bus)
        self.task_queue = PersistentTaskQueue(self.db, self.event_bus)
        self.knowledge_graph = KnowledgeGraph(self.db, self.event_bus)
        self.benchmark_engine = BenchmarkEngine(self.db, self.event_bus)
        self.project_workspace = ProjectWorkspaceManager(self.db, config.abs_path("output_dir") / "workspaces", self.event_bus)
        self.background_scheduler = BackgroundScheduler(self.db, self.event_bus)
        self.bug_hunter = AutonomousBugHunter(self.db, config.abs_path("output_dir"), self.event_bus)

        phase11_plugins_dir = PROJECT_ROOT / "plugins"
        self.dynamic_plugins = DynamicPluginManager(phase11_plugins_dir, self.event_bus)
        self.dynamic_plugins.discover_and_load()

        self.dashboard = DashboardApp(self)

        self.jarvis.wire(
            db=self.db,
            registry=self.registry,
            memory=self.memory,
            templates=self.templates,
            workers=self.workers,
            pipeline=self.pipeline,
            brain=self.brain,
            hardware=self.hardware,
            token_banker=self.token_banker
        )

    def start(self) -> None:
        self.log.info("PyFlare %s starting...", self.version)
        self.health_monitor.run_preflight()
        self.supervisor.start()
        self.background_scheduler.start()
        self.log.info("PyFlare %s started successfully", self.version)

    def shutdown(self) -> None:
        self.log.info("PyFlare shutting down gracefully...")
        if hasattr(self, 'watchdog') and self.watchdog:
            self.watchdog.stop()
        if hasattr(self, 'background_scheduler'):
            self.background_scheduler.stop()
        if hasattr(self, 'supervisor'):
            self.supervisor.stop()
        if hasattr(self, 'db'):
            self.db.close()
        self.log.info("PyFlare shutdown complete")


def create_app(config: AppConfig | None = None) -> FastAPI:
    if config is None:
        config = load_config()
    ctx = AppContext(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ctx.start()
        yield
        ctx.shutdown()

    app = FastAPI(
        title="PyFlare",
        version=__version__,
        description="Autonomous AI Agent Orchestration and Development Platform",
        lifespan=lifespan,
    )
    configure_middleware(app)
    app.state.ctx = ctx
    app.include_router(build_router(ctx), prefix="/api/v1")

    @app.get("/")
    def root() -> Dict[str, str]:
        return {
            "app": "PyFlare",
            "version": __version__,
            "docs": "/docs",
            "api": "/api/v1",
        }

    return app


def main() -> None:
    import uvicorn
    cfg = load_config()
    
    # Secure binding check
    host = os.environ.get("PYFLARE_HOST") or cfg.raw.get("server", {}).get("host", "127.0.0.1")
    allow_external = (
        os.environ.get("PYFLARE_ALLOW_EXTERNAL_BIND", "false").lower() in ("1", "true", "yes")
        or cfg.raw.get("server", {}).get("allow_external_bind", False)
    )
    if host not in ("127.0.0.1", "localhost") and not allow_external:
        print(f"[SECURITY WARNING] Binding to non-loopback address '{host}' requested without PYFLARE_ALLOW_EXTERNAL_BIND=true. Defaulting to 127.0.0.1 for security.")
        host = "127.0.0.1"

    port = int(os.environ.get("PYFLARE_PORT") or cfg.raw.get("server", {}).get("port", 8000))
    app = create_app(cfg)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()