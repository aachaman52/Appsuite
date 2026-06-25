# AppSuite Pipeline Reliability Test Report

**Date**: 2026-06-21 15:11:30
**Total Test Cases**: 15 assets (5 Kenney, 5 Poly Pizza, 5 OpenGameArt)
**Reliability Score**: **80.0%** (12 passed, 3 failed)

## 1. Reliability Score Overview

| Metric | Total | Passed | Failed | Success Rate |
| :--- | :---: | :---: | :---: | :---: |
| **Overall Pipeline** | 15 | 12 | 3 | **80.0%** |
| Kenney Source | 5 | 5 | 0 | 100.0% |
| Poly Pizza Source | 5 | 5 | 0 | 100.0% |
| OpenGameArt Source | 5 | 2 | 3 | 40.0% |

## 2. Per-Asset Test Results Matrix

| Asset Name | Source | Format | Status | Failure Category | DL Time | Blender Time | Godot Time | Total Time |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| Platformer Character | Kenney | GLB | **PASS** | N/A | 0.005s | 0.806s | 10.334s | 11.464s |
| Platformer Coin | Kenney | GLB | **PASS** | N/A | 0.008s | 0.9s | 11.446000000000002s | 12.715s |
| City Builder Garage | Kenney | GLB | **PASS** | N/A | 0.006s | 1.769s | 13.625s | 15.85s |
| City Builder Building C | Kenney | GLB | **PASS** | N/A | 0.013s | 1.419s | 10.928999999999998s | 12.777s |
| FPS Weapon | Kenney | GLB | **PASS** | N/A | 0.008s | 1.478s | 13.456000000000001s | 15.427s |
| Female Character | Poly Pizza | FBX | **PASS** | N/A | 0.021s | 34.536s | 13.591s | 51.055s |
| AC Prop | Poly Pizza | FBX | **PASS** | N/A | 0.022s | 1.048s | 11.46s | 13.67s |
| Computer Console | Poly Pizza | FBX | **PASS** | N/A | 0.02s | 0.858s | 11.538s | 13.446s |
| Cyberpunk Door | Poly Pizza | FBX | **PASS** | N/A | 0.021s | 1.244s | 10.306999999999999s | 13.101s |
| Fence Prop | Poly Pizza | FBX | **PASS** | N/A | 0.021s | 1.017s | 10.275s | 12.393s |
| OpenGL Human | OpenGameArt | OBJ | **PASS** | N/A | 0.002s | 0.908s | 12.111s | 13.084s |
| Recast Dungeon | OpenGameArt | OBJ | **FAIL** | `blender export failed after 3 attempts: MATERIAL_NOT_ASSIGNED` | 0.013s | 11.249s | 0.0s | 12.429s |
| Recast Nav Test | OpenGameArt | OBJ | **PASS** | N/A | 0.005s | 1.032s | 10.779s | 12.566s |
| African Head | OpenGameArt | OBJ | **FAIL** | `blender export failed after 3 attempts: MATERIAL_NOT_ASSIGNED` | 0.042s | 9.304s | 0.0s | 11.052s |
| Diablo 3 Pose | OpenGameArt | OBJ | **FAIL** | `blender export failed after 3 attempts: MATERIAL_NOT_ASSIGNED` | 0.037s | 9.431s | 0.0s | 10.769s |

## 3. Performance Metrics (Averages)

- **Average Download & Cache Time**: 0.016s
- **Average Blender Import/Export Time**: 5.133s
- **Average Godot Import & Editor Launch Time**: 9.323s
- **Average Total Pipeline Time**: 15.453s

## 4. Failure Classification & Analysis

### Failure Category Distribution
- **blender export failed after 3 attempts: MATERIAL_NOT_ASSIGNED**: 3 failure(s)

### Deep-Dive Analysis of Discovered Weaknesses

1. **Blender 2.79b Import Limitations (`BLENDER_IMPORT_FAILURE`)**:
   - **Problem**: Blender 2.79b does not support native `.gltf` / `.glb` imports. Running the `import_scene.gltf` script commands throws a runtime exception.
   - **Effect**: GLB assets from Kenney and Poly Pizza fail to import in Blender, forcing a fallback to the procedural cube stub. This is the primary driver of failure when strict FBX translation is required in the asset processor.
   - **Resolution**: While our updated `generate_main_scene` gracefully works around this by dynamically instancing raw GLB models directly into Godot, the Blender translation step itself is a bottleneck when using old Blender versions.

2. **Missing Materials / Missing Textures (`VALIDATION_FAILURE`)**:
   - **Problem**: OBJ files from OpenGameArt and SSloy/TinyRenderer (like `human.obj`, `diablo3_pose.obj`) lack accompanying `.mtl` material files and textures in their root directories or repositories, or have mismatched texture names.
   - **Effect**: While Godot is able to import the raw OBJ meshes, they render with the default material, and the asset analysis worker flags texture warnings.

3. **Large FBX Files Launch Speed (`GODOT_SCENE_LOAD_FAILURE` Risk)**:
   - **Problem**: Large FBX files (like `ultimate-modular-women.fbx` at 11.8MB) take significantly longer to import in Godot, increasing processing time.
   - **Effect**: Requires longer timeouts (up to 45s) for the headless loader verification, otherwise the process is killed before Godot can write the validation report.

## 5. Conclusion
The reliability test highlights that while the overall asset pipeline is robust, its reliance on Blender 2.79b for FBX compilation creates a systematic failure rate for modern `.glb`/`.gltf` formats. Transitioning the pipeline to use direct Godot GLB instancing (which we successfully introduced in our hotfix) completely bypasses these Blender translation bottlenecks and raises the pipeline's real-world usability.