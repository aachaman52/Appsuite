import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from squashfs_discovery import discover_squashfs


@pytest.fixture
def casper(tmp_path):
    d = tmp_path / "iso_extracted" / "casper"
    d.mkdir(parents=True)
    return tmp_path / "iso_extracted"


# ── Layout: Ubuntu 20.04 / 22.04 Desktop ──────────────────────────────────────
def test_desktop_iso_layout(casper):
    (casper / "casper" / "filesystem.squashfs").touch()
    result = discover_squashfs(casper)
    assert result.name == "filesystem.squashfs"


# ── Layout: Ubuntu 24.04.4 Server (the failing real-world case) ───────────────
def test_server_24_04_4_layout(casper):
    c = casper / "casper"
    (c / "ubuntu-server-minimal.squashfs").touch()
    (c / "ubuntu-server-minimal.ubuntu-server.squashfs").touch()
    (c / "ubuntu-server-minimal.ubuntu-server.installer.squashfs").touch()
    (c / "ubuntu-server-minimal.ubuntu-server.installer.generic.squashfs").touch()
    (c / "ubuntu-server-minimal.ubuntu-server.installer.generic-hwe.squashfs").touch()

    result = discover_squashfs(casper)
    # The *.ubuntu-server.squashfs gets score 10 — highest priority
    assert result.name == "ubuntu-server-minimal.ubuntu-server.squashfs"


# ── Layout: Only server-minimal, no ubuntu-server variant ─────────────────────
def test_server_minimal_only(casper):
    c = casper / "casper"
    (c / "ubuntu-server-minimal.squashfs").touch()
    (c / "ubuntu-server-minimal.ubuntu-server.installer.squashfs").touch()

    result = discover_squashfs(casper)
    assert result.name == "ubuntu-server-minimal.squashfs"


# ── Layout: Server + Desktop coexist, server should win ───────────────────────
def test_server_wins_over_desktop(casper):
    c = casper / "casper"
    (c / "filesystem.squashfs").touch()
    (c / "ubuntu-server-minimal.ubuntu-server.squashfs").touch()

    result = discover_squashfs(casper)
    assert result.name == "ubuntu-server-minimal.ubuntu-server.squashfs"


# ── Layout: Unknown future naming, non-installer wins ─────────────────────────
def test_unknown_future_layout(casper):
    c = casper / "casper"
    (c / "ubuntu-future-base.squashfs").touch()
    (c / "ubuntu-future-base.installer.squashfs").touch()

    result = discover_squashfs(casper)
    assert result.name == "ubuntu-future-base.squashfs"


# ── Layout: Installer-only — last resort fallback ─────────────────────────────
def test_installer_only_last_resort(casper):
    c = casper / "casper"
    (c / "ubuntu-server-minimal.ubuntu-server.installer.squashfs").touch()

    # Should NOT raise — it falls back to installer with a warning
    result = discover_squashfs(casper)
    assert "installer" in result.name


# ── Layout: Completely missing squashfs ───────────────────────────────────────
def test_missing_squashfs_raises(casper):
    # No squashfs files at all
    with pytest.raises(RuntimeError, match="No \\*.squashfs files found"):
        discover_squashfs(casper)


# ── Layout: install/ directory fallback (older ISOs) ─────────────────────────
def test_install_directory_fallback(tmp_path):
    extract_dir = tmp_path / "iso_extracted"
    install_dir = extract_dir / "install"
    install_dir.mkdir(parents=True)
    (install_dir / "filesystem.squashfs").touch()

    result = discover_squashfs(extract_dir)
    assert result.name == "filesystem.squashfs"
