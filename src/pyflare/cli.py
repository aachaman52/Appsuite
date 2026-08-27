"""PyFlare CLI entry point."""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from pyflare import __product__, __version__
from pyflare.core.config import load_config
from pyflare.core.security import redact_secrets

# Ensure Windows stdout prints standard UTF-8 safely without crashing
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def doctor_command(args: argparse.Namespace) -> int:
    """Run system diagnostic and preflight checks."""
    from pyflare.core.health import run_doctor_checks

    cfg = load_config()
    print(f"\n{__product__} v{__version__} - System Diagnostics & Doctor")
    print("=" * 55)

    checks = run_doctor_checks(cfg)
    all_ok = True
    for check in checks:
        status_tag = "[OK]" if check["ok"] else "[-]"
        print(f"{status_tag} {check['title']}: {check['message']}")
        if not check["ok"] and check.get("required", False):
            all_ok = False

    print("\nOptional Tool Integrations:")
    for tool in ["blender", "godot", "ffmpeg", "git"]:
        bin_path = cfg.get("workers", {}).get(tool, {}).get("binary", tool)
        import shutil
        found = shutil.which(bin_path)
        tag = "[OK]" if found else "[-]"
        msg = f"Available at {found}" if found else "Not found in PATH (gracefully mocked/disabled)"
        print(f"  {tag:<4} {tool:<10}: {msg}")

    print("\nConfigured LLM Provider Keys (presence only):")
    for key_name in ["OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "NVIDIA_API_KEY", "MESHY_API_KEY"]:
        is_set = bool(os.environ.get(key_name))
        tag = "[CONFIGURED]" if is_set else "[NOT SET - local fallback used]"
        print(f"  {key_name:<20}: {tag}")

    print("\nSecurity Configuration:")
    api_key_set = bool(os.environ.get("PYFLARE_API_KEY") or os.environ.get("APPSUITE_API_KEY"))
    auth_required = os.environ.get("PYFLARE_REQUIRE_AUTH", "true").lower() in ("true", "1", "yes")
    external_allowed = cfg.raw.get("server", {}).get("allow_external_bind", False)
    print(f"  PYFLARE_API_KEY     : {'[CONFIGURED]' if api_key_set else '[NOT CONFIGURED]'}")
    print(f"  Authentication Req  : {'[ENABLED BY DEFAULT]' if auth_required else '[DISABLED]'}")
    print(f"  External Binding    : {'[ENABLED]' if external_allowed else '[RESTRICTED TO LOCALHOST]'}")
    print(f"  FTP Deployments     : {'[ENABLED]' if os.environ.get('PYFLARE_FTP_ENABLED', 'false').lower() == 'true' else '[DISABLED (safe default)]'}")

    print("\n" + "=" * 55)
    print("Doctor check complete: System is ready to run PyFlare.\n")
    return 0 if all_ok else 1


def serve_command(args: argparse.Namespace) -> int:
    """Launch the PyFlare hardened FastAPI server."""
    from pyflare.core.main import create_app
    import uvicorn

    cfg = load_config()
    server_cfg = cfg.raw.get("server", {})
    host = args.host or server_cfg.get("host", "127.0.0.1")
    port = args.port or server_cfg.get("port", 8000)
    allow_external = args.allow_external or server_cfg.get("allow_external_bind", False)

    if host not in ("127.0.0.1", "localhost") and not allow_external:
        print(f"Error: Binding to external interface '{host}' is disallowed by default.")
        print("To allow external binding, provide --allow-external or set server.allow_external_bind=true in config.")
        return 1

    app = create_app(cfg)
    log_lvl = cfg.raw.get("log_level", "info").lower()
    print(f"\nStarting {__product__} v{__version__} API Server on http://{host}:{port}")
    print("Press Ctrl+C to stop.\n")
    uvicorn.run(app, host=host, port=port, log_level=log_lvl)
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
    from pyflare.core.jarvis_brain import JarvisBrain

    cfg = load_config()
    db = Database(cfg.abs_path("database_path"))
    templates = TemplateEngine(cfg.templates)
    token_banker = TokenBanker(cfg.get("token_banker", {}))
    provider_mgr = ProviderManager(cfg.providers, token_banker=token_banker)
    memory = SemanticMemory(db, provider_mgr)
    hardware = HardwareManager(cfg.scheduler, str(cfg.abs_path("output_dir")))

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


def route_command(args: argparse.Namespace) -> int:
    """Plan a deterministic execution route for a task."""
    from pyflare.router import DeterministicRouter, TaskSpec, TaskType, PrivacyLevel

    # Determine TaskType from arguments or prompt heuristics
    task_type_val = TaskType.GENERAL
    if args.task_type:
        try:
            task_type_val = TaskType(args.task_type)
        except ValueError:
            task_type_val = TaskType.GENERAL
    else:
        prompt_lower = args.prompt.lower()
        if any(k in prompt_lower for k in ["3d", "mesh", "tower", "castle", "model", "blender", "fbx", "glb"]):
            task_type_val = TaskType.THREE_D_GENERATION
        elif any(k in prompt_lower for k in ["code", "script", "gdscript", "python", "function", "class"]):
            task_type_val = TaskType.CODE_GENERATION
        elif any(k in prompt_lower for k in ["godot", "scene", "tscn", "game"]):
            task_type_val = TaskType.GODOT_AUTOMATION

    privacy = PrivacyLevel.CONFIDENTIAL if args.local_only or args.privacy == "confidential" else (
        PrivacyLevel.INTERNAL if args.privacy == "internal" else PrivacyLevel.PUBLIC
    )

    spec = TaskSpec(
        prompt=args.prompt,
        task_type=task_type_val,
        allow_cloud=not args.no_cloud and not args.local_only,
        require_local=bool(args.local_only),
        privacy_level=privacy,
        max_cost_usd=args.max_cost,
    )

    router = DeterministicRouter()
    decision = router.plan_route(spec)

    print(f"\n{__product__} Deterministic Routing Plan")
    print("=" * 60)
    print(f"Task ID           : {spec.task_id}")
    print(f"Prompt            : '{redact_secrets(spec.prompt)}'")
    print(f"Task Type         : {spec.task_type.value}")
    print(f"Privacy Level     : {spec.privacy_level.value}")
    print(f"Allow Cloud       : {spec.allow_cloud}")
    print(f"Require Local     : {spec.require_local}")

    print("\nRouting Decision:")
    if decision.selected_candidate:
        cand = decision.selected_candidate
        print(f"  [SELECTED] {cand.display_name} (ID: {cand.candidate_id})")
        print(f"  Provider Type   : {cand.provider_type}")
        print(f"  Execution Mode  : {'Local' if cand.is_local else 'Cloud'}")
        print(f"  Deterministic Score : {decision.score:.4f}")
        print(f"  Estimated Cost  : ${decision.estimated_cost_usd:.4f}")
        print(f"  Expected Latency: ~{decision.estimated_latency_seconds:.1f}s")
        print("  Selection Rationale:")
        for r in decision.selection_reasons:
            print(f"    - {r}")
    else:
        print("  [-] NO ELIGIBLE CANDIDATE FOUND")
        for r in decision.selection_reasons:
            print(f"    - {r}")

    if decision.fallback_candidates:
        print("\nOrdered Fallback Candidates:")
        for idx, fb in enumerate(decision.fallback_candidates, start=1):
            fb_score = decision.candidate_scores.get(fb.candidate_id, 0.0)
            print(f"  {idx}. {fb.display_name:<35} [Score: {fb_score:.4f}, Cost: ${fb.estimated_cost_usd:.4f}, Latency: ~{fb.expected_latency_seconds:.1f}s]")

    if decision.rejected_candidates:
        print("\nRejected Candidates:")
        for cid, reason in decision.rejected_candidates.items():
            print(f"  [-] {cid:<22}: {reason}")

    print("=" * 60 + "\n")
    return 0 if decision.selected_candidate else 1


def capabilities_command(args: argparse.Namespace) -> int:
    """List all registered capability candidates and availability."""
    from pyflare.router import CapabilityRegistry

    reg = CapabilityRegistry()
    candidates = reg.list_candidates()

    print(f"\n{__product__} Registered Capability Registry ({len(candidates)} candidates)")
    print("=" * 70)
    for c in candidates:
        status_tag = "[AVAILABLE]" if c.is_available else "[- UNAVAILABLE]"
        print(f"{status_tag:<16} {c.display_name} ({c.candidate_id})")
        print(f"  Type: {c.provider_type:<18} Local: {str(c.is_local):<6} Privacy: {c.privacy_level.value}")
        print(f"  Cost: ${c.estimated_cost_usd:.4f}/task    Latency: ~{c.expected_latency_seconds:.1f}s  Quality: {c.quality_score:.2f}")
        supported_tasks = ", ".join(t.value for t in c.supported_task_types)
        print(f"  Supported Tasks: {supported_tasks}")
        if not c.is_available and c.unavailability_reason:
            print(f"  Reason: {c.unavailability_reason}")
        print("-" * 70)
    print()
    return 0


def hardware_command(args: argparse.Namespace) -> int:
    """Inspect and display detected hardware capabilities and tier."""
    from pyflare.core.hardware_manager import HardwareManager

    hw = HardwareManager({})
    profile = hw.get_hardware_profile()

    print(f"\n{__product__} Host Hardware Profile & Telemetry")
    print("=" * 55)
    print(f"Hardware Tier     : {profile.hardware_tier.value.upper()}")
    print(f"Operating System  : {profile.os_name}")
    print(f"CPU Cores         : {profile.cpu_cores_logical} logical ({profile.cpu_cores_physical} physical)")
    print(f"RAM Total         : {profile.ram_total_mb:.1f} MB (Available: {profile.ram_available_mb:.1f} MB)")
    if profile.gpu_name:
        print(f"GPU Device        : {profile.gpu_name}")
        print(f"VRAM Total        : {profile.vram_total_mb:.1f} MB (Free: {profile.vram_available_mb:.1f} MB)")
    else:
        print("GPU Device        : No discrete NVIDIA GPU detected (Integrated/CPU fallback)")
    print(f"Disk Available    : {profile.disk_available_gb:.1f} GB")

    print("\nInstalled Binary Tools:")
    for b_name, b_inst in profile.installed_binaries.items():
        tag = "[INSTALLED]" if b_inst else "[- NOT FOUND]"
        print(f"  {tag:<14} {b_name}")

    print("\nResource Pressure:")
    for p_name, p_val in profile.resource_pressure.items():
        print(f"  {p_name:<16}: {p_val:.1f}%")

    print("=" * 55 + "\n")
    return 0


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

    # 5. route
    route_p = subparsers.add_parser("route", help="Plan a deterministic execution route for a task")
    route_p.add_argument("prompt", help="Task prompt or requirement")
    route_p.add_argument("--task-type", help="Explicit TaskType (e.g. 3d_generation, code_generation, validation)")
    route_p.add_argument("--local-only", action="store_true", help="Force local-only execution")
    route_p.add_argument("--no-cloud", action="store_true", help="Disallow cloud providers")
    route_p.add_argument("--privacy", choices=["public", "internal", "confidential"], default="internal", help="Privacy constraint")
    route_p.add_argument("--max-cost", type=float, help="Maximum allowed cost in USD")

    # 6. capabilities
    subparsers.add_parser("capabilities", help="List all registered candidate capabilities")

    # 7. hardware
    subparsers.add_parser("hardware", help="Inspect host hardware profile and detection telemetry")

    # 8. validate-os
    subparsers.add_parser("validate-os", help="Run lightweight PyFlare OS source validation without building ISO")

    return parser


def validate_os_command(args: argparse.Namespace) -> int:
    """Run static syntax, branding, and manifest validation for PyFlare OS source tree."""
    from pyflare.core.config import find_project_root
    root = find_project_root()
    val_script = root / "archive" / "pyflareos" / "validation" / "run_all.py"
    if not val_script.exists():
        print(f"PyFlare OS source tree not found at {val_script}")
        return 1

    import subprocess
    print("\nRunning PyFlare OS Static Source Validation...")
    res = subprocess.run([sys.executable, str(val_script)], cwd=str(val_script.parent.parent))
    return res.returncode


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
    elif args.command == "route":
        return route_command(args)
    elif args.command == "capabilities":
        return capabilities_command(args)
    elif args.command == "hardware":
        return hardware_command(args)
    elif args.command == "validate-os":
        return validate_os_command(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
