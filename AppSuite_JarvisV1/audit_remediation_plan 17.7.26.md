# AppSuite Audit Remediation Plan

Based on the technical audit (from 17.7.26), the platform suffers from a "prototype-to-production" gap. It appears highly functional on the surface but relies on mock implementations, thread-unsafe infrastructure, and disconnected architectural components.

## Core Problems Identified

1. **Fake Successes (Mocks & Fallbacks):** When Blender or Godot binaries fail, the system silently generates "stubs" (fake ASCII FBXs) and considers the task successful. The validation worker only checks if files exist, not if they work.
2. **Database & Concurrency:** The SQLite database is single-threaded but being accessed concurrently by the Supervisor, leading to crashes. 
3. **Architectural Fiction:** 
    - **Memory:** Records are written but never read/used for future planning.
    - **Agents:** The multi-agent system exists in code but is never used; monolithic workers do all the work in a linear pipeline.
4. **Security Risks:** API keys and FTP credentials are in plaintext, and there are vectors for Zip Slip and Shell Injection.
5. **No Transaction Rollbacks:** Failed jobs leave corrupted or partial files on disk.

---

## Phased Remediation Plan

### Phase 1: Stabilization & "Truthfulness" (Days 1-3)
*Goal: Stop the system from lying about successes and fix core crashes.*
1. **Database Refactor:** Implement a connection pool for SQLite or migrate to PostgreSQL to fix "database is locked" concurrency crashes.
2. **Worker Dependency Registry:** Create a `WorkerHealthMonitor` and run `run_preflight()` at startup. Dashboard should show "🔴 Missing Blender" instead of crashing later.
3. **Remove Stubs:** Delete the fallback stub generators. If Blender fails, the job must fail and trigger a retry, rather than faking success.
4. **Strict Success Criteria:** Success must equal `godot_scene_loadable and imports_successful and scripts_compile and validation_passed`. Real 40% reliability is better than fake 90% reliability.
5. **Job Sandboxing:** Ensure every job gets isolated `output/job-id/` and `temp/job-id/` directories. Implement rollback routines (`shutil.rmtree(temp_job)` and `rollback_db()`) on failure.

### Phase 2: Security & State Management (Days 4-5)
*Goal: Secure the application, manage configurations, and limit resources.*
1. **Config Validation:** Run `ConfigValidator.validate()` at startup to verify API keys, paths, Godot binary, Blender version, and write permissions.
2. **Secrets Management:** Move all plaintext credentials from `config.json` to `.env` variables or a secrets manager.
3. **Input Sanitization:** Fix the Zip Slip vulnerability in `internet_worker.py` and sanitize arguments passed to subprocesses in Godot/Blender workers.
4. **Resource Limits:** Implement limits to prevent massive asset downloads, runaway RAM usage, and too many concurrent workers.

### Phase 3: Activating Autonomy (Days 6-10)
*Goal: Make the aspirational AI features actually influence behavior. (Memory -> Store -> Retrieve -> Change Planning)*
1. **Memory Integration:** The Supervisor must query memory. If a previous template failed 8 times and another succeeded 92% of the time, `choose_template_B()` must be dynamically selected.
2. **Agent Migration:** Begin breaking down the monolithic workers into the `BaseAgent` structure, allowing the orchestrator to dynamically route tasks (DAG) instead of using a rigid linear pipeline.

### Phase 4: Observability (Days 11-12)
*Goal: Provide visibility into real system health.*
1. **Dashboard Wiring:** Connect the `DashboardApp` to the `EventBus` so metrics and logs are exposed.
2. **Timeline Recorder:** Store granular job data: Worker Start, Worker End, Memory Used, Tokens, Failures, and Retries.

### Phase 5: Production Pipeline (Days 13-20)
*Goal: Validate what the AI makes actually works.*
1. **Real Asset Validation:** Actually open `godot --headless` to test imports, meshes, textures, and scene loading integrity.
2. **Integration Tests:** Automate `Generate FPS`, `Generate Platformer`, and `Generate RPG` to run on every commit.
3. **Reliability Benchmarks:** Target metrics: Scene Load Success >90%, Asset Import >95%, Worker Recovery >80%, Full Pipeline Success >75%.

### Phase 6: Freeze Features
*Goal: Stop building features, finish the product.*
1. **No Scope Creep:** ❌ No Linux distro, ❌ No Browser AI everywhere, ❌ No 200 agents, ❌ No Marketplace.
2. **Core Focus:** ✅ Generation pipeline, ✅ Reliability, ✅ Memory, ✅ Validation.
