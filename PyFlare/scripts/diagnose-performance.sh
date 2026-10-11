#!/usr/bin/env bash
# ==============================================================================
# PyFlare OS — Performance Diagnostics & System Health Script
# ==============================================================================
# Safely inspects system performance, resource utilization, boot bottlenecks,
# display/graphics subsystem, and PyFlare background services.
#
# Usage:
#   bash PyFlare/scripts/diagnose-performance.sh [--output report.txt] [--json]
#
# Requirements:
#   Read-only operations only. Safe to run on live systems without side effects.
# ==============================================================================

set -u

OUTPUT_FILE=""
JSON_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output|-o)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --json)
            JSON_MODE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--output <file>] [--json]"
            echo "Collects read-only system and PyFlare diagnostic metrics."
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Redaction helper to ensure no tokens or secrets leak
sanitize() {
    sed -E 's/(token|secret|password|api[_-]?key)=[^ &]+/ \1=[REDACTED]/gI'
}

run_diag() {
    echo "=============================================================================="
    echo "PyFlare OS — Performance Diagnostic Report"
    echo "Timestamp : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "Hostname  : $(hostname 2>/dev/null || echo 'unknown')"
    echo "=============================================================================="
    echo ""

    # 1. OS & Desktop Session
    echo "--- [1] OS & Desktop Environment ---"
    if [[ -f /etc/os-release ]]; then
        grep -E '^(PRETTY_NAME|VERSION_ID|ID)=' /etc/os-release
    else
        echo "OS: $(uname -s -r -v)"
    fi
    echo "Kernel: $(uname -r)"
    echo "Architecture: $(uname -m)"
    echo "Desktop Session: ${XDG_CURRENT_DESKTOP:-unknown} (${XDG_SESSION_TYPE:-unknown})"
    echo "Display Manager: $(systemctl is-active display-manager.service 2>/dev/null || echo 'N/A')"
    echo ""

    # 2. CPU Profile
    echo "--- [2] CPU Configuration ---"
    if command -v lscpu &>/dev/null; then
        lscpu | grep -E '^(Model name|Socket|Core|Thread|CPU\(s\)|CPU max MHz|Virtualization):' || true
    elif [[ -f /proc/cpuinfo ]]; then
        echo "Processors: $(grep -c '^processor' /proc/cpuinfo)"
        echo "Model: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)"
    fi
    echo "Load Average: $(cat /proc/loadavg 2>/dev/null || uptime 2>/dev/null || echo 'N/A')"
    echo ""

    # 3. Memory & Swap
    echo "--- [3] Memory, Swap & Pressure ---"
    if command -v free &>/dev/null; then
        free -h
    elif [[ -f /proc/meminfo ]]; then
        grep -E '^(MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo
    fi
    if [[ -f /proc/pressure/memory ]]; then
        echo "Memory Pressure (PSI):"
        cat /proc/pressure/memory
    fi
    if [[ -f /proc/pressure/cpu ]]; then
        echo "CPU Pressure (PSI):"
        cat /proc/pressure/cpu
    fi
    if [[ -f /proc/pressure/io ]]; then
        echo "I/O Pressure (PSI):"
        cat /proc/pressure/io
    fi
    echo ""

    # 4. Storage & Filesystem
    echo "--- [4] Storage Utilization ---"
    df -h -x tmpfs -x devtmpfs -x squashfs 2>/dev/null || df -h
    echo ""

    # 5. Display, Graphics & Hypervisor Integration
    echo "--- [5] Graphics Subsystem & Hypervisor ---"
    if command -v lspci &>/dev/null; then
        echo "VGA/Display Controllers:"
        lspci | grep -iE 'vga|3d|display' || echo "None found via lspci"
    fi
    if command -v glxinfo &>/dev/null; then
        echo "OpenGL Renderer: $(glxinfo -B 2>/dev/null | grep -E '(OpenGL renderer string|OpenGL version string)' || echo 'N/A')"
    fi
    if command -v systemd-detect-virt &>/dev/null; then
        echo "Virtualization Detected: $(systemd-detect-virt || echo 'none')"
    fi
    if command -v VBoxControl &>/dev/null; then
        echo "VirtualBox Guest Additions: Installed ($(VBoxControl -v 2>/dev/null || echo 'unknown'))"
    else
        echo "VirtualBox Guest Additions: NOT detected in guest"
    fi
    echo ""

    # 6. Systemd Boot Analysis
    echo "--- [6] Boot Time Analysis ---"
    if command -v systemd-analyze &>/dev/null; then
        echo "Startup Timeline:"
        systemd-analyze time 2>/dev/null || echo "systemd-analyze time unavailable"
        echo ""
        echo "Top 10 Slowest Services (blame):"
        systemd-analyze blame 2>/dev/null | head -n 10 || echo "systemd-analyze blame unavailable"
        echo ""
        echo "Critical Chain:"
        systemd-analyze critical-chain 2>/dev/null | head -n 15 || echo "systemd-analyze critical-chain unavailable"
    else
        echo "systemd-analyze not available in this environment."
    fi
    echo ""

    # 7. Failed Units & System Warnings
    echo "--- [7] Failed Units & Warnings ---"
    if command -v systemctl &>/dev/null; then
        echo "System Units in Failed State:"
        systemctl --failed --no-legend 2>/dev/null || echo "None"
        echo ""
        echo "User Units in Failed State:"
        systemctl --user --failed --no-legend 2>/dev/null || echo "None"
    fi
    echo ""

    # 8. PyFlare Services & Autostart
    echo "--- [8] PyFlare Background Services & Autostart ---"
    for svc in pyflare-engine.service pyflare-firstrun.service pyflare-update.service pyflare-update.timer; do
        if command -v systemctl &>/dev/null; then
            STATUS=$(systemctl is-active "$svc" 2>/dev/null || echo "inactive")
            ENABLED=$(systemctl is-enabled "$svc" 2>/dev/null || echo "disabled")
            echo "  $svc: status=$STATUS, enabled=$ENABLED"
        fi
    done

    echo "Autostart Entries in /etc/xdg/autostart/:"
    if [[ -d /etc/xdg/autostart ]]; then
        ls -1 /etc/xdg/autostart/pyflare* 2>/dev/null || echo "  (none)"
    fi

    echo "GNOME Enabled Shell Extensions:"
    if command -v gsettings &>/dev/null; then
        gsettings get org.gnome.shell enabled-extensions 2>/dev/null || echo "  (gsettings unavailable)"
    fi
    echo ""

    # 9. Top Resource-Consuming Processes
    echo "--- [9] Top Resource Consuming Processes ---"
    if command -v ps &>/dev/null; then
        echo "Top 5 by CPU:"
        ps -eo pid,user,%cpu,%mem,comm --sort=-%cpu | head -n 6
        echo ""
        echo "Top 5 by RAM:"
        ps -eo pid,user,%cpu,%mem,rss,comm --sort=-rss | head -n 6
    fi
    echo ""

    # 10. PyFlare Log Tail
    echo "--- [10] PyFlare System Logs ---"
    if [[ -f /var/lib/pyflare/firstrun.log ]]; then
        echo "Tail of /var/lib/pyflare/firstrun.log:"
        tail -n 15 /var/lib/pyflare/firstrun.log | sanitize
    else
        echo "No /var/lib/pyflare/firstrun.log present."
    fi
    echo "=============================================================================="
}

if [[ -n "$OUTPUT_FILE" ]]; then
    run_diag | tee "$OUTPUT_FILE"
    echo "Diagnostic report saved to: $OUTPUT_FILE"
else
    run_diag
fi
