"""Clean root media and temporary runtime json logs."""
import shutil
from pathlib import Path

root = Path(".")
media_dir = root / "archive" / "media"

for f in ["render_trailer_mp4.py", "aachmanstiudios.png"]:
    p = root / f
    if p.exists():
        shutil.move(str(p), str(media_dir / f))
        print(f"Moved {f} -> archive/media/{f}")

for f in [
    "agent_timeline.json",
    "dependency_graph.json",
    "execution_metrics.json",
    "execution_timeline.json",
    "worker_statistics.json",
    "test_planning.db",
    "test_pyflare.db",
]:
    p = root / f
    if p.exists():
        p.unlink()
        print(f"Cleaned {f}")

job_dir = root / "job123"
if job_dir.exists():
    shutil.rmtree(str(job_dir), ignore_errors=True)
    print("Cleaned job123 directory")
