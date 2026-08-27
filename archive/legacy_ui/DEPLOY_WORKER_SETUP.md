# Jarvis Core v1 - Deploy Worker Configuration Guide

## Overview
The Deploy Worker (OBJECTIVE 2) adds "Instant Play" capability to Jarvis Core v1. After the Godot Worker finishes assembling your scene, Jarvis automatically:

1. **Headless Build:** Triggers Godot to export the project as WebGL/HTML5
2. **FTP Deployment:** Uploads the exported files to your InfinityFree hosting
3. **Live URL:** Returns a playable web link (e.g., `http://my-infinityfree-domain.com/jarvis_builds/[job-id]/`)

---

## Step A: Configure FTP Credentials

Edit your `config/config.json` to add the deploy worker configuration:

```json
{
  "workers": {
    "internet": { ... },
    "analysis": { ... },
    "blender": { ... },
    "godot": { ... },
    "validation": { ... },
    "deploy": {
      "enabled": true,
      "binary": "godot",
      "ftp_host": "ftpupload.net",
      "ftp_user": "epiz_XXXXXXXX",
      "ftp_pass": "your_secure_ftp_password",
      "ftp_remote_dir": "/htdocs/jarvis_builds",
      "web_base_url": "http://your-infinityfree-domain.com"
    }
  }
}
```

### Getting InfinityFree Credentials

