"""Jarvis CLI for AppSuite and Aachman Ecosystem Bridge.

Usage:
    python run_jarvis.py "Create a medieval village"
    python run_jarvis.py "open daymentor"
    python run_jarvis.py "add physics revision tomorrow" --confirm
    python run_jarvis.py "new t20 match india vs australia 20 overs"
    python run_jarvis.py --ecosystem-status
    python run_jarvis.py --ecosystem-login --email user@example.com --password secret
    python run_jarvis.py --ecosystem-logout
"""
from __future__ import annotations

import argparse
import getpass
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
from appsuite.workers.code_worker import CodeWorker

from appsuite.ecosystem import (
    interpret_ecosystem_query,
    EcosystemExecutor,
    get_ecosystem_client,
    interpret_ecosystem_read_query,
    EcosystemReadExecutor,
    EcosystemPlanner,
    GoalPlanner,
    JarvisEcosystemIntent,
)


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
        "code": CodeWorker(
            wcfg.get("code", {}),
            retries,
            worker_ctx,
            output_dir=cfg.abs_path("output_dir"),
        ),
    }

    pipeline = Pipeline(
        workers=workers,
        db=db,
        output_dir=str(cfg.abs_path("output_dir")),
    )

    jarvis.wire(
        db=db,
        registry=registry,
        memory=memory,
        templates=templates,
        workers=workers,
        pipeline=pipeline,
        brain=brain,
        hardware=hardware,
    )

    return jarvis, db, memory, cfg


