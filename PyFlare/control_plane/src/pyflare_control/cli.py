"""Small diagnostic CLI for the control-plane foundation."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .hardware import capture_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pyflare-control")
    subparsers = parser.add_subparsers(dest="command", required=True)
    hardware = subparsers.add_parser("hardware", help="print a conservative hardware snapshot")
    hardware.add_argument(
        "--online",
        action="store_true",
        help="declare network available; no external probe is performed",
    )
    hardware.add_argument("--foreground", choices=("unity", "blender"))
    hardware.add_argument("--vram-mb", type=int)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    if arguments.command == "hardware":
        snapshot = capture_snapshot(
            online=arguments.online,
            foreground_application=arguments.foreground,
            vram_available_mb=arguments.vram_mb,
        )
        print(json.dumps(asdict(snapshot), indent=2, default=list))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
