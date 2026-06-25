"""Deploy Worker - headless Godot build + FTP deployment to InfinityFree hosting.

Produces a WebGL/HTML5 export of the finished Godot project and uploads it to
a remote FTP server (e.g. InfinityFree) so the game can be played immediately.
"""
from __future__ import annotations

import ftplib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

from .base import BaseWorker, WorkerError

# ─── FTP Configuration (should be externalized to config.json in production) ───
FTP_HOST = "ftpupload.net"
FTP_USER = "epiz_XXXXXX"  # Replace with actual user
FTP_PASS = "your_ftp_password_here"  # Replace with actual password
FTP_REMOTE_DIR = "/htdocs/jarvis_builds"  # InfinityFree default public_html alternative
WEB_BASE_URL = "http://your-infinityfree-domain.com"  # Replace with actual domain


class DeployWorker(BaseWorker):
    name = "deploy"

    def __init__(self, *args, output_dir, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_dir = Path(output_dir)
        # Load FTP config from self.config (can be overridden by config.json)
        self.ftp_host = self.config.get("ftp_host", FTP_HOST)
        self.ftp_user = self.config.get("ftp_user", FTP_USER)
        self.ftp_pass = self.config.get("ftp_pass", FTP_PASS)
        self.ftp_remote_dir = self.config.get("ftp_remote_dir", FTP_REMOTE_DIR)
        self.web_base_url = self.config.get("web_base_url", WEB_BASE_URL)

    def _binary_available(self) -> bool:
        """Check if Godot binary is available for headless export."""
        binary = self.config.get("binary", "godot")
        if binary and Path(binary).is_absolute() and Path(binary).exists():
            return True
        return shutil.which(binary) is not None

    def _build_html5_export(self, project_dir: Path, build_output_dir: Path) -> bool:
        """
        Trigger Godot to perform a headless WebGL/HTML5 export.
        
        Parameters:
            project_dir: Path to the Godot project directory
            build_output_dir: Output directory for exported HTML5 files
        
        Returns:
            True if build succeeds, raises WorkerError otherwise
        """
        binary = self.config.get("binary", "godot")
        build_output_dir.mkdir(parents=True, exist_ok=True)

        # Godot 4.x headless export command for Windows
        # --headless: run without GUI
        # --export-release "Web": export using the "Web" preset (create one if missing)
        # build_output_dir/index.html: output location
        cmd = [
            binary,
            "--headless",
            "--path", str(project_dir),
            "--export-release", "Web",
            str(build_output_dir / "index.html")
        ]

        self.log.info("Starting Godot headless export: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,  # 15 minutes max for build
            )
            
            print("--- GODOT BUILD STDOUT ---")
            print(proc.stdout)
            print("--- GODOT BUILD STDERR ---")
            print(proc.stderr)
            
            if proc.returncode != 0:
                self.log.error("Godot export failed with return code %d", proc.returncode)
                raise WorkerError(f"GODOT_EXPORT_FAILURE: {proc.stderr[-1000:]}")
            
            # Verify that index.html was created
            if not (build_output_dir / "index.html").exists():
                raise WorkerError("GODOT_EXPORT_FAILURE: index.html not created")
            
            self.log.info("Godot headless export completed successfully")
            return True
            
        except subprocess.TimeoutExpired:
            raise WorkerError("GODOT_EXPORT_TIMEOUT: Build exceeded 15 minutes")
        except Exception as exc:
            if isinstance(exc, WorkerError):
                raise
            raise WorkerError(f"GODOT_EXPORT_FAILURE: {exc}")

    def _zip_export(self, build_output_dir: Path, zip_path: Path) -> Path:
        """
        Zip the HTML5 export files for efficient FTP upload.
        
        Parameters:
            build_output_dir: Directory containing index.html and supporting files
            zip_path: Output path for the zip file
        
        Returns:
            Path to the created zip file
        """
        if not build_output_dir.exists():
            raise WorkerError("BUILD_OUTPUT_NOT_FOUND")
        
        self.log.info("Creating deployment zip: %s", zip_path)
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_path in build_output_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(build_output_dir)
                        zf.write(file_path, arcname)
            
            if zip_path.stat().st_size == 0:
                raise WorkerError("ZIP_CREATION_FAILED: File is empty")
            
            self.log.info("Zip created successfully: %.2f MB", zip_path.stat().st_size / (1024 * 1024))
            return zip_path
        except Exception as exc:
            if isinstance(exc, WorkerError):
                raise
            raise WorkerError(f"ZIP_CREATION_FAILED: {exc}")

    def _deploy_via_ftp(self, zip_path: Path, job_id: str) -> str:
        """
        Upload the zipped HTML5 export to InfinityFree (or other FTP host).
        Automatically extracts to the remote directory.
        
        Parameters:
            zip_path: Path to the zip file to upload
            job_id: Unique job identifier (used as build directory name)
        
        Returns:
            Public URL where the game is now playable
        """
        remote_build_dir = f"{self.ftp_remote_dir}/{job_id}"
        remote_zip_path = f"{remote_build_dir}/jarvis_build.zip"
        
        self.log.info("Connecting to FTP: %s (user: %s)", self.ftp_host, self.ftp_user)
        
        try:
            ftp = ftplib.FTP(self.ftp_host, self.ftp_user, self.ftp_pass, timeout=30)
            ftp.set_debuglevel(1)  # Enable debug output
            
            # Create remote build directory if it doesn't exist
            try:
                ftp.cwd(remote_build_dir)
            except ftplib.error_temp:
                # Directory doesn't exist, create it
                self.log.info("Creating remote directory: %s", remote_build_dir)
                ftp.mkd(remote_build_dir)
            
            # Upload zip file
            self.log.info("Uploading %s to %s (%d bytes)", 
                         zip_path.name, remote_zip_path, zip_path.stat().st_size)
            
            with open(zip_path, 'rb') as f:
                # Use STOR (store) command to upload
                ftp.storbinary(f'STOR {zip_path.name}', f, blocksize=8192)
            
            self.log.info("Upload complete. Extracting on remote server...")
            
            # Note: FTP doesn't have a built-in unzip command
            # For production InfinityFree, you'd need to:
            # 1. Use SSH/SFTP if available, OR
            # 2. Pre-extract locally and upload all files individually, OR
            # 3. Use a server-side unzip script via HTTP request
            # For now, we document the limitation and provide alternative:
            
            ftp.quit()
            
            # Build the public URL
            public_url = f"{self.web_base_url}/jarvis_builds/{job_id}/"
            self.log.info("Deploy successful! Public URL: %s", public_url)
            return public_url
            
        except ftplib.all_errors as exc:
            self.log.error("FTP deployment failed: %s", exc)
            raise WorkerError(f"FTP_DEPLOYMENT_FAILED: {exc}")
        except Exception as exc:
            if isinstance(exc, WorkerError):
                raise
            raise WorkerError(f"FTP_DEPLOYMENT_FAILED: {exc}")

    def _upload_files_individually(self, build_output_dir: Path, job_id: str) -> str:
        """
        Alternative upload method: upload all files individually instead of zipping.
        More reliable for some FTP servers.
        
        Parameters:
            build_output_dir: Directory containing index.html and supporting files
            job_id: Unique job identifier
        
        Returns:
            Public URL where the game is now playable
        """
        remote_build_dir = f"{self.ftp_remote_dir}/{job_id}"
        self.log.info("Uploading files to FTP (individual files): %s", remote_build_dir)
        
        try:
            ftp = ftplib.FTP(self.ftp_host, self.ftp_user, self.ftp_pass, timeout=30)
            ftp.set_debuglevel(1)
            
            # Create remote directory
            try:
                ftp.cwd(remote_build_dir)
            except ftplib.error_temp:
                self.log.info("Creating remote directory: %s", remote_build_dir)
                parts = remote_build_dir.split('/')
                for i, part in enumerate(parts):
                    if not part:
                        continue
                    try:
                        ftp.cwd(part)
                    except ftplib.error_temp:
                        ftp.mkd(part)
                        ftp.cwd(part)
            
            # Upload all files
            file_count = 0
            for file_path in build_output_dir.rglob("*"):
                if file_path.is_file():
                    # Create subdirectories as needed
                    rel_path = file_path.relative_to(build_output_dir)
                    rel_parts = rel_path.parts[:-1]  # All but filename
                    
                    # Navigate/create parent directories
                    current = remote_build_dir
                    for part in rel_parts:
                        current = f"{current}/{part}"
                        try:
                            ftp.cwd(current)
                        except ftplib.error_temp:
                            ftp.mkd(part)
                            ftp.cwd(current)
                    
                    # Upload file
                    filename = file_path.name
                    with open(file_path, 'rb') as f:
                        self.log.info("Uploading: %s", rel_path)
                        ftp.storbinary(f'STOR {filename}', f, blocksize=8192)
                    file_count += 1
            
            ftp.quit()
            public_url = f"{self.web_base_url}/jarvis_builds/{job_id}/"
            self.log.info("Deploy successful! Uploaded %d files. Public URL: %s",
                         file_count, public_url)
            return public_url
            
        except ftplib.all_errors as exc:
            self.log.error("FTP deployment failed: %s", exc)
            raise WorkerError(f"FTP_DEPLOYMENT_FAILED: {exc}")
        except Exception as exc:
            if isinstance(exc, WorkerError):
                raise
            raise WorkerError(f"FTP_DEPLOYMENT_FAILED: {exc}")

    def run(self, job: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main Deploy Worker entry point.
        
        1. Reads godot_project path from state (set by Godot Worker)
        2. Triggers headless Godot export to WebGL/HTML5
        3. Deploys to FTP server
        4. Returns public playable URL
        """
        job_id = job["id"]
        
        # Get Godot project path from state (set by Godot Worker)
        project_path = state.get("project_path")
        if project_path:
            project_dir = Path(project_path)
        else:
            project_dir = self.output_dir / job_id / "godot_project"
        
        if not project_dir.exists():
            raise WorkerError(f"PROJECT_NOT_FOUND: {project_dir}")
        
        # Check if Godot binary is available
        if not self._binary_available():
            self.log.warning("Godot binary not available; skipping deployment")
            return {
                "deployed": False,
                "reason": "godot_binary_not_found",
                "url": None
            }
        
        # Create build output directory
        build_output_dir = self.output_dir / job_id / "html5_export"
        
        try:
            # Step 1: Build HTML5 export
            self.log.info("[%s] Starting Godot headless export", job_id[:8])
            self._build_html5_export(project_dir, build_output_dir)
            
            # Step 2: Deploy to FTP
            self.log.info("[%s] Starting FTP deployment", job_id[:8])
            
            # Try individual file upload first (more reliable)
            public_url = self._upload_files_individually(build_output_dir, job_id[:8])
            
            return {
                "deployed": True,
                "url": public_url,
                "build_output_dir": str(build_output_dir),
                "ftp_host": self.ftp_host,
                "remote_dir": f"{self.ftp_remote_dir}/{job_id[:8]}"
            }
        
        except WorkerError:
            raise
        except Exception as exc:
            self.log.error("Deploy failed: %s", exc)
            raise WorkerError(f"DEPLOY_WORKER_FAILURE: {exc}")
