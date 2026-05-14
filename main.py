#!/usr/bin/env python3
from pyproot import PRoot
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

# pyproot tarafu0131ndan indirilen binary'lerin bulunduu011fu dizin
PYPROOT_BINARIES_DIR = BASE_DIR / "pyproot" / "binaries"


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
def proot_binary() -> str:
    """
    Resolution order:
      1. pyproot/binaries/proot-<arch>-android  (Termux)
      2. pyproot/binaries/proot-<arch>          (desktop)
      3. proot/  klasu00f6ru00fcndeki eski binary
      4. system proot
    """
    a = arch()
    android = is_termux()

    # 1. pyproot/binaries iu00e7indeki binary
    if android:
        candidate = PYPROOT_BINARIES_DIR / f"proot-{a}-android"
        if candidate.exists():
            return str(candidate)

    candidate = PYPROOT_BINARIES_DIR / f"proot-{a}"
    if candidate.exists():
        return str(candidate)

    # 2. Eski proot/ dizini (geriye du00f6nu00fck uyumluluk)
    if a == "aarch64":
        legacy = PROOT_DIR / "arm64" / "proot"
    elif a == "x86_64":
        legacy = PROOT_DIR / "x86_64" / "proot"
    else:
        legacy = None

    if legacy and legacy.exists():
        return str(legacy)

    # 3. System proot
    system = shutil.which("proot")
    if system:
        return system

    print(f"[!] No proot binary found for arch: {a}")
    sys.exit(1)


def proot_distro_binary() -> str:
    p = PROOT_DIR / "proot-distro"
    return str(p) if p.exists() else "proot-distro"


def _inject_proot_to_path():
    """
    Termux'ta proot-distro'nun shutil.which("proot") ile
    bizim binary'mizi bulmasu0131 iu00e7in PATH'e enjekte et.
    """
    if not PYPROOT_BINARIES_DIR.exists():
        return

    a = arch()

    # android binary varsa onu, yoksa desktop binary'yi "proot" adu0131yla symlink/copy et
    android_bin = PYPROOT_BINARIES_DIR / f"proot-{a}-android"
    desktop_bin = PYPROOT_BINARIES_DIR / f"proot-{a}"
    proot_link = PYPROOT_BINARIES_DIR / "proot"

    source = android_bin if android_bin.exists(
    ) else desktop_bin if desktop_bin.exists() else None

    if source and not proot_link.exists():
        try:
            proot_link.symlink_to(source)
        except OSError:
            # symlink bau015faru0131su0131z olursa kopyala
            import shutil as _shutil
            _shutil.copy2(str(source), str(proot_link))
            proot_link.chmod(proot_link.stat().st_mode | 0o111)

    # PATH'e en bau015fa ekle
    current_path = os.environ.get("PATH", "")
    binaries_str = str(PYPROOT_BINARIES_DIR)
    if binaries_str not in current_path.split(":"):
        os.environ["PATH"] = binaries_str + ":" + current_path


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

    if is_termux():
        # proot-distro shutil.which("proot") kullandu0131u011fu0131 iu00e7in PATH'e enjekte et
        _inject_proot_to_path()
        run_distro_temp(name, rootfs)
    else:
        pr = (
            PRoot(rootfs=str(rootfs))
            .bind("/proc")
            .bind("/sys")
            .bind("/dev")
        )

        subprocess.run(
            pr.build_argv([shell])
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
            devstick install debian
            devstick install ubuntu
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
