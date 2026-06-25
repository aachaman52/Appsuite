"""Jarvis CLI for AppSuite.

Usage:
    python run_jarvis.py "Create a medieval village"
    python run_jarvis.py "A sci-fi space station with corridors" --template sci_fi
    python run_jarvis.py "Forest scene" --job-id my-custom-id
    python run_jarvis.py --status
    python run_jarvis.py --history 10
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

# Ensure the project root is on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Support UTF-8 output streams on Windows to prevent UnicodeEncodeError with Thai paths
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from appsuite.config import PROJECT_ROOT, load_config
from appsuite.core.asset_registry import AssetRegistry
from appsuite.core.jarvis import JarvisCore
from appsuite.core.semantic_memory import SemanticMemory
from appsuite.core.token_banker import TokenBanker
from appsuite.core.hardware_manager import HardwareManager
from appsuite.core.jarvis_brain import JarvisBrain
from appsuite.core.supervisor import Supervisor
from appsuite.core.plugin_manager import PluginManager
from appsuite.core.provider_manager import ProviderManager
from appsuite.core.templates import TemplateEngine
from appsuite.db import Database
from appsuite.logging_setup import setup_logging
from appsuite.pipeline.pipeline import Pipeline
from appsuite.workers.analysis_worker import AnalysisWorker
from appsuite.workers.blender_worker import BlenderWorker
from appsuite.workers.deploy_worker import DeployWorker
from appsuite.workers.godot_worker import GodotWorker
from appsuite.workers.internet_worker import InternetWorker
from appsuite.workers.validation_worker import ValidationWorker


def _bootstrap():
    """Build the same component graph as AppContext, without FastAPI."""
    cfg = load_config()
    setup_logging(cfg.abs_path("log_dir"), cfg.get("log_level", "INFO"))

    db = Database(cfg.abs_path("database_path"))
    registry = AssetRegistry(db)
    memory = SemanticMemory(db)
    templates = TemplateEngine(cfg.templates)
    token_banker = TokenBanker(cfg.get("token_banker", {}))
    providers = ProviderManager(cfg.providers, token_banker=token_banker)
    hardware = HardwareManager(cfg.scheduler, str(cfg.abs_path("output_dir")))
    brain = JarvisBrain(memory, providers, token_banker, hardware, templates)
    
    jarvis = JarvisCore(cfg.scheduler, str(cfg.abs_path("output_dir")))

    retries = cfg.retries
    worker_ctx = {"registry": registry, "db": db}
    wcfg = cfg.workers
    workers = {
        "internet": InternetWorker(
            wcfg.get("internet", {}),
            retries,
            worker_ctx,
            provider_manager=providers,
            registry=registry,
            assets_dir=cfg.abs_path("assets_dir"),
            cache_dir=cfg.abs_path("cache_dir"),
        ),
        "analysis": AnalysisWorker(wcfg.get("analysis", {}), retries, worker_ctx),
        "blender": BlenderWorker(
            wcfg.get("blender", {}),
            retries,
            worker_ctx,
            output_dir=cfg.abs_path("output_dir"),
        ),
        "godot": GodotWorker(
            wcfg.get("godot", {}),
            retries,
            worker_ctx,
            output_dir=cfg.abs_path("output_dir"),
        ),
        "validation": ValidationWorker(wcfg.get("validation", {}), retries, worker_ctx),
        "deploy": DeployWorker(
            wcfg.get("deploy", {}),
            retries,
            worker_ctx,
            output_dir=cfg.abs_path("output_dir"),
        ),
    }

    plugins_cfg = cfg.get("plugins", {})
    plugins_dir = PROJECT_ROOT / plugins_cfg.get("directory", "plugins")
    plugins = PluginManager(plugins_dir, enabled=plugins_cfg.get("enabled", True))
    plugins.load({"db": db, "registry": registry})

    pipeline = Pipeline(
        db=db,
        registry=registry,
        memory=memory,
        templates=templates,
        plugins=plugins,
        workers=workers,
        output_dir=cfg.abs_path("output_dir"),
    )
    
    supervisor = Supervisor(
        db=db,
        jarvis=jarvis,
        pipeline=pipeline,
        memory=memory,
        scheduler_cfg=cfg.scheduler,
        retries_cfg=cfg.retries,
        brain=brain
    )
    pipeline.supervisor = supervisor

    jarvis.wire(
        db=db,
        registry=registry,
        memory=memory,
        templates=templates,
        workers=workers,
        pipeline=pipeline,
        brain=brain,
        hardware=hardware,
        token_banker=token_banker
    )

    return jarvis, db, memory, cfg


def _print_result(result) -> None:
    width = 64
    line = "-" * width

    print(f"\n{'=' * width}")
    print("  Jarvis Result")
    print(f"{'=' * width}")
    print(f"  Job ID  : {result.job_id}")
    print(f"  Status  : {result.status.upper()}")
    print(f"  Duration: {result.duration_seconds:.1f}s")
    print(line)

    print("  PLAN:")
    print(f"    Template : {result.plan.template_id}")
    print(f"    Cached   : {result.plan.use_cached_assets}")
    print(f"    Workers  : {', '.join(result.plan.workers_to_run)}")
    scene_plan = result.plan.scene_plan or {}
    needed_assets = scene_plan.get("needed_assets", [])
    if needed_assets:
        print("    Assets   :")
        for asset in needed_assets:
            terms = ", ".join(asset.get("search_terms", []))
            print(f"      - {asset.get('role')} x{asset.get('count')} ({terms})")
    for reason in result.plan.reasons:
        print(f"    * {reason}")
    print(line)

    if result.godot_project:
        print(f"  Godot Project : {result.godot_project}")
    if result.main_scene:
        print(f"  Main Scene    : {result.main_scene}")
    if result.asset_count:
        print(f"  Assets        : {result.asset_count}")
    if result.deployment_url:
        print(f"  Live URL      : {result.deployment_url}")

    if result.stages:
        print(line)
        print("  STAGES:")
        for stage, info in result.stages.items():
            ok_str = "[OK]" if isinstance(info, dict) and info.get("ok", True) else "[XX]"
            print(f"    {ok_str} {stage}")

    if result.warnings:
        print(line)
        print("  WARNINGS:")
        for warning in result.warnings:
            print(f"    [!!] {warning}")

    if result.errors:
        print(line)
        print("  ERRORS:")
        for error in result.errors:
            print(f"    [XX] {error}")

    res_end = result.resources_at_end
    if res_end.get("cpu_percent") is not None:
        print(line)
        print("  RESOURCES (at end):")
        print(f"    CPU  : {res_end['cpu_percent']}%")
        print(f"    RAM  : {res_end['ram_percent']}%")
        disk = res_end.get("disk", {})
        if disk:
            print(f"    Disk : {disk['free_gb']}GB free")
        gpu = res_end.get("gpu", {})
        if gpu.get("available"):
            print(
                f"    GPU  : {gpu['utilization_percent']}% util "
                f"{gpu['memory_used_mb']:.0f}/{gpu['memory_total_mb']:.0f}MB"
            )

    print(f"{'=' * width}\n")


def _print_status(jarvis) -> None:
    snap = jarvis.status()
    print("\n=== Jarvis Status ===")
    print(f"  Uptime : {snap['uptime_seconds']}s")
    print(f"  Wired  : {snap['wired']}")
    print(f"  Workers: {', '.join(snap.get('workers_wired', []))}")
    ok_str = "[OK]" if snap["scheduling_allowed"] else "[--]"
    print(f"  Sched  : {ok_str} {snap['scheduling_reason']}")
    res = snap["resources"]
    if res.get("cpu_percent") is not None:
        print(f"  CPU    : {res['cpu_percent']}%")
        print(f"  RAM    : {res['ram_percent']}%")
    disk = res.get("disk", {})
    if disk:
        print(f"  Disk   : {disk['free_gb']}GB free / {disk['total_gb']}GB total")
    gpu = res.get("gpu", {})
    if gpu.get("available"):
        print(
            f"  GPU    : {gpu['utilization_percent']}% util "
            f"{gpu['memory_used_mb']:.0f}/{gpu['memory_total_mb']:.0f}MB"
        )
    print()


def _print_plan(plan) -> None:
    scene_plan = plan.scene_plan or {}
    print("\n=== Jarvis Plan ===")
    print(f"  Prompt   : {plan.prompt}")
    print(f"  Template : {plan.template_id}")
    print(f"  Cached   : {plan.use_cached_assets}")
    if plan.cached_job_id:
        print(f"  Cache Job: {plan.cached_job_id}")
    print(f"  Workers  : {', '.join(plan.workers_to_run)}")

    needed_assets = scene_plan.get("needed_assets", [])
    if needed_assets:
        print("\n  Needed Assets:")
        for asset in needed_assets:
            terms = ", ".join(asset.get("search_terms", []))
            print(f"    - {asset.get('role')} x{asset.get('count')} ({terms})")

    strategy = scene_plan.get("strategy", {})
    if strategy:
        print("\n  Strategy:")
        for key, value in strategy.items():
            print(f"    - {key}: {value}")

    if plan.reasons:
        print("\n  Reasons:")
        for reason in plan.reasons:
            print(f"    - {reason}")
    print()


def _print_history(memory, limit: int) -> None:
    records = memory.recall(limit)
    print(f"\n=== Jarvis Memory (last {len(records)} runs) ===")
    for index, record in enumerate(records, 1):
        outcome_icon = "[OK]" if record.get("outcome") == "success" else "[XX]"
        print(f"  {index:>3}. {outcome_icon} {record.get('prompt', '')[:60]}")
        print(
            f"       job={record.get('job_id', '')[:8]}  "
            f"template={record.get('template_id', '?')}  "
            f"outcome={record.get('outcome', '?')}"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_jarvis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
            Jarvis CLI - AI-powered Godot scene generator
            =============================================
            Examples:
              python run_jarvis.py "Create a medieval village"
              python run_jarvis.py "Sci-fi corridor" --template sci_fi
              python run_jarvis.py "Create a medieval village" --plan
              python run_jarvis.py --status
              python run_jarvis.py --history 10
            """
        ),
    )
    parser.add_argument("prompt", nargs="?", default=None, help="Scene description prompt")
    parser.add_argument("--template", "-t", default=None, help="Force a specific template ID")
    parser.add_argument("--job-id", default=None, help="Explicit job ID")
    parser.add_argument("--status", action="store_true", help="Show Jarvis status and exit")
    parser.add_argument("--history", type=int, default=0, metavar="N", help="Show memory")
    parser.add_argument("--plan", action="store_true", help="Preview Jarvis plan and exit")
    parser.add_argument("--json", action="store_true", help="Output result as raw JSON")
    args = parser.parse_args()

    jarvis, _db, memory, _cfg = _bootstrap()

    if args.status:
        _print_status(jarvis)
        return
    if args.history:
        _print_history(memory, args.history)
        return
    if not args.prompt:
        parser.print_help()
        sys.exit(1)

    if args.plan:
        plan = jarvis._plan(args.prompt, args.template)
        if args.json:
            print(json.dumps({
                "prompt": plan.prompt,
                "template_id": plan.template_id,
                "scene_plan": plan.scene_plan,
                "use_cached_assets": plan.use_cached_assets,
                "cached_job_id": plan.cached_job_id,
                "workers_to_run": plan.workers_to_run,
                "reasons": plan.reasons,
            }, indent=2))
        else:
            _print_plan(plan)
        return

    print("\nJarvis starting...")
    print(f"  Prompt: {args.prompt}")
    if args.template:
        print(f"  Template override: {args.template}")
    print(f"Creating job {args.job_id}...")
    print("[JARVIS] Planning...")

    result = jarvis.run(prompt=args.prompt, template_id=args.template, job_id=args.job_id)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        _print_result(result)

    sys.exit(0 if result.status == "success" else 1)


if __name__ == "__main__":
    main()