1. **Sign up at [InfinityFree.net](https://www.infinityfree.net/)**
2. **Activate FTP Account:**
   - Go to Account → FTP Accounts
   - Create a new FTP account (note: use existing directory `/htdocs` or create a subdirectory)
3. **Retrieve Credentials:**
   - `ftp_host`: Usually `ftpupload.net` (provided by InfinityFree)
   - `ftp_user`: Your FTP username (usually `epiz_XXXXXXXX`)
   - `ftp_pass`: Your FTP password
4. **Domain Configuration:**
   - `web_base_url`: Your InfinityFree domain (e.g., `http://myproject123.infinityfreeapp.com`)

---

## Step B: Godot Export Preset (Important!)

The Deploy Worker requires a Godot export preset named **"Web"** for HTML5 export.

### Using Godot Editor:

1. Open your Godot project
2. Go to **Project → Export**
3. Click **"Add Preset"** → Select **"Web"**
4. Configure settings:
   - **HTML5 Export Path:** `res://` (default)
   - **Fallback Page:** Leave default
   - **Vram Compression:** Enable for performance
5. **Save** the preset (Ctrl+S)

### Preset will be saved to:
```
godot_project/export_presets.cfg
```

The Deploy Worker reads this automatically when calling `godot --export-release "Web"`.

---

## Step C: Advanced Configuration Options

### Optional Parameters in config.json:

```json
"deploy": {
  "enabled": true,
  "binary": "C:\\path\\to\\godot.exe",  // Absolute path if not in PATH
  "ftp_host": "ftpupload.net",
  "ftp_user": "epiz_XXXXXXXX",
  "ftp_pass": "password",
  "ftp_remote_dir": "/htdocs/jarvis_builds",  // Public directory
  "web_base_url": "http://my-domain.com"
}
```

---

## Step D: Pipeline Integration

The Deploy Worker is automatically integrated into the pipeline. Order of execution:

```
1. asset_search (Internet Worker)
   ↓
2. asset_processing (Analysis Worker)
   ↓
3. blender_import (Blender Worker)
   ↓
4. godot_import (Godot Worker)
   ↓
5. output_validation (Validation Worker)
   ↓
6. cloud_deploy (Deploy Worker)  ← NEW!
```

When `jarvis.run("Create a medieval village")` completes, you'll get:

```python
result = JarvisResult(
    job_id="a1b2c3d4-...",
    status="success",
    godot_project="/path/to/godot_project/",
    deployment_url="http://my-infinityfree-domain.com/jarvis_builds/a1b2c3d4/",  ← PLAYABLE LINK!
    ...
)
```

---

## Step E: Troubleshooting

### Issue: "FTP_DEPLOYMENT_FAILED: Connection refused"

**Solution:**
- Verify `ftp_host`, `ftp_user`, `ftp_pass` are correct
- Check FireFire is not blocking port 21 (FTP)
- Use passive FTP mode (Deploy Worker defaults to this)

### Issue: "GODOT_EXPORT_FAILURE: index.html not created"

**Solution:**
- Ensure Godot binary is available (set `binary` in config)
- Verify WebGL preset exists in `export_presets.cfg`
- Check Godot version supports HTML5 export (4.0+)

### Issue: Files uploaded but web page 404

**Solution:**
- Verify `ftp_remote_dir` matches your public directory (usually `/htdocs`)
- Check file permissions on FTP server (644 for files)
- Ensure `web_base_url` matches your actual domain

### Issue: Upload times out after 15 minutes

**Solution:**
- Godot export may be taking too long
- Reduce texture resolution in Godot export preset
- Disable audio if not needed
- Increase Godot build timeout in `deploy_worker.py` (line ~100)

---

## Step F: Manual Verification

After Jarvis completes, manually verify the deployment:

```bash
# Check FTP upload
# Connect to ftpupload.net with your credentials
# Navigate to /htdocs/jarvis_builds/
# Verify [job-id] directory exists with index.html

# Test the live URL
curl http://my-infinityfree-domain.com/jarvis_builds/a1b2c3d4/index.html
# Should return HTML content
```

---

## Step G: Production Security Notes

⚠️ **DO NOT commit FTP passwords to versioning!**

### Recommended Setup:

1. **Environment Variables:**
   ```bash
   # .env file (don't commit!)
   JARVIS_FTP_USER=epiz_XXXXXXXX
   JARVIS_FTP_PASS=your_secure_password
   ```

2. **config.json (safe):**
   ```json
   "deploy": {
     "ftp_user": "${env:JARVIS_FTP_USER}",
     "ftp_pass": "${env:JARVIS_FTP_PASS}"
   }
   ```

3. **Load in Python:**
   ```python
   import os
   ftp_user = os.environ.get('JARVIS_FTP_USER')
   ftp_pass = os.environ.get('JARVIS_FTP_PASS')
   ```

---

## Architecture Summary

### Deploy Worker Flow:

```
run(job, state)
    ├─ Read Godot project path from state
    ├─ _build_html5_export()
    │  └─ Execute: godot --headless --path ./project --export-release "Web" ./output/index.html
    ├─ _upload_files_individually()
    │  ├─ Connect to FTP
    │  ├─ Create /htdocs/jarvis_builds/[job-id]/ directory
    │  └─ Upload all HTML/JS/WASM files
    └─ Return {"deployed": true, "url": "http://..."}
```

### Integration Points:

- **Pipeline:** Deploy runs as final stage after validation
- **JarvisCore:** Includes `deployment_url` in final result
- **Logging:** All operations logged to console and file

---

## API Usage

When using Jarvis through the API:

```python
from appsuite.core.jarvis import JarvisCore

result = jarvis.run("Create a cozy cottage in the woods")
# result.deployment_url = "http://my-domain.com/jarvis_builds/xyz123/"

print(f"Play your game: {result.deployment_url}")
```

The URL is automatically printed in logs at the END of execution:

```
[Jarvis] *** END job=a1b2c3d4 status=success duration=142.3s ***
[Jarvis] *** LIVE URL: http://my-infinityfree-domain.com/jarvis_builds/a1b2c3d4/ ***
```

---

## Next Steps

1. ✅ Edit config.json with your FTP credentials
2. ✅ Set up Godot WebGL export preset
3. ✅ Run: `python run_jarvis.py "Create a scene"`
4. ✅ Check logs for deployment URL
5. ✅ Visit URL in browser to play immediately!

---

## Support

For issues with:
- **InfinityFree:** Check [InfinityFree Docs](https://www.infinityfree.net/knowl/en/)
- **Godot Export:** See [Godot HTML5 Export Docs](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)
- **Blender Fallback Material Fix:** See [OBJECTIVE 1 Notes](#blender-fallback-material-fix)
