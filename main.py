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

USERS_DB = BASE_DIR / ".users.json"

GITHUB_API = "https://api.github.com/repos/yaso09/devstick/releases/latest"

PYPROOT_BINARIES_DIR = BASE_DIR / "pyproot" / "binaries"


# ----------------------------
# SYSTEM INFO
# ----------------------------
def arch():
    return platform.machine()


# ----------------------------
# USERS DB
# ----------------------------
def load_users():
    if USERS_DB.exists():
        return json.loads(USERS_DB.read_text())

    return {}


def save_users(data):
    USERS_DB.write_text(json.dumps(data, indent=2))


# ----------------------------
# ROOTFS RESOLVER
# ----------------------------
def get_rootfs(name):
    if name == "debian":
        return DEBIAN

    elif name == "ubuntu":
        return UBUNTU

    print("[!] Invalid distro")
    sys.exit(1)


# ----------------------------
# SAFE SHELL RESOLVER
# ----------------------------
def resolve_shell(rootfs: Path):
    """
    NEVER allow /usr/bin/bash
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

      1. pyproot/binaries/proot-<arch>-android
      2. pyproot/binaries/proot-<arch>
      3. proot/
      4. system proot
    """

    a = arch()
    android = is_termux()

    if android:
        candidate = PYPROOT_BINARIES_DIR / f"proot-{a}-android"

        if candidate.exists():
            return str(candidate)

    candidate = PYPROOT_BINARIES_DIR / f"proot-{a}"

    if candidate.exists():
        return str(candidate)

    if a == "aarch64":
        legacy = PROOT_DIR / "arm64" / "proot"

    elif a == "x86_64":
        legacy = PROOT_DIR / "x86_64" / "proot"

    else:
        legacy = None

    if legacy and legacy.exists():
        return str(legacy)

    system = shutil.which("proot")

    if system:
        return system

    print(f"[!] No proot binary found for arch: {a}")
    sys.exit(1)


def proot_distro_binary() -> str:
    p = PROOT_DIR / "proot-distro"

    return str(p) if p.exists() else "proot-distro"


# ----------------------------
# PATH INJECTION
# ----------------------------
def _inject_proot_to_path():
    if not PYPROOT_BINARIES_DIR.exists():
        return

    a = arch()

    android_bin = PYPROOT_BINARIES_DIR / f"proot-{a}-android"
    desktop_bin = PYPROOT_BINARIES_DIR / f"proot-{a}"

    proot_link = PYPROOT_BINARIES_DIR / "proot"

    source = (
        android_bin
        if android_bin.exists()
        else desktop_bin
        if desktop_bin.exists()
        else None
    )

    if source and not proot_link.exists():
        try:
            proot_link.symlink_to(source)

        except OSError:
            import shutil as _shutil

            _shutil.copy2(str(source), str(proot_link))

            proot_link.chmod(
                proot_link.stat().st_mode | 0o111
            )

    current_path = os.environ.get("PATH", "")
    binaries_str = str(PYPROOT_BINARIES_DIR)

    if binaries_str not in current_path.split(":"):
        os.environ["PATH"] = binaries_str + ":" + current_path


# ----------------------------
# ENV SANITIZER
# ----------------------------
def sanitize_env():
    os.environ.pop("SHELL", None)
    os.environ["SHELL"] = "/bin/bash"


# ----------------------------
# USER REGISTER
# ----------------------------
def register_user(
    distro,
    username,
    password,
    is_root=False
):
    rootfs = get_rootfs(distro)

    if not rootfs.exists():
        print("[!] Rootfs not installed")
        sys.exit(1)

    shell = resolve_shell(rootfs)

    print(f"[*] Creating user: {username}")

    pr = (
        PRoot(rootfs=str(rootfs))
        .bind("/proc")
        .bind("/sys")
        .bind("/dev")
        .workdir("/")
    )

    print("[*] Installing user management tools...")

    install_cmd = r"""
if command -v apt >/dev/null 2>&1; then
    apt update &&
    DEBIAN_FRONTEND=noninteractive apt install -y \
        passwd \
        login \
        sudo \
        bash \
        coreutils

elif command -v apk >/dev/null 2>&1; then
    apk add shadow sudo bash

elif command -v pacman >/dev/null 2>&1; then
    pacman -Sy --noconfirm shadow sudo bash

elif command -v dnf >/dev/null 2>&1; then
    dnf install -y shadow-utils sudo bash
fi
"""

    cmds = [
        f"useradd -m -s {shell} {username}",
        f"echo '{username}:{password}' | chpasswd"
    ]

    if is_root:
        if (rootfs / "etc/debian_version").exists():
            cmds.append(
                f"usermod -aG sudo {username}"
            )

            cmds.append(
                "mkdir -p /etc/sudoers.d"
            )

            cmds.append(
                "echo '%sudo ALL=(ALL:ALL) ALL' > /etc/sudoers.d/devstick"
            )

            cmds.append(
                "chmod 440 /etc/sudoers.d/devstick"
            )

        else:
            cmds.append(
                f"usermod -aG wheel {username}"
            )

    full_cmd = (
        install_cmd
        + "\n"
        + " && ".join(cmds)
    )

    result = subprocess.run(
        pr.build_argv([
            "/bin/sh",
            "-c",
            full_cmd
        ])
    )

    if result.returncode != 0:
        print("[!] Failed to create user")
        sys.exit(1)

    users = load_users()

    users.setdefault(distro, {})

    users[distro][username] = {
        "root": is_root
    }

    save_users(users)

    print(f"[✓] User created: {username}")

