#!/usr/bin/env python3
import time
import logging
from typing import Any, Dict
from chroot_manager import ChrootManager

class PackageInstaller:
    def __init__(self, chroot: ChrootManager, config: Dict[str, Any], packages_config: Dict[str, Any], logger: logging.Logger):
        self.chroot = chroot
        self.config = config
        self.packages_config = packages_config
        self.logger = logger

    def configure_system(self) -> bool:
        self.logger.info("Configuring base system settings...")
        hostname = self.config["system"]["hostname"]
        username = self.config["system"]["username"]
        locale = self.config["system"]["locale"]
        tz = self.config["system"]["timezone"]
        
        commands = [
            f"echo '{hostname}' > /etc/hostname",
            f"echo '127.0.1.1 {hostname}' >> /etc/hosts",
            f"locale-gen {locale}",
            f"update-locale LANG={locale}",
            f"ln -fs /usr/share/zoneinfo/{tz} /etc/localtime",
            "dpkg-reconfigure -f noninteractive tzdata",
            f"if ! id -u {username} >/dev/null 2>&1; then useradd -m -s /bin/bash -G sudo,cdrom,dip,plugdev,render,video {username}; echo '{username}:appsuite' | chpasswd; fi",
            "mkdir -p /etc/gdm3",
            f"echo -e '[daemon]\\nWaylandEnable=false\\nAutomaticLoginEnable=true\\nAutomaticLogin={username}' > /etc/gdm3/custom.conf",
            "touch /opt/.appsuite_first_boot"
        ]
        
        for cmd in commands:
            if not self.chroot.run(cmd):
                return False
        return True

    def install_apt_packages(self) -> bool:
        self.logger.info("Updating APT and adding repositories...")
        
        # Divert snap command inside chroot to prevent apt hang on snap install firefox
        self.chroot.run("if [ -f /usr/bin/snap ] && [ ! -f /usr/bin/snap.real ]; then mv /usr/bin/snap /usr/bin/snap.real && ln -sf /bin/true /usr/bin/snap; fi")
        
        repos = self.packages_config.get("repositories", [])
        for repo in repos:
            if not self.chroot.run(f"add-apt-repository -y '{repo}'"):
                self.logger.warning(f"Failed to add repository {repo}")
                
        if not self.chroot.run("apt-get update"):
            return False
            
        packages = self.packages_config.get("packages", [])
        pkg_str = " ".join(packages)
        self.logger.info(f"Installing packages: {pkg_str}")
        
        # Retry mechanism for robust installation
        max_retries = 3
        success = False
        for attempt in range(1, max_retries + 1):
            if self.chroot.run(f"apt-get install -y {pkg_str}"):
                success = True
                break
            self.logger.warning(f"Apt install failed. Retrying ({attempt}/{max_retries})...")
            time.sleep(5)
            self.chroot.run("dpkg --configure -a")
            self.chroot.run("apt-get --fix-broken install -y")
            
        if not success:
            self.logger.error("Failed to install packages after multiple retries.")
            return False
            
        return True

    def install_custom(self) -> bool:
        self.logger.info("Executing custom installation scripts...")
        custom_scripts = self.packages_config.get("custom_installs", [])
        for script in custom_scripts:
            if not self.chroot.run(script):
                self.logger.warning(f"Custom install script failed: {script}")
        return True

    def create_appsuite_integration(self) -> bool:
        self.logger.info("Setting up /opt/AppSuite integration...")
        commands = [
            "mkdir -p /opt/AppSuite/bin",
            "mkdir -p /opt/AppSuite/logs",
            "echo '#!/bin/bash\\necho \"Starting AppSuite...\"' > /opt/AppSuite/bin/appsuite",
            "chmod +x /opt/AppSuite/bin/appsuite",
            "ln -sf /opt/AppSuite/bin/appsuite /usr/local/bin/appsuite"
        ]
        
        # Dummy desktop file
        desktop_entry = (
            "[Desktop Entry]\\n"
            "Name=AppSuite\\n"
            "Comment=Autonomous AI Software Engineering\\n"
            "Exec=/usr/local/bin/appsuite\\n"
            "Icon=appsuite\\n"
            "Terminal=true\\n"
            "Type=Application\\n"
            "Categories=Development;"
        )
        commands.append(f"mkdir -p /usr/share/applications && echo -e '{desktop_entry}' > /usr/share/applications/appsuite.desktop")
        
        for cmd in commands:
            if not self.chroot.run(cmd):
                return False
        return True

    def cleanup(self) -> bool:
        self.logger.info("Cleaning up filesystem before packaging...")
        commands = [
            "apt-get autoremove -y",
            "apt-get clean",
            "rm -rf /var/lib/apt/lists/*",
            "rm -rf /tmp/*",
            "rm -rf /var/tmp/*",
            "rm -rf /var/log/*",
            "rm -f /etc/machine-id",
            "touch /etc/machine-id",
            "if [ -f /usr/bin/snap.real ]; then rm -f /usr/bin/snap && mv /usr/bin/snap.real /usr/bin/snap; fi",
            "update-initramfs -u -k all"
        ]
        for cmd in commands:
            self.chroot.run(cmd) # We ignore minor cleanup failures
        return True
