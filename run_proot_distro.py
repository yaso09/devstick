import os
import subprocess
import shutil
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent

PROOT_DISTRO_ROOT = os.path.expandvars(
    "$PREFIX/var/lib/proot-distro/installed-rootfs"
)

# pyproot/binaries dizinindeki binary'leri bul
PYPROOT_BINARIES_DIR = BASE_DIR / "pyproot" / "binaries"


def get_proot_binary() -> str:
    import platform
    a = platform.machine()

    for name in [f"proot-{a}-android", f"proot-{a}", "proot"]:
        candidate = PYPROOT_BINARIES_DIR / name
        if candidate.exists():
            return str(candidate)

    system = shutil.which("proot")
    if system:
        return system

    print("[!] No proot binary found")
    sys.exit(1)


def resolve_shell(rootfs: str) -> str:
    rootfs = Path(rootfs)
    if (rootfs / "bin/bash").exists():
        return "/bin/bash"
    if (rootfs / "bin/sh").exists():
        return "/bin/sh"
    print("[!] No shell found in rootfs")
    sys.exit(1)


class TempBindDistro:
    def __init__(self, name: str, rootfs_path: str):
        self.name = name
        self.rootfs_path = os.path.abspath(rootfs_path)
        self.target_path = os.path.join(PROOT_DISTRO_ROOT, name)

    def _attach(self):
        if os.path.islink(self.target_path):
            os.unlink(self.target_path)
        elif os.path.exists(self.target_path):
            raise RuntimeError(
                f"{self.target_path} geru00e7ek bir dizin u2014 silmiyorum")

        print(f"[*] Binding rootfs: {self.target_path}")
        os.symlink(self.rootfs_path, self.target_path)

    def _detach(self):
        if os.path.islink(self.target_path):
            print("[*] Removing bind link")
            os.unlink(self.target_path)

    def run(self):
        try:
            self._attach()

            proot = get_proot_binary()
            shell = resolve_shell(self.rootfs_path)

            print(f"[*] proot binary: {proot}")
            print(f"[*] Starting distro: {self.name}\n")

            cmd = [
                proot,
                "--kill-on-exit",
                "--link2symlink",
                "-0",
                "-r", self.rootfs_path,
                "-b", "/dev",
                "-b", "/proc",
                "-b", "/sys",
                "-b", f"/sdcard:/sdcard",
                "-w", "/root",
                "--",
                shell,
            ]

            env = os.environ.copy()
            env["PROOT_TMP_DIR"] = str(Path(self.rootfs_path) / "tmp")
            env["HOME"] = "/root"
            env["TERM"] = os.environ.get("TERM", "xterm-256color")
            env["LANG"] = "C.UTF-8"
            env.pop("LD_PRELOAD", None)

            os.makedirs(str(Path(self.rootfs_path) / "tmp"), exist_ok=True)

            subprocess.run(cmd, env=env)

        finally:
            print("\n[*] Cleaning up session...\n")
            self._detach()


def run_distro_temp(name: str, rootfs: str):
    session = TempBindDistro(name, rootfs)
    session.run()
