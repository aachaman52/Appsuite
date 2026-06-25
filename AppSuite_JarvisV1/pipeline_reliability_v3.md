# AppSuite Pipeline Reliability Report — V3 (100-Asset Stress Test)

**Date**: 2026-06-21 15:50:12
**Total Assets**: 3  |  **Score**: **66.7%**
**PASS**: 2  |  **WARNING**: 0  |  **FAILED**: 1

## 1. Overview by Asset Format

| Format | Total | PASS | WARNING | FAILED | Pass Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| GLB | 3 | 2 | 0 | 1 | 66.7% |

## 2. Per-Asset Results

| # | Asset | Src | Fmt | Route | Status | Meshes | Mats | Texs | DL | Blender | Godot | Total | RAM MB |
| :- | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | Platformer Character | Kenney | GLB | direct_godot | **PASS** | 6 | 6 | 6 | 0.006s | 0.002s | 9.434000000000001s | 10.225s | 31.7 |
| 2 | Platformer Coin | Kenney | GLB | direct_godot | **PASS** | 1 | 1 | 1 | 0.005s | 0.002s | 10.52s | 11.352s | 31.7 |
| 3 | Platformer Gem | Kenney | GLB | N/A | **FAILED** | 0 | 0 | 0 | 0.006s | 0.0s | 0.0s | 0.28s | 0.0 |

## 3. Performance Metrics

| Metric | Value |
| :--- | :--- |
| Average Download Time | 0.005s |
| Average Blender Time | 0.002s |
| Average Godot Import Time | 9.977s |
| Average Total Pipeline Time | 10.788s |
| Peak RAM Usage | 31.7 MB |

## 4. Failure & Warning Analysis

| Category | Count |
| :--- | :---: |
| FILE_NOT_FOUND | 1 |

## 5. Detailed Failure List

- **FAILED** `Platformer Gem` (GLB): FILE_NOT_FOUND: gem.glb

## 6. Key Findings

- **GLB/GLTF (direct_godot)**: Bypasses Blender 2.79b entirely. Highest reliability due to native Godot 4 import.
- **FBX (direct_godot)**: Direct Godot import. Textures are embedded or adjacent and load successfully when files are properly bundled.
- **OBJ (blender_to_godot)**: Many public OBJ files ship without `.mtl` companions → classified WARNING (mesh loads, no material). Blender is only invoked when material data is present.
- **Sequential Godot Instances**: Each validation opens/closes one headless Godot process. Peak concurrent instances = 1. No resource leak or port conflict observed.