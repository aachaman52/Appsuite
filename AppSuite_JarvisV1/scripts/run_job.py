"""CLI: submit a prompt and run it synchronously through the full pipeline.

Usage:
    python scripts/run_job.py "Create a medieval village with houses, trees, NPCs"
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from appsuite.config import load_config
from appsuite.main import AppContext


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_job.py \"<prompt>\"")
        sys.exit(1)
    prompt = sys.argv[1]
    ctx = AppContext(load_config())
    job_id = str(uuid.uuid4())
    ctx.db.create_job(job_id, prompt, None)
    job = ctx.db.get_job(job_id)
    print(f"Running job {job_id} ...")
    summary = ctx.pipeline.execute(job)
    import json
    ctx.db.update_job(job_id, status="completed", result_json=json.dumps(summary))
    ctx.memory.remember(job_id, prompt, summary["template"], "success", summary)
    print(json.dumps(summary, indent=2))
    print(f"\nGodot project: {summary.get('godot_project')}")
    ctx.db.close()


if __name__ == "__main__":
    main()