def _print_ecosystem_status() -> None:
    client = get_ecosystem_client()
    print("\n=== Aachman Ecosystem Status ===")
    print(f"  Authenticated : {'YES' if client.is_authenticated else 'NO'}")
    if client.is_authenticated:
        print(f"  User Email    : {client.user_email}")
        print(f"  User ID (UUID): {client.user_id}")
        print(f"  Session File  : {client.session_file}")
    else:
        print("  Notice        : Not signed in. Run with --ecosystem-login to sign in with Aachman Account.")
    print("================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_jarvis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
            Jarvis CLI - AI-powered Scene Generator & Aachman Ecosystem Bridge
            ==================================================================
            Examples:
              python run_jarvis.py "Create a medieval village"
              python run_jarvis.py "open daymentor"
              python run_jarvis.py "add physics revision tomorrow" --confirm
              python run_jarvis.py "new t20 match india vs australia 20 overs"
              python run_jarvis.py --ecosystem-status
              python run_jarvis.py --ecosystem-login --email <email>
              python run_jarvis.py --ecosystem-logout
            """
        ),
    )
    parser.add_argument("prompt", nargs="?", default=None, help="Scene description or ecosystem action prompt")
    parser.add_argument("--template", "-t", default=None, help="Force a specific template ID")
    parser.add_argument("--job-id", default=None, help="Explicit job ID")
    parser.add_argument("--status", action="store_true", help="Show Jarvis status and exit")
    parser.add_argument("--history", type=int, default=0, metavar="N", help="Show memory")
    parser.add_argument("--plan", action="store_true", help="Preview Jarvis plan and exit")
    parser.add_argument("--json", action="store_true", help="Output result as raw JSON")
    parser.add_argument("--confirm", action="store_true", help="Confirm execution of ecosystem write actions")
    
    # Ecosystem Auth Flags
    parser.add_argument("--ecosystem-status", action="store_true", help="Show Aachman Ecosystem login status")
    parser.add_argument("--ecosystem-login", action="store_true", help="Sign in to Aachman Account")
    parser.add_argument("--ecosystem-logout", action="store_true", help="Sign out of Aachman Account")
    parser.add_argument("--email", default=None, help="Email for Aachman Account sign in")
    parser.add_argument("--password", default=None, help="Password for Aachman Account sign in")

    args = parser.parse_args()

    # Handle Ecosystem Auth Commands
    if args.ecosystem_status:
        _print_ecosystem_status()
        return

    if args.ecosystem_logout:
        client = get_ecosystem_client()
        client.sign_out()
        print("\n[OK] Signed out of Aachman Account.\n")
        return

    if args.ecosystem_login:
        client = get_ecosystem_client()
        email = args.email or input("Aachman Account Email: ").strip()
        password = args.password or getpass.getpass("Aachman Account Password: ")
        res = client.sign_in(email, password)
        if res.get("success"):
            print(f"\n[OK] Successfully signed in as {email} (User ID: {client.user_id})\n")
        else:
            print(f"\n[ERROR] Sign in failed: {res.get('error')}\n")
            sys.exit(1)
        return

    if not args.prompt and not args.status and not args.history:
        parser.print_help()
        sys.exit(1)

    # ── CHECK FOR MULTI-STEP GOAL PLAN FIRST ──
    if args.prompt:
        goal_planner = GoalPlanner()
        goal_plan = goal_planner.plan_goal(args.prompt)

        if goal_plan is not None:
            if args.json:
                print(json.dumps(goal_plan.to_dict(), indent=2))
                sys.exit(0)

            print(f"\n{'=' * 60}")
            print(f"  Jarvis Goal Plan: {goal_plan.goal}")
            print(f"{'=' * 60}\n")
            print(f"  Summary : {goal_plan.summary}\n")
            print(f"  PLANNED STEPS ({len(goal_plan.steps)} total):")

            for step in goal_plan.steps:
                stype = "[READ]" if step.step_type == "read_summary" else "[WRITE]"
                print(f"    {step.order}. {stype} {step.title} ({step.status.upper()})")
                print(f"       {step.description}")
                if step.reason:
                    print(f"       Reason: {step.reason}")

            # Step-by-step confirmation loop
            for step in goal_plan.steps:
                if step.step_type == "write_action" and step.status in ("ready", "planned"):
                    print(f"\n  ┌─ STEP {step.order}: {step.title} {'─' * max(2, 35 - len(step.title))}┐")
                    print(f"  │ Command ID : {step.command_id}")
                    print("  │ Parameters :")
                    for k, v in step.parameters.items():
                        print(f"  │   • {k:10}: {v}")
                    print(f"  └{'─' * 55}┘")

                    action_choice = "confirm" if args.confirm else None
                    if not action_choice:
                        try:
                            ans = input("  Execute step? [y=Confirm / s=Skip / c=Cancel Plan / N=Stop]: ").strip().lower()
                            if ans in ("y", "yes"):
                                action_choice = "confirm"
                            elif ans in ("s", "skip"):
                                action_choice = "skip"
                            else:
                                action_choice = "cancel"
                        except (EOFError, KeyboardInterrupt):
                            action_choice = "cancel"

                    if action_choice == "confirm":
                        res = goal_planner.execute_plan_step(goal_plan, step.step_id, confirm=True)
                        if res.status == "success":
                            print(f"  [OK] Step completed: {res.message}")
                            if res.deep_link:
                                print(f"  Link: {res.deep_link}")
                        else:
                            print(f"  [FAILED] Step failed: {res.message}")
                            break
                    elif action_choice == "skip":
                        goal_planner.skip_plan_step(goal_plan, step.step_id)
                        print("  [SKIPPED] Step marked as skipped.")
                    else:
                        goal_planner.cancel_plan(goal_plan)
                        print("\n  Plan execution cancelled. Zero further writes performed.\n")
                        break

            print(f"\n{'=' * 60}\n")
            sys.exit(0)

        # ── SINGLE-STEP PLANNER & READ QUERY ──
        planner = EcosystemPlanner()
        plan_result = planner.plan_from_prompt(args.prompt)

        if plan_result is not None:
            if args.json:
                print(json.dumps(plan_result.to_dict(), indent=2))
                sys.exit(0)

            print(f"\n{'=' * 60}")
            print("  Jarvis Ecosystem Intelligence & Planning")
            print(f"{'=' * 60}\n")
            print(plan_result.answer_text)

            sugg = plan_result.suggested_action
            if sugg is not None:
                print(f"\n  ┌─ SUGGESTED ACTION {'─' * 38}┐")
                print(f"  │ Command ID : {sugg.command_id}")
                print(f"  │ Action     : {sugg.title}")
                print(f"  │ Reason     : {sugg.reason}")
                print("  │ Parameters :")
                for k, v in sugg.parameters.items():
                    print(f"  │   • {k:10}: {v}")
                print(f"  └{'─' * 57}┘\n")

                should_execute = args.confirm
                if not should_execute:
                    try:
                        ans = input("  Execute this suggested action? [y/N]: ").strip().lower()
                        should_execute = ans in ("y", "yes")
                    except (EOFError, KeyboardInterrupt):
                        should_execute = False

                if should_execute:
                    executor = EcosystemExecutor()
                    action_intent = JarvisEcosystemIntent(
                        command_id=sugg.command_id,
                        confidence=sugg.confidence,
                        parameters=sugg.parameters,
                        requires_confirmation=False,
                        summary=sugg.title,
                    )
                    res = executor.execute_intent(action_intent, confirm=True)
                    print(f"\n  [OK] {res.message}")
                    if res.deep_link:
                        print(f"  Link: {res.deep_link}\n")
                    sys.exit(0 if res.status == "success" else 1)
                else:
                    print("  Action cancelled. Zero writes executed.\n")
                    sys.exit(0)

            print(f"\n{'=' * 60}\n")
            sys.exit(0)

        # ── CHECK FOR EXPLICIT AACHMAN ECOSYSTEM WRITE/NAV ACTION ──
        eco_intent = interpret_ecosystem_query(args.prompt)
        if eco_intent is not None:
            executor = EcosystemExecutor()
            result = executor.execute_intent(eco_intent, confirm=args.confirm)

            if args.json:
                print(json.dumps(result.to_dict(), indent=2))
                sys.exit(0 if result.status in ("success", "preview") else 1)

            print(f"\n{'=' * 60}")
            print("  Jarvis Ecosystem Action")
            print(f"{'=' * 60}")
            print(f"  Command ID : {result.command_id}")
            print(f"  Status     : {result.status.upper()}")
            print(f"  Message    : {result.message}")
            if result.deep_link:
                print(f"  Deep Link  : {result.deep_link}")

            if result.status == "preview":
                print("\n  PREVIEW PARAMETERS:")
                for k, v in result.preview_data.get("parameters", {}).items():
                    print(f"    - {k:12}: {v}")
                if result.preview_data.get("missing_fields"):
                    print(f"    [!] Missing fields: {', '.join(result.preview_data['missing_fields'])}")
                print("\n  To execute this action, run again with `--confirm`.")
                print(f"{'=' * 60}\n")
                sys.exit(0)

            print(f"{'=' * 60}\n")
            sys.exit(0 if result.status == "success" else 1)

    # ── REGULAR SCENE GENERATION PIPELINE ──
    jarvis, _db, memory, _cfg = _bootstrap()

    if args.status:
        snap = jarvis.status() if hasattr(jarvis, "status") else jarvis.snapshot()
        print("\n=== Jarvis Status ===")
        print(f"  Uptime : {snap.get('uptime_seconds', 0)}s")
        print(f"  Wired  : {snap.get('wired', True)}")
        print()
        return

    if args.history:
        records = memory.recall(args.history)
        print(f"\n=== Jarvis Memory (last {len(records)} runs) ===")
        for index, record in enumerate(records, 1):
            outcome_icon = "[OK]" if record.get("outcome") == "success" else "[XX]"
            print(f"  {index:>3}. {outcome_icon} {record.get('prompt', '')[:60]}")
        print()
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
        print(f"\nJarvis Result Status: {result.status.upper()}")
        print(f"Duration: {result.duration_seconds:.1f}s")
        if result.godot_project:
            print(f"Godot Project: {result.godot_project}")

    sys.exit(0 if result.status == "success" else 1)


if __name__ == "__main__":
    main()
