"""PyFlare Command Line Interface.

Provides:
- pyflare serve
- pyflare run "<prompt>"
- pyflare plan "<prompt>"
- pyflare doctor
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

# Ensure standard output can handle utf-8 / localized filepaths without charmap errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pyflare import __version__, __product__
from pyflare.core.config import get_config, load_config


def doctor_command(args: argparse.Namespace) -> int:
    """Run diagnostics on environment, dependencies, optional tools, and configs."""
    print(f"\n{__product__} v{__version__} - System Diagnostics & Doctor\n" + "=" * 55)
    
    # 1. Python Environment
    print(f"[OK] Python version: {sys.version.split()[0]} ({sys.executable})")
    
    # 2. Config & Workspace
    cfg = load_config()
    print(f"[OK] Config loaded successfully ({len(cfg.raw)} top-level sections)")
    print(f"[OK] Providers configured: {len(cfg.providers)}")
    print(f"[OK] Templates available: {len(cfg.templates)}")
    
    ws_dir = os.environ.get("PYFLARE_WORKSPACE_DIR") or str(Path.cwd() / "workspace")
    Path(ws_dir).mkdir(parents=True, exist_ok=True)
    print(f"[OK] Workspace directory: {ws_dir} (writeable: {os.access(ws_dir, os.W_OK)})")

    # 3. Optional Tool Binaries
    print("\nOptional Tool Integrations:")
    for tool in ["blender", "godot", "ffmpeg", "git"]:
        path = shutil.which(tool)
        if path:
            print(f"  [OK] {tool:<10}: Available at {path}")
        else:
            print(f"  [-]  {tool:<10}: Not found in PATH (gracefully mocked/disabled)")

    # 4. LLM API Keys
    print("\nConfigured LLM Provider Keys (presence only):")
    for key_env in ["OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "NVIDIA_API_KEY"]:
        has_key = bool(os.environ.get(key_env))
        status = "[SET]" if has_key else "[NOT SET - local fallback used]"
        print(f"  {key_env:<20}: {status}")

    # 5. Security & Auth Settings
    print("\nSecurity Configuration:")
    api_key_set = bool(os.environ.get("PYFLARE_API_KEY"))
    print(f"  PYFLARE_API_KEY     : {'[CONFIGURED]' if api_key_set else '[NOT CONFIGURED - dev mode]'}")
    ext_bind = os.environ.get("PYFLARE_ALLOW_EXTERNAL_BIND", "false").lower() in ("1", "true", "yes")
    print(f"  External Binding    : {'[ALLOWED]' if ext_bind else '[RESTRICTED TO LOCALHOST]'}")
    ftp_enabled = os.environ.get("PYFLARE_FTP_ENABLED", "false").lower() in ("1", "true", "yes")
    print(f"  FTP Deployments     : {'[ENABLED]' if ftp_enabled else '[DISABLED (safe default)]'}")

    print("\n" + "=" * 55)
    print("Doctor check complete: System is ready to run PyFlare.\n")
    return 0


def serve_command(args: argparse.Namespace) -> int:
    """Start the PyFlare FastAPI server with uvicorn."""
    import uvicorn
    from pyflare.core.main import create_app

    cfg = load_config()
    host = args.host or os.environ.get("PYFLARE_HOST") or cfg.raw.get("server", {}).get("host", "127.0.0.1")
    port = args.port or int(os.environ.get("PYFLARE_PORT") or cfg.raw.get("server", {}).get("port", 8000))
    allow_external = args.allow_external or (
        os.environ.get("PYFLARE_ALLOW_EXTERNAL_BIND", "false").lower() in ("1", "true", "yes")
    )

    if host not in ("127.0.0.1", "localhost") and not allow_external:
        print(
            f"[SECURITY ERROR] Binding to non-loopback address '{host}' blocked.\n"
            "Pass --allow-external or set PYFLARE_ALLOW_EXTERNAL_BIND=true to allow external connections.",
            file=sys.stderr,
        )
        return 1

    print(f"Starting {__product__} v{__version__} server on http://{host}:{port}")
    app = create_app(cfg)
    uvicorn.run(app, host=host, port=port)
    return 0


def plan_command(args: argparse.Namespace) -> int:
    """Preview execution plan for a prompt without running pipeline."""
    from pyflare.core.jarvis import JarvisCore
    from pyflare.core.templates import TemplateEngine
    from pyflare.core.db import Database
    from pyflare.memory.semantic_memory import SemanticMemory
    from pyflare.providers.provider_manager import ProviderManager
    from pyflare.core.hardware_manager import HardwareManager
    from pyflare.core.token_banker import TokenBanker

    cfg = load_config()
    db = Database(cfg.abs_path("database_path"))
    templates = TemplateEngine(cfg.templates)
    token_banker = TokenBanker(cfg.get("token_banker", {}))
    provider_mgr = ProviderManager(cfg.providers, token_banker=token_banker)
    memory = SemanticMemory(db, provider_mgr)
    hardware = HardwareManager(cfg.scheduler, str(cfg.abs_path("output_dir")))

    from pyflare.core.jarvis_brain import JarvisBrain

    brain = JarvisBrain(memory, provider_mgr, token_banker, hardware, templates)
    jarvis = JarvisCore(cfg.scheduler, str(cfg.abs_path("output_dir")))
    jarvis.wire(
        db=db,
        registry=None,
        memory=memory,
        templates=templates,
        workers={},
        pipeline=None,
        brain=brain,
        hardware=hardware,
        token_banker=token_banker,
    )

    print(f"\nPlanning execution for prompt: '{args.prompt}'")
    plan = jarvis._plan(args.prompt, template_id=args.template)
    print(f"Template ID       : {plan.template_id}")
    print(f"Scene Plan        : {plan.scene_plan}")
    print(f"Workers to Run    : {', '.join(plan.workers_to_run)}")
    print(f"Use Cached Assets : {plan.use_cached_assets}")
    print(f"Reasons           : {plan.reasons}\n")
    return 0


def run_command(args: argparse.Namespace) -> int:
    """Execute a prompt through the PyFlare autonomous engine."""
    from pyflare.core.main import AppContext

    cfg = load_config()
    ctx = AppContext(cfg)
    ctx.start()
    try:
        print(f"\nExecuting {__product__} run for prompt: '{args.prompt}'")
        res = ctx.jarvis.run(prompt=args.prompt, template_id=args.template)
        status_val = getattr(res.status, "value", str(res.status))
        print(f"Status  : {status_val}")
        print(f"Job ID  : {res.job_id}")
        errors = getattr(res, "errors", [])
        if errors:
            print(f"Errors  : {errors}")
        return 0 if status_val == "success" else 1
    finally:
        ctx.shutdown()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyflare",
        description=f"{__product__} CLI - Autonomous AI Agent Orchestration and Development Platform",
    )
    parser.add_argument("--version", "-v", action="version", version=f"{__product__} {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # 1. doctor
    subparsers.add_parser("doctor", help="Inspect system environment, tools, and configuration")

    # 2. serve
    serve_p = subparsers.add_parser("serve", help="Start the PyFlare API server")
    serve_p.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    serve_p.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    serve_p.add_argument("--allow-external", action="store_true", help="Explicitly allow binding to non-localhost")

    # 3. plan
    plan_p = subparsers.add_parser("plan", help="Generate an execution plan for a prompt without executing")
    plan_p.add_argument("prompt", help="Natural language prompt describing what to build")
    plan_p.add_argument("--template", help="Optional template identifier")

    # 4. run
    run_p = subparsers.add_parser("run", help="Run a prompt through the PyFlare engine")
    run_p.add_argument("prompt", help="Natural language prompt describing what to build")
    run_p.add_argument("--template", help="Optional template identifier")

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "doctor":
        return doctor_command(args)
    elif args.command == "serve":
        return serve_command(args)
    elif args.command == "plan":
        return plan_command(args)
    elif args.command == "run":
        return run_command(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
