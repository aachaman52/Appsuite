# Hardware Telemetry & Resource Routing

## Overview

PyFlare’s `HardwareManager` inspects host system hardware metrics, CPU topology, GPU state, memory availability, and installed binary tools to inform the **Deterministic Router**.

---

## Hardware Profile Telemetry (`HardwareProfile`)

The telemetry model captures real-time host resource availability:

| Metric | Field | Description | Fallback Behavior |
| :--- | :--- | :--- | :--- |
| **CPU Cores** | `cpu_cores_logical`, `cpu_cores_physical` | Total logical & physical execution threads | Defaults to `os.cpu_count()` or 1 |
| **RAM** | `ram_total_mb`, `ram_available_mb` | Total and currently available system memory | Uses `psutil.virtual_memory()` or safe static estimates |
| **GPU & VRAM** | `gpu_name`, `vram_total_mb`, `vram_available_mb` | Discrete NVIDIA GPU name and free video memory | Queried via `nvidia-smi`; falls back to CPU mode if absent |
| **Disk Space** | `disk_available_gb` | Free space on the working drive | Calculated via `shutil.disk_usage` |
| **Tool Binaries** | `installed_binaries` | Detection map (`blender`, `godot`, `ffmpeg`, `git`, `python`) | Checked via `shutil.which` without blocking |
| **Resource Pressure** | `resource_pressure` | `% CPU`, `% RAM`, `% Disk` utilization | Monitored to throttle heavy worker dispatch |

---

## Normalized Hardware Tiers

Hardware is categorized into three normalized tiers:

* **`high`**: $\ge 16\text{ GB RAM}$, $\ge 6\text{ GB VRAM}$, $\ge 8\text{ logical CPU cores}$. Suitable for local 70B LLMs, heavy Blender Cycles rendering, and neural 3D synthesis.
* **`mid`**: $\ge 8\text{ GB RAM}$, $(\ge 2\text{ GB VRAM} \text{ or } \ge 4\text{ logical CPU cores})$. Suitable for local lightweight models, Godot headless compilation, and Blender workbench rendering.
* **`weak`**: $< 8\text{ GB RAM}$ or $< 500\text{ MB available RAM}$. Throttles heavy local neural pipelines, preferring lightweight rule engines or cloud dispatch when allowed.

> [!NOTE]
> The hardware tier is informational. The **Deterministic Router** uses *actual resource quantities* (available RAM/VRAM) to evaluate each candidate rather than relying solely on the tier label.

---

## Host Protection & Anti-Crash Safety

1. **Non-Crashing Inspection**: If `psutil` or `nvidia-smi` is not installed or errors, `HardwareManager` catches exceptions and provides safe default telemetry.
2. **RAM Guardrails**:
   * If available RAM is insufficient for a candidate's `min_ram_mb`, the candidate is rejected with an explanatory rejection reason.
   * `HardwareManager.can_worker_run()` pauses heavy workers (`blender`, `godot`) if system RAM utilization exceeds 85%.
3. **Discrete GPU Independence**: Absence of an NVIDIA GPU does not crash Blender or other workers; CPU fallbacks are engaged automatically.