# ----------------------------
# RUN DISTRO
# ----------------------------
def run_distro(name, user=None):
    rootfs = get_rootfs(name)

    if not rootfs.exists():
        print("[!] Rootfs not found")
        print("[!] Run: devstick install")
        sys.exit(1)

    sanitize_env()

    shell = resolve_shell(rootfs)

    print(f"[*] Arch: {arch()}")
    print(f"[*] Distro: {name}")
    print(f"[*] Shell: {shell}")

    if user:
        print(f"[*] User: {user}")

    print("[*] Starting Devstick...\n")

    if is_termux():
        _inject_proot_to_path()

        run_distro_temp(
            name=name,
            rootfs=rootfs,
            user=user
        )

    else:
        pr = (
            PRoot(rootfs=str(rootfs))
            .bind("/proc")
            .bind("/sys")
            .bind("/dev")
            .workdir("/")
        )

        if user:
            cmd = [
                "/bin/su",
                "-",
                user
            ]

        else:
            cmd = [shell]

        subprocess.run(
            pr.build_argv(cmd)
        )


# ----------------------------
# PACKAGE MANAGER DETECTION
# ----------------------------
def detect_pkg_manager():
    managers = [
        "apt",
        "dnf",
        "apk",
        "pacman",
        "pkg"
    ]

    for m in managers:
        if subprocess.run(
            ["which", m],
            stdout=subprocess.DEVNULL
        ).returncode == 0:
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
        subprocess.run([
            "pkg",
            "install",
            "-y",
            "debootstrap",
            "proot"
        ])

    elif pm == "apt":
        subprocess.run([
            "sudo",
            "apt",
            "install",
            "-y",
            "debootstrap",
            "proot"
        ])

    elif pm == "dnf":
        subprocess.run([
            "sudo",
            "dnf",
            "install",
            "-y",
            "debootstrap",
            "proot"
        ])

    elif pm == "pacman":
        subprocess.run([
            "sudo",
            "pacman",
            "-S",
            "--noconfirm",
            "debootstrap",
            "proot"
        ])

    elif pm == "apk":
        subprocess.run([
            "sudo",
            "apk",
            "add",
            "debootstrap",
            "proot"
        ])


# ----------------------------
# INSTALL DISTROS
# ----------------------------
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
# INSTALL ROOTFS
# ----------------------------
def install_rootfs():
    ROOTFS_DIR.mkdir(exist_ok=True)

    install_debian()
    install_ubuntu()

    print("[✓] Install complete")


def install():
    if is_termux():
        install_proot_distro()

    install_dependencies()
    install_rootfs()


# ----------------------------
# REMOVE ROOTFS
# ----------------------------
def remove(name):
    rootfs = get_rootfs(name)

    if rootfs.exists():
        subprocess.run([
            "rm",
            "-rf",
            str(rootfs)
        ])

        print(f"[✓] Removed {name}")

    else:
        print("[!] Rootfs not found")
        sys.exit(1)


# ----------------------------
# UPDATE CHECK
# ----------------------------
def get_latest_release():
    try:
        data = json.loads(
            urllib.request.urlopen(
                GITHUB_API
            ).read().decode()
        )

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

    current = (
        version_file.read_text().strip()
        if version_file.exists()
        else "none"
    )

    print(f"[*] Current: {current}")
    print(f"[*] Latest : {latest}")

    if current == latest:
        print("[✓] Up to date")
        return

    print("[*] Update available")

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

devstick run debian --user yasir

devstick register debian \
  --username yasir \
  --password 123

devstick register debian \
  --username yasir \
  --password 123 \
  --root

devstick remove debian
devstick update
""")
        return

    cmd = sys.argv[1]

    # ----------------------------
    # RUN
    # ----------------------------
    if cmd == "run":
        if len(sys.argv) < 3:
            print("Wrong usage")
            return

        distro = sys.argv[2]

        user = None

        if "--user" in sys.argv:
            idx = sys.argv.index("--user")

            try:
                user = sys.argv[idx + 1]

            except IndexError:
                print("[!] Missing username")
                return

        run_distro(
            distro,
            user=user
        )

    # ----------------------------
    # INSTALL
    # ----------------------------
    elif cmd == "install":
        if len(sys.argv) == 3:
            if sys.argv[2] == "debian":
                install_debian()

            elif sys.argv[2] == "ubuntu":
                install_ubuntu()

            else:
                print("OS not found")

        elif len(sys.argv) == 2:
            install()

        else:
            print("Wrong usage")

    # ----------------------------
    # REGISTER
    # ----------------------------
    elif cmd == "register":
        if len(sys.argv) < 3:
            print("Wrong usage")
            return

        distro = sys.argv[2]

        username = None
        password = None

        if "--username" in sys.argv:
            username = sys.argv[
                sys.argv.index("--username") + 1
            ]

        if "--password" in sys.argv:
            password = sys.argv[
                sys.argv.index("--password") + 1
            ]

        if not username or not password:
            print("[!] Missing username/password")
            return

        is_root = "--root" in sys.argv

        register_user(
            distro=distro,
            username=username,
            password=password,
            is_root=is_root
        )

    # ----------------------------
    # REMOVE
    # ----------------------------
    elif cmd == "remove":
        if len(sys.argv) < 3:
            print("Wrong usage")
            return

        remove(sys.argv[2])

    # ----------------------------
    # UPDATE
    # ----------------------------
    elif cmd == "update":
        update()

    else:
        print("Unknown command")


if __name__ == "__main__":
    main()