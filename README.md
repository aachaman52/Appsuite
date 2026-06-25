# AppSuite & Jarvis Orchestrator Workspace

Welcome to the unified workspace for **AppSuite** and **Jarvis Orchestrator**. This repository integrates AI-driven 3D asset search/generation, quality validation pipelines, and automated game engine scene assembly, powered by a state-of-the-art orchestration graph.

---

## 📂 Workspace Structure

This workspace is composed of two primary directories:

*   **[`AppSuite_JarvisV1`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1)**: The core implementation of the AppSuite asset pipeline and the Jarvis supervisor agent.
*   **[`langgraph-main`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/langgraph-main)**: The reference framework for low-level orchestration of stateful agents, which inspires the custom `GraphOrchestrator` in Jarvis.

---

## 🚀 AppSuite: AI-Powered 3D Content Pipeline

Given a natural-language prompt (e.g., *"Create a medieval village with houses, barrels, trees, and NPCs"*), AppSuite automates:
1.  **Asset Sourcing**: Searches public asset databases (Kenney, Poly Pizza, OpenGameArt) or generates them using AI providers.
2.  **Conversion & Material Audit**: Converts glTF/GLB models to Obj/FBX and verifies material and texture coordinates.
3.  **Headless Blender Assembly**: Places assets in a 3D scene grid, assigns transforms, configures materials, and exports to FBX.
4.  **Godot Import & Assembly**: Automatically imports the FBX models, configures collisions/lighting, and builds a playable Godot scene.
5.  **Runtime Headless Verification**: Launches the scene inside a headless Godot runner to verify mesh existence and material/texture survival.

### 🎭 System Architecture

```
User Prompt
    │
    ▼
┌────────────────────────────────────────────────────────┐
│ Jarvis Planner (Rule-based Templates & Semantic Memory) │
└───────────────────────────┬────────────────────────────┘
                            │ (Scene Plan & Strategy)
                            ▼
┌────────────────────────────────────────────────────────┐
│ GraphOrchestrator (Stateful Parallel DAG Execution)    │
└───────────────────────────┬────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Internet    │    │  Analysis    │    │   Blender    │
│  Worker      │    │  Worker      │    │   Worker     │
└───────┬──────┘    └───────┬──────┘    └───────┬──────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                    ┌──────────────┐
                    │    Godot     │
                    │    Worker    │
                    └───────┬──────┘
                            ▼
                    ┌──────────────┐
                    │  Validation  │
                    │  Worker      │
                    └──────────────┘
```

---

## 🛠️ Quick Start

### 1. Requirements & Setup
Ensure you have **Python 3.12** installed on your system. Run the following setup commands inside `AppSuite_JarvisV1`:

```powershell
cd AppSuite_JarvisV1

# Install required dependencies
python -m pip install -r requirements.txt

# Initialize the SQLite database
python scripts/init_db.py
```

### 2. Run the API Server
AppSuite provides a FastAPI backend to schedule and monitor 3D generation jobs.
```powershell
python -m appsuite.main
```
*   **API Port**: `http://localhost:8000`
*   **Interactive Documentation**: `http://localhost:8000/docs`

### 3. Run a Command-Line Job
You can trigger a full pipeline execution directly from the command line:
```powershell
python scripts/run_job.py "Create a medieval village with houses, barrels, trees, roads, NPCs and lighting."
```

---

## 📊 Component Blueprint

| Component | Directory / File | Description |
| :--- | :--- | :--- |
| **Jarvis Planner** | [`jarvis_planner.py`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1/appsuite/core/jarvis_planner.py) | Resolves layout templates and plans required assets from prompt heuristics. |
| **Graph Orchestrator** | [`graph.py`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1/appsuite/graph/graph.py) | State-machine orchestrator ensuring checkpointing, parallelism, and recovery. |
| **Semantic Memory** | [`agent_memory.py`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1/appsuite/core/semantic_memory/agent_memory.py) | Remembers successful runs and layout templates to minimize generation overhead. |
| **Internet Worker** | [`internet_worker.py`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1/appsuite/workers/internet_worker.py) | Searches and pulls models, caching assets under standard GLB formats. |
| **Analysis Worker** | [`analysis_worker.py`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1/appsuite/workers/analysis_worker.py) | Performs pre-import GLB audit checks, slots materials, and resolves texture paths. |
| **Blender Worker** | [`blender_worker.py`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1/appsuite/workers/blender_worker.py) | Executes headless Blender automation scripts to scale, assemble, and export FBX files. |
| **Godot Worker** | [`godot_worker.py`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1/appsuite/workers/godot_worker.py) | Builds Godot scenes (.tscn), configures lights, environments, and collisions. |
| **Validation Worker** | [`validation_worker.py`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1/appsuite/workers/validation_worker.py) | Executes headless Godot validation scripts to test visual and node conformity. |

---

## 🛡️ Pipeline Diagnostics & Reliability Testing

AppSuite contains built-in automated validation tools to ensure material pipeline survival and prevent missing textures.

### 1. Reliability Sweep Suite
Run the suite of 15 pre-selected 3D assets of different formats (GLB, FBX, OBJ) to evaluate import/export fidelity:
```powershell
python scripts/test_pipeline_reliability.py
```
This script evaluates the success rate and outputs a full diagnostic report: [`reliability_report.md`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1/reliability_report.md).

### 2. Headless Godot Editor Verification
Evaluate if scenes render properly in Godot and take screenshots automatically:
```powershell
python scripts/run_visual_validation.py
```
Outputs:
*   Screenshot: `godot_screenshot.png`
*   Visual Validation Report: [`godot_visual_validation_report.md`](file:///c:/Users/91629/OneDrive/%E0%B9%80%E0%B8%AD%E0%B8%81%E0%B8%AA%E0%B8%B2%E0%B8%A3/Desktop/New%20folder%20%283%29/AppSuite_JarvisV1/godot_visual_validation_report.md)
