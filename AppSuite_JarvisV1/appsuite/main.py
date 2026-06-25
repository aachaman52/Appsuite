"""AppSuite application entrypoint - wires every component together."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.routes import build_router
from .config import AppConfig, load_config
from .core.asset_registry import AssetRegistry
from .core.jarvis import JarvisCore
from .core.semantic_memory import SemanticMemory
from .core.jarvis_brain import JarvisBrain
from .core.hardware_manager import HardwareManager
from .core.token_banker import TokenBanker
from .core.plugin_manager import PluginManager
from .core.provider_manager import ProviderManager
from .core.supervisor import Supervisor
from .core.templates import TemplateEngine
from .db import Database
from .logging_setup import get_logger, setup_logging
from .pipeline.pipeline import Pipeline
from .workers.analysis_worker import AnalysisWorker
from .workers.blender_worker import BlenderWorker
from .workers.deploy_worker import DeployWorker
from .workers.godot_worker import GodotWorker
from .workers.internet_worker import InternetWorker
from .workers.validation_worker import ValidationWorker


class AppContext:
    """Holds all wired singletons."""

    def __init__(self, config: AppConfig):
        self.version = __version__
        self.config = config
        setup_logging(config.abs_path("log_dir"), config.get("log_level", "INFO"))
        self.log = get_logger("appsuite")

        self.db = Database(config.abs_path("database_path"))
        self.registry = AssetRegistry(self.db)
        self.memory = SemanticMemory(self.db)
        self.templates = TemplateEngine(config.templates)
        self.token_banker = TokenBanker(config.get("token_banker", {}))
        self.provider_manager = ProviderManager(config.providers, token_banker=self.token_banker)
        self.hardware = HardwareManager(config.scheduler, str(config.abs_path("output_dir")))
        self.brain = JarvisBrain(self.memory, self.provider_manager, self.token_banker, self.hardware, self.templates)
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
            config.scheduler, config.retries, brain=self.brain
        )

        # Wire Jarvis to all components so jarvis.run() can orchestrate them
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
        self.supervisor.start()
        self.log.info("AppSuite %s started", self.version)

    def shutdown(self) -> None:
        self.supervisor.stop()
        self.db.close()


def create_app() -> FastAPI:
    config = load_config()
    ctx = AppContext(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ctx.start()
        yield
        ctx.shutdown()

    app = FastAPI(title="AppSuite", version=__version__,
                  description="AI-powered asset generation and game content pipeline",
                  lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )
    app.state.ctx = ctx
    app.include_router(build_router(ctx), prefix="/api/v1")

    @app.get("/")
    def root() -> Dict[str, str]:
        return {"app": "AppSuite", "version": __version__, "docs": "/docs",
                "api": "/api/v1"}

    return app


app = create_app()


def main() -> None:
    import uvicorn
    cfg = load_config()
    uvicorn.run(app, host=cfg.get("host", "0.0.0.0"), port=cfg.get("port", 8000))


if __name__ == "__main__":
    main()