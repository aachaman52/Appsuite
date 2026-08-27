"""Quick real-world test: 2 Kenney + 2 Poly Pizza assets through Download -> Extract -> Validate."""
import sys, time, json, shutil
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from appsuite.config import load_config
from appsuite.workers.internet_worker import InternetWorker
from appsuite.workers.analysis_worker import AnalysisWorker
from appsuite.db import Database
from appsuite.core.asset_registry import AssetRegistry
from appsuite.core.provider_manager import ProviderManager

ASSETS = [
    {
        "source": "Kenney",
        "name": "Platformer Kit",
        "url": "https://github.com/KenneyNL/Starter-Kit-3D-Platformer/archive/refs/heads/main.zip",
    },
    {
        "source": "Kenney",
        "name": "City Builder Kit",
        "url": "https://github.com/KenneyNL/Starter-Kit-City-Builder/archive/refs/heads/main.zip",
    },
    {
        "source": "Poly Pizza",
        "name": "GLTF Animation Library",
        "url": "https://github.com/J-Ponzo/gltf-universal-animation-library/archive/refs/heads/main.zip",
    },
    {
        "source": "Poly Pizza",
        "name": "FBX Quaternius Pack",
        "url": "https://github.com/V-Sekai-fire/TEST_fbx_quaternius/archive/refs/heads/main.zip",
    },
]


def main():
    tmp = Path(tempfile.mkdtemp())
    db = Database(tmp / "test.db")
    registry = AssetRegistry(db)
    providers = ProviderManager([])

    cfg = load_config()
    worker = InternetWorker(
        cfg.workers.get("internet", {}), cfg.retries, {},
        provider_manager=providers, registry=registry,
        assets_dir=tmp / "assets", cache_dir=tmp / "cache",
    )

    results = []
    for asset in ASSETS:
        print(f"\n--- {asset['source']} : {asset['name']} ---")
        t0 = time.time()
        try:
            # Step 1: Download
            archive = worker._download_archive(asset["url"], timeout=300)
            dl_time = round(time.time() - t0, 2)
            print(f"  Download: {archive.stat().st_size // 1024} KB in {dl_time}s")

            # Step 2: Validate archive
            valid = worker._validate_archive(archive)
            print(f"  Archive valid: {valid}")
            if not valid:
                results.append({"asset": asset["name"], "status": "FAIL", "reason": "corrupt_archive"})
                continue

            # Step 3: Extract
            t1 = time.time()
            files = worker.extract_archive(archive)
            ex_time = round(time.time() - t1, 2)
            print(f"  Extracted {len(files)} files in {ex_time}s")

            # Step 4: Detect models
            detected = worker.detect_assets(files)
            models = detected["models"]
            textures = detected["textures"]
            print(f"  Models: {len(models)}, Textures: {len(textures)}")

            if not models:
                results.append({"asset": asset["name"], "status": "FAIL", "reason": "no_models_found"})
                continue

            # Step 5: Validate main model
            main = detected["main_model"]
            val = worker._validate_model_file(main)
            kb = main.stat().st_size // 1024
            print(f"  Main model: {main.name} ({kb} KB)")
            print(f"  Validation: {val}")

            results.append({
                "asset": asset["name"],
                "source": asset["source"],
                "status": "PASS" if val["valid"] else "FAIL",
                "reason": val.get("reason"),
                "warning": val.get("warning"),
                "model": main.name,
                "model_size_kb": kb,
                "models_found": len(models),
                "textures_found": len(textures),
                "download_time_s": dl_time,
                "extract_time_s": ex_time,
            })

        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append({
                "asset": asset["name"],
                "source": asset.get("source", "?"),
                "status": "FAIL",
                "reason": str(exc)[:200],
            })

    # Summary
    print("\n=== RESULTS ===")
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"{passed}/{len(results)} passed")
    for r in results:
        tag = "[PASS]" if r["status"] == "PASS" else "[FAIL]"
        warn = f" (warning: {r.get('warning')})" if r.get("warning") else ""
        print(f"  {tag} {r['asset']}: {r.get('reason', 'ok')}{warn}")

    db.close()
    shutil.rmtree(tmp, ignore_errors=True)
    return results


if __name__ == "__main__":
    res = main()
    print(json.dumps(res, indent=2))
