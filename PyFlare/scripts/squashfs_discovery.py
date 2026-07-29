#!/usr/bin/env python3
"""
squashfs_discovery.py
---------------------
Automatically detects the correct root filesystem squashfs from an extracted
Ubuntu ISO, regardless of release version or filename convention.

Ubuntu has changed squashfs naming across releases:
  - 20.04/22.04 Desktop: casper/filesystem.squashfs
  - 22.04/24.04 Server:  casper/ubuntu-server-minimal.squashfs
                          casper/ubuntu-server-minimal.ubuntu-server.squashfs
                          casper/ubuntu-server-minimal.ubuntu-server.installer.*.squashfs
  - Future releases:     Unknown, handled via scoring heuristics.

Priority scoring (lower = preferred):
  Score 10: *.ubuntu-server.squashfs  (Server root — most specific non-installer match)
  Score 20: *-minimal.squashfs        (Server minimal — pre-install base)
  Score 30: filesystem.squashfs       (Desktop / legacy)
  Score 40: Any other *.squashfs not containing 'installer'
  Score 90: installer-only squashfs   (Last resort, explicitly logged as warning)
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def _log(logger: Optional[logging.Logger], level: str, msg: str):
    if logger:
        getattr(logger, level)(msg)
    else:
        print(f"[{level.upper()}] {msg}")


def _score(path: Path) -> Tuple[int, str]:
    """
    Returns (score, reason) for a squashfs candidate.
    Lower score = higher priority.
    """
    name = path.name.lower()
    
    # Installer images — these are not root filesystems
    if "installer" in name:
        return (90, "installer image (lowest priority)")

    # *.ubuntu-server.squashfs — most targeted server root
    if name.endswith(".ubuntu-server.squashfs"):
        return (10, "ubuntu-server root filesystem (highest priority)")

    # *-minimal.squashfs — server minimal base (e.g., ubuntu-server-minimal.squashfs)
    if name.endswith("-minimal.squashfs") or name == "ubuntu-server-minimal.squashfs":
        return (20, "server-minimal base filesystem")

    # Classic desktop layout
    if name == "filesystem.squashfs":
        return (30, "standard desktop filesystem.squashfs")

    # Anything else that is not an installer
    return (40, "unknown non-installer squashfs")


def discover_squashfs(extract_dir: Path, logger: Optional[logging.Logger] = None) -> Path:
    """
    Discovers the correct root squashfs from an extracted Ubuntu ISO.

    Searches:
      <extract_dir>/casper/
      <extract_dir>/install/

    Logs every candidate found and explains the selection decision.

    Raises RuntimeError if no valid candidate exists, printing the directory
    tree of the casper/ directory before failing.
    """
    search_dirs = [extract_dir / "casper", extract_dir / "install"]
    all_found: List[Path] = []

    for sdir in search_dirs:
        if sdir.exists():
            # Recursive search to catch any subdirectory layouts in future releases
            found = list(sdir.rglob("*.squashfs"))
            if found:
                _log(logger, "info", f"Discovered {len(found)} squashfs file(s) in {sdir.name}/:")
                for f in found:
                    _log(logger, "info", f"  - {f.relative_to(extract_dir)}")
                all_found.extend(found)

    if not all_found:
        # Print full directory tree before failing so the user can debug
        tree = _get_dir_tree(extract_dir)
        msg = (
            f"No *.squashfs files found under {extract_dir}.\n"
            f"Directory tree:\n{tree}"
        )
        _log(logger, "error", msg)
        raise RuntimeError(msg)

    # Score every candidate
    scored: List[Tuple[int, str, Path]] = []
    for candidate in all_found:
        score, reason = _score(candidate)
        scored.append((score, reason, candidate))

    scored.sort(key=lambda x: x[0])

    # Log all candidates and their scores
    _log(logger, "info", "Squashfs candidate scoring:")
    for score, reason, path in scored:
        _log(logger, "info",
             f"  score={score:3d}  {path.relative_to(extract_dir)}  ({reason})")

    best_score, best_reason, chosen = scored[0]

    # Warn if we were forced to fall back to an installer image
    if best_score >= 90:
        _log(logger, "warning",
             "Only installer squashfs images found — this may produce an incomplete system.")

    _log(logger, "info",
         f"[OK] Selected squashfs: {chosen.name}\n"
         f"     Reason: {best_reason}\n"
         f"     Path:   {chosen.relative_to(extract_dir)}")

    return chosen


def _get_dir_tree(root: Path, prefix: str = "") -> str:
    """Returns a textual tree of the directory for diagnostic output."""
    lines = []
    try:
        children = sorted(root.iterdir())
    except PermissionError:
        return f"{prefix}[Permission Denied]"
    for i, child in enumerate(children):
        connector = "└── " if i == len(children) - 1 else "├── "
        lines.append(f"{prefix}{connector}{child.name}")
        if child.is_dir():
            extension = "    " if i == len(children) - 1 else "│   "
            sub = _get_dir_tree(child, prefix + extension)
            if sub:
                lines.append(sub)
    return "\n".join(lines)
