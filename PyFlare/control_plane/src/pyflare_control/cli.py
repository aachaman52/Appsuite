"""CLI for PyFlare Control Plane and Developer Workflows."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from types import MappingProxyType

from .auth import AuthManager
from .context import ProjectContextManager
from .hardware import capture_snapshot, detect_hardware
from .model_registry import ModelCapabilityRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyflare-control",
        description="PyFlare Control Plane CLI for game developer workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── hardware ──────────────────────────────────────────────────────────────
    hw_parser = subparsers.add_parser("hardware", help="print conservative hardware snapshot")
    hw_parser.add_argument(
        "--online",
        action="store_true",
        help="declare network available; no external probe is performed",
    )
    hw_parser.add_argument("--foreground", choices=("unity", "blender"))
    hw_parser.add_argument("--vram-mb", type=int)

    # ── models ────────────────────────────────────────────────────────────────
    models_parser = subparsers.add_parser("models", help="model capability registry and selection")
    model_sub = models_parser.add_subparsers(dest="model_action", required=True)

    model_sub.add_parser("list", help="list registered model architectures and tiers")

    rec_parser = model_sub.add_parser("recommend", help="recommend model based on hardware")
    rec_parser.add_argument("--vram-mb", type=int, help="override detected VRAM in MB")
    rec_parser.add_argument("--free-disk-mb", type=int, help="override available disk in MB")
    rec_parser.add_argument("--api-only", action="store_true", help="force API-only tier selection")

    # ── context ───────────────────────────────────────────────────────────────
    ctx_parser = subparsers.add_parser("context", help="manage project context indexing and query")
    ctx_sub = ctx_parser.add_subparsers(dest="context_action", required=True)

    reg_proj = ctx_sub.add_parser("register", help="register a project directory")
    reg_proj.add_argument("--project-id", required=True, help="unique project ID")
    reg_proj.add_argument("--path", required=True, type=Path, help="path to project directory")
    reg_proj.add_argument("--db", type=Path, default=Path(".pyflare/context.sqlite3"))

    idx_proj = ctx_sub.add_parser("index", help="index or refresh project files")
    idx_proj.add_argument("--project-id", required=True, help="unique project ID")
    idx_proj.add_argument("--db", type=Path, default=Path(".pyflare/context.sqlite3"))

    qry_proj = ctx_sub.add_parser("query", help="query context for relevant snippets")
    qry_proj.add_argument("--project-id", required=True, help="unique project ID")
    qry_proj.add_argument("--intent", required=True, help="user query or task intent")
    qry_proj.add_argument("--max-tokens", type=int, default=4000, help="max token budget")
    qry_proj.add_argument("--db", type=Path, default=Path(".pyflare/context.sqlite3"))

    # ── auth ──────────────────────────────────────────────────────────────────
    auth_parser = subparsers.add_parser("auth", help="manage user identity and credentials")
    auth_sub = auth_parser.add_subparsers(dest="auth_action", required=True)

    create_u = auth_sub.add_parser("create-user", help="create local user identity")
    create_u.add_argument("--username", "--user-id", dest="username", required=True)
    create_u.add_argument("--password", required=True)
    create_u.add_argument("--db", type=Path, default=Path(".pyflare/auth.sqlite3"))

    set_k = auth_sub.add_parser("set-key", help="store provider API credential")
    set_k.add_argument("--provider-id", required=True)
    set_k.add_argument("--api-key", required=True)
    set_k.add_argument("--db", type=Path, default=Path(".pyflare/auth.sqlite3"))

    return parser


def handle_hardware(arguments: argparse.Namespace) -> int:
    snapshot = capture_snapshot(
        online=arguments.online,
        foreground_application=arguments.foreground,
        vram_available_mb=arguments.vram_mb,
    )
    print(json.dumps(asdict(snapshot), indent=2, default=list))
    return 0


def handle_models(arguments: argparse.Namespace) -> int:
    registry = ModelCapabilityRegistry()
    if arguments.model_action == "list":
        models = [asdict(m) for m in registry.all_models()]
        print(json.dumps(models, indent=2, default=str))
        return 0

    if arguments.model_action == "recommend":
        hw = detect_hardware()
        if arguments.vram_mb is not None:
            hw = replace(hw, gpu_vram_mb=arguments.vram_mb)
        if arguments.free_disk_mb is not None:
            hw = replace(hw, storage_available_mb=arguments.free_disk_mb)

        rec = registry.recommend(
            hardware=hw,
            api_only=arguments.api_only,
        )
        out = {
            "tier": rec.selected_tier.value,
            "recommended_model": asdict(rec.recommended_model) if rec.recommended_model else None,
            "is_compatible": rec.is_compatible,
            "explanation": rec.explanation,
            "compatible_models": [m.model_id for m in rec.compatible_models],
            "incompatible_reasons": rec.incompatible_reasons,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0
    return 2


def handle_context(arguments: argparse.Namespace) -> int:
    db_path = arguments.db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    manager = ProjectContextManager(db_path)

    if arguments.context_action == "register":
        info = manager.register_project(arguments.project_id, arguments.path.resolve())
        print(
            json.dumps(
                {
                    "project_id": info.project_id,
                    "name": info.name,
                    "root_path": info.root_path,
                    "project_type": info.project_type,
                    "metadata": info.metadata,
                },
                indent=2,
            )
        )
        return 0

    if arguments.context_action == "index":
        report = manager.index_project(arguments.project_id)
        print(
            json.dumps(
                {
                    "project_id": report.project_id,
                    "indexed_files": report.indexed_files,
                    "total_chunks": report.total_chunks,
                    "duration_seconds": round(report.duration_seconds, 3),
                    "status": "ready",
                },
                indent=2,
            )
        )
        return 0

    if arguments.context_action == "query":
        context = manager.retrieve_context(
            arguments.project_id,
            arguments.intent,
            max_tokens=arguments.max_tokens,
        )
        out = {
            "project_id": context.project_id,
            "estimated_tokens": context.estimated_tokens,
            "total_characters": context.total_characters,
            "sources": [
                {
                    "rel_path": s.rel_path,
                    "score": round(s.score, 3),
                    "line_range": f"{s.start_line}-{s.end_line}",
                    "snippet": s.content[:200] + ("..." if len(s.content) > 200 else ""),
                }
                for s in context.sources
            ],
        }
        print(json.dumps(out, indent=2))
        return 0
    return 2


def handle_auth(arguments: argparse.Namespace) -> int:
    db_path = arguments.db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    auth = AuthManager(db_path)

    if arguments.auth_action == "create-user":
        user = auth.register_user(arguments.username, arguments.password)
        print(
            json.dumps(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "created_at": user.created_at,
                },
                indent=2,
            )
        )
        return 0

    if arguments.auth_action == "set-key":
        auth.set_provider_credential(arguments.provider_id, arguments.api_key)
        print(json.dumps({"status": "stored", "provider_id": arguments.provider_id}, indent=2))
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "hardware":
        return handle_hardware(arguments)
    if arguments.command == "models":
        return handle_models(arguments)
    if arguments.command == "context":
        return handle_context(arguments)
    if arguments.command == "auth":
        return handle_auth(arguments)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
