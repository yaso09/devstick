#!/usr/bin/env python3
from pyproot.pyproot import start_sandbox
import os
import sys
import platform
import shutil
import subprocess
import urllib.request
import json
from pathlib import Path
from is_termux import is_termux
from run_proot_distro import run_distro_temp

# ----------------------------
# PATHS
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent
ROOTFS_DIR = BASE_DIR / "rootfs"
PROOT_DIR = BASE_DIR / "proot"

DEBIAN = ROOTFS_DIR / "debian"
UBUNTU = ROOTFS_DIR / "ubuntu"

GITHUB_API = "https://api.github.com/repos/yaso09/devstick/releases/latest"


# ----------------------------
# SYSTEM INFO
# ----------------------------
def arch():
    return platform.machine()


# ----------------------------
# SAFE SHELL RESOLVER (CRITICAL FIX)
# ----------------------------
def resolve_shell(rootfs: Path):
    """
    NEVER allow /usr/bin/bash (PRoot-safe rule)
    """
    if (rootfs / "bin/bash").exists():
        return "/bin/bash"
    if (rootfs / "bin/sh").exists():
        return "/bin/sh"

    print("[!] No valid shell found in rootfs")
    sys.exit(1)


# ----------------------------
# PROOT BINARY
# ----------------------------
def proot_binary():
    a = arch()

    if a == "aarch64":
        p = PROOT_DIR / "arm64" / "proot"
    elif a == "x86_64":
        p = PROOT_DIR / "x86_64" / "proot"
    else:
        print(f"[!] Unsupported arch: {a}")
        sys.exit(1)

    return str(p) if p.exists() else "proot"


def proot_distro_binary():
    p = PROOT_DIR / "proot-distro"
    return str(p) if p.exists() else "proot-distro"

# ----------------------------
# ENV SANITIZER (IMPORTANT)
# ----------------------------


def sanitize_env():
    os.environ.pop("SHELL", None)
    os.environ["SHELL"] = "/bin/bash"


# ----------------------------
# RUN DISTRO
# ----------------------------
def run_distro(name):
    rootfs = None

    if name == "debian":
        rootfs = DEBIAN
    elif name == "ubuntu":
        rootfs = UBUNTU
    else:
        print("Usage: devstick run [debian|ubuntu]")
        sys.exit(1)

    if not rootfs.exists():
        print("[!] Rootfs not found. Run: devstick install")
        sys.exit(1)

    sanitize_env()

    shell = resolve_shell(rootfs)
    proot = proot_distro_binary()

    print(f"[*] Arch: {arch()}")
    print(f"[*] Distro: {name}")
    print(f"[*] Shell: {shell}")
    print("[*] Starting Devstick...\n")

    cmd = [
        proot,
        "-0",
        "-r", str(rootfs),

        "-b", "/dev",
        "-b", "/proc",
        "-b", "/sys",

        "-w", "/root",

        shell
    ]

    # os.execvp(cmd[0], cmd)

    if is_termux():
        run_distro_temp(name, rootfs)
    else:
        start_sandbox(
            rootfs=str(rootfs),
            cmd=[shell]
        )


# ----------------------------
# PACKAGE MANAGER DETECTION
# ----------------------------
def detect_pkg_manager():
    managers = ["apt", "dnf", "apk", "pacman", "pkg"]

    for m in managers:
        if subprocess.run(["which", m], stdout=subprocess.DEVNULL).returncode == 0:
            return m

    return None


# ----------------------------
# INSTALL DEPENDENCIES
# ----------------------------
def install_proot_distro():
    print("[*] Installing proot-distro for Termux")

    PROOT_DISTRO_DIR = BASE_DIR / "proot-distro"

    if PROOT_DISTRO_DIR.exists():
        shutil.rmtree(PROOT_DISTRO_DIR)

    subprocess.run([
        "git",
        "clone",
        "https://github.com/termux/proot-distro.git"
    ])

    for item in PROOT_DISTRO_DIR.iterdir():
        if item.name == "proot_distro":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    d = PROOT_DISTRO_DIR / "proot_distro"

    for item in d.iterdir():
        target = PROOT_DISTRO_DIR / item.name
        shutil.move(str(item), str(target))

    shutil.rmtree(d)
    os.rename(PROOT_DISTRO_DIR, "proot_distro")


