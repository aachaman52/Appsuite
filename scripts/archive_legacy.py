"""Archive obsolete and legacy non-canonical files according to ARCHIVE_MANIFEST.md."""
import os
import shutil
from pathlib import Path

root = Path(".")
archive_root = root / "archive"
archive_root.mkdir(parents=True, exist_ok=True)

# 1. Archive OS builder (PyFlare/)
pyflareos_src = root / "PyFlare"
pyflareos_dst = archive_root / "pyflareos"
if pyflareos_src.exists() and not pyflareos_dst.exists():
    shutil.move(str(pyflareos_src), str(pyflareos_dst))
    print(f"Moved {pyflareos_src} -> {pyflareos_dst}")

# 2. Archive trailer_app and raw mp4 media
media_dst = archive_root / "media"
media_dst.mkdir(parents=True, exist_ok=True)

trailer_src = root / "trailer_app"
if trailer_src.exists():
    shutil.move(str(trailer_src), str(media_dst / "trailer_app"))
    print(f"Moved {trailer_src} -> {media_dst / 'trailer_app'}")

for mp4 in root.glob("*.mp4"):
    shutil.move(str(mp4), str(media_dst / mp4.name))
    print(f"Moved {mp4.name} -> {media_dst / mp4.name}")

# 3. Archive large markdown AI transcripts and audits
docs_dst = archive_root / "docs"
docs_dst.mkdir(parents=True, exist_ok=True)

doc_files = [
    "Fixing AppSuite Jarvis Architecture.md",
    "Analyzing Artisan AI Appsuite.md",
    "Architectural Review of AppSuite Jarvis.md",
    "Audit by 17.7.26",
]
for doc in doc_files:
    p = root / doc
    if p.exists():
        shutil.move(str(p), str(docs_dst / doc))
        print(f"Moved {doc} -> {docs_dst / doc}")

# 4. Archive legacy Godot UI project
legacy_ui_dst = archive_root / "legacy_ui"
legacy_ui_src = root / "AppSuite_JarvisV1"
if legacy_ui_src.exists() and not legacy_ui_dst.exists():
    shutil.move(str(legacy_ui_src), str(legacy_ui_dst))
    print(f"Moved {legacy_ui_src} -> {legacy_ui_dst}")

# 5. Remove vendored duplicate langgraph-main
langgraph_src = root / "langgraph-main"
if langgraph_src.exists():
    shutil.rmtree(str(langgraph_src), ignore_errors=True)
    print("Removed duplicate vendored langgraph-main")

print("Archival operations completed successfully")
