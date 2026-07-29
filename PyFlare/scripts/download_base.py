#!/usr/bin/env python3
import os
import sys
import hashlib
import urllib.request
import urllib.error
import yaml
import re
from pathlib import Path

def load_config():
    config_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def sha256sum(filename):
    h = hashlib.sha256()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        while n := f.readinto(mv):
            h.update(mv[:n])
    return h.hexdigest()

def scrape_iso_info(mirror_base: str, major_version: str, flavor: str, logger=None):
    """
    Scrapes the SHA256SUMS file to find the latest ISO matching the major version and flavor.
    Returns (iso_url, iso_filename, expected_sha256) or None on failure.
    """
    url = f"{mirror_base.rstrip('/')}/{major_version}/SHA256SUMS"
    if logger: logger.info(f"Fetching {url}")
    
    try:
        req = urllib.request.urlopen(url, timeout=10)
        lines = req.read().decode('utf-8').splitlines()
    except Exception as e:
        if logger: logger.warning(f"Failed to fetch {url}: {e}")
        return None

    # Looking for a line like:
    # 8762f7e74e4d64d72fceb5f70682e6b069932deedb4949c6975d0f0fe0a91be3 *ubuntu-24.04.1-live-server-amd64.iso
    # or ubuntu-24.04-live-server-amd64.iso
    
    pattern = re.compile(rf"([a-fA-F0-9]{{64}})\s+\*?(ubuntu-{major_version}(?:\.\d+)?-{flavor}\.iso)")
    
    best_match = None
    best_version_tuple = (-1,)
    
    for line in lines:
        match = pattern.search(line)
        if match:
            sha, filename = match.groups()
            
            # Extract point release if any (e.g., .1 from 24.04.1)
            # Find the string between major_version and -flavor
            v_str = filename[len(f"ubuntu-{major_version}") : -len(f"-{flavor}.iso")]
            if v_str.startswith("."):
                try:
                    point = int(v_str[1:])
                except ValueError:
                    point = 0
            else:
                point = 0
                
            if point > best_version_tuple[0]:
                best_version_tuple = (point,)
                iso_url = f"{mirror_base.rstrip('/')}/{major_version}/{filename}"
                best_match = (iso_url, filename, sha)
                
    return best_match

def download_base(logger=None):
    def log(msg):
        print(msg)
        if logger: logger.info(msg)
        
    config = load_config()
    os_cfg = config["os"]
    major_version = str(os_cfg["ubuntu_major_version"])
    flavor = os_cfg["iso_flavor"]
    mirrors = os_cfg.get("fallback_mirrors", ["https://releases.ubuntu.com"])
    
    log(f"Searching for the latest Ubuntu {major_version} {flavor} ISO...")
    
    iso_info = None
    for mirror in mirrors:
        iso_info = scrape_iso_info(mirror, major_version, flavor, logger)
        if iso_info:
            break
            
    if not iso_info:
        log("[ERROR] Could not find a matching ISO on any mirror!")
        sys.exit(1)
        
    iso_url, filename, expected_hash = iso_info
    log(f"[OK] Found newest ISO: {filename}")
    
    work_dir = Path(__file__).resolve().parent.parent / config["build"]["work_folder"]
    work_dir.mkdir(parents=True, exist_ok=True)
    filepath = work_dir / filename
    
    if filepath.exists():
        log(f"ISO already exists at {filepath}. Verifying checksum...")
        current_hash = sha256sum(filepath)
        if current_hash == expected_hash:
            log("[OK] Checksum matches. Skipping download.")
            return filepath
        else:
            log("[WARNING] Checksum mismatch. Redownloading...")
            filepath.unlink()
            
    log(f"Downloading {iso_url}...")
    def reporthook(count, block_size, total_size):
        if total_size > 0:
            percent = int(count * block_size * 100 / total_size)
            sys.stdout.write(f"\r...{percent}%")
            sys.stdout.flush()
            
    try:
        urllib.request.urlretrieve(iso_url, filepath, reporthook)
        print()
    except Exception as e:
        log(f"\n[ERROR] Download failed: {e}")
        sys.exit(1)
    
    log("Verifying downloaded ISO checksum...")
    current_hash = sha256sum(filepath)
    if current_hash != expected_hash:
        log(f"[ERROR] SHA256 mismatch! Expected {expected_hash}, got {current_hash}")
        sys.exit(1)
        
    log("[OK] ISO downloaded and verified successfully.")
    return filepath

if __name__ == "__main__":
    download_base()