def install_dependencies():
    pm = detect_pkg_manager()

    print(f"[*] Package manager: {pm}")

    if not pm:
        print("[!] No package manager found")
        sys.exit(1)

    if pm == "pkg":
        subprocess.run(["pkg", "install", "-y", "debootstrap", "proot"])
    elif pm == "apt":
        subprocess.run(["sudo", "apt", "install",
                       "-y", "debootstrap", "proot"])
    elif pm == "dnf":
        subprocess.run(["sudo", "dnf", "install",
                       "-y", "debootstrap", "proot"])
    elif pm == "pacman":
        subprocess.run(
            ["sudo", "pacman", "-S", "--noconfirm", "debootstrap", "proot"])
    elif pm == "apk":
        subprocess.run(["sudo", "apk", "add", "debootstrap", "proot"])


def install_debian():
    if DEBIAN.exists():
        subprocess.run(["rm", "-rf", str(DEBIAN)])
    print("[*] Installing Debian...")
    cmd = [
        "debootstrap",
        "--variant=minbase",
        "stable",
        str(DEBIAN),
        "http://deb.debian.org/debian"
    ]

    if not is_termux():
        cmd.insert(0, "sudo")

    subprocess.run(cmd)


def install_ubuntu():
    if UBUNTU.exists():
        subprocess.run(["rm", "-rf", str(UBUNTU)])
    print("[*] Installing Ubuntu...")
    cmd = [
        "debootstrap",
        "--variant=minbase",
        "jammy",
        str(UBUNTU),
        "http://archive.ubuntu.com/ubuntu"
    ]

    if not is_termux():
        cmd.insert(0, "sudo")

    subprocess.run(cmd)

# ----------------------------
# DEBOOTSTRAP INSTALL
# ----------------------------


def install_rootfs():
    ROOTFS_DIR.mkdir(exist_ok=True)

    install_debian()
    install_ubuntu()

    print("[u2713] Install complete")


def install():
    if is_termux():
        install_proot_distro()
    install_dependencies()
    install_rootfs()

# ----------------------------
# REMOVE ROOTFS
# ----------------------------


def remove(name):
    rootfs = None
    if name == "debian":
        rootfs = DEBIAN
    elif name == "ubuntu":
        rootfs = UBUNTU
    else:
        print(f"[!] OS not found.")
        sys.exit(1)
    if rootfs.exists():
        subprocess.run(["rm", "-rf", str(rootfs)])
        print(f"[u2713] Removed {name}")
    else:
        print("[!] Rootfs not found.")
        sys.exit(1)

# ----------------------------
# UPDATE CHECK (GITHUB RELEASES)
# ----------------------------


def get_latest_release():
    try:
        data = json.loads(urllib.request.urlopen(GITHUB_API).read().decode())
        return data["tag_name"]
    except Exception as e:
        print("[!] Update check failed:", e)
        return None


def update():
    print("[*] Checking updates...")

    latest = get_latest_release()
    if not latest:
        return

    version_file = BASE_DIR / ".version"
    current = version_file.read_text().strip() if version_file.exists() else "none"

    print(f"[*] Current: {current}")
    print(f"[*] Latest : {latest}")

    if current == latest:
        print("[u2713] Up to date")
        return

    print("[*] Update available (manual apply recommended)")
    version_file.write_text(latest)


# ----------------------------
# CLI
# ----------------------------
def main():
    if len(sys.argv) < 2:
        print("""
            Devstick CLI

            Commands:
            devstick install
            devstick run debian
            devstick run ubuntu
            devstick update
        """)
        return

    cmd = sys.argv[1]

    if cmd == "run":
        if len(sys.argv) == 3:
            run_distro(sys.argv[2])
        else:
            print("Wrong usage")

    elif cmd == "install":
        if len(sys.argv) == 3:
            if sys.argv[2] == "debian":
                install_debian()
            elif sys.argv[2] == "ubuntu":
                install_ubuntu()
            else:
                print("OS not found.")
        elif len(sys.argv) == 2:
            install()
        else:
            print("Wrong usage")

    elif cmd == "remove":
        remove(sys.argv[2])

    elif cmd == "update":
        update()

    else:
        print("Unknown command")


if __name__ == "__main__":
    main()
