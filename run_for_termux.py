import os
import subprocess
import shutil
from pathlib import Path
import sys
import platform

BASE_DIR = Path(__file__).resolve().parent

PROOT_DISTRO_ROOT = os.path.expandvars(
    "$PREFIX/var/lib/proot-distro/installed-rootfs"
)

PYPROOT_BINARIES_DIR = BASE_DIR / "pyproot" / "binaries"


# ----------------------------
# PROOT BINARY
# ----------------------------
def get_proot_binary() -> str:
    arch = platform.machine()

    for name in [
        f"proot-{arch}-android",
        f"proot-{arch}",
        "proot"
    ]:
        candidate = PYPROOT_BINARIES_DIR / name
        if candidate.exists():
            return str(candidate)

    system = shutil.which("proot")
    if system:
        return system

    print("[!] proot binary not found")
    sys.exit(1)


# ----------------------------
# SHELL
# ----------------------------
def resolve_shell(rootfs: str) -> str:
    rootfs = Path(rootfs)

    if (rootfs / "bin/bash").exists():
        return "/bin/bash"

    if (rootfs / "bin/sh").exists():
        return "/bin/sh"

    print("[!] no shell in rootfs")
    sys.exit(1)


# ----------------------------
# SESSION
# ----------------------------
class TempBindDistro:
    def __init__(self, name: str, rootfs_path: str, user: str | None = None):
        self.name = name
        self.rootfs_path = str(Path(rootfs_path).resolve())
        self.user = user

        self.target_path = os.path.join(
            PROOT_DISTRO_ROOT,
            name
        )

    # ----------------------------
    # BIND
    # ----------------------------
    def _attach(self):
        if os.path.islink(self.target_path):
            os.unlink(self.target_path)

        elif os.path.exists(self.target_path):
            raise RuntimeError(
                f"{self.target_path} is not a symlink"
            )

        os.symlink(self.rootfs_path, self.target_path)

    # ----------------------------
    # CLEAN
    # ----------------------------
    def _detach(self):
        if os.path.islink(self.target_path):
            os.unlink(self.target_path)

    # ----------------------------
    # RUN
    # ----------------------------
    def run(self):
        try:
            self._attach()

            proot = get_proot_binary()
            shell = resolve_shell(self.rootfs_path)

            user = self.user if self.user else None

            print(f"[*] proot: {proot}")
            print(f"[*] rootfs: {self.rootfs_path}")
            print(f"[*] user: {user if user else 'root'}")
            print()

            home = f"/home/{user}" if user else "/root"

            cmd = [
                proot,
                "--kill-on-exit",
                "-r", self.rootfs_path,

                "-b", "/dev",
                "-b", "/proc",
                "-b", "/sys",
                "-b", "/sdcard:/sdcard",

                "-w", home,
            ]

            env = os.environ.copy()

            # ----------------------------
            # GLOBAL SAFE PATH (CRITICAL)
            # ----------------------------
            env["PATH"] = (
                "/usr/local/sbin:"
                "/usr/local/bin:"
                "/usr/sbin:"
                "/usr/bin:"
                "/sbin:"
                "/bin"
            )

            env["TERM"] = os.environ.get("TERM", "xterm-256color")
            env["LANG"] = "C.UTF-8"
            env.pop("LD_PRELOAD", None)

            # ----------------------------
            # USER MODE (DEVSTICK STYLE)
            # ----------------------------
            if user:
                env["HOME"] = f"/home/{user}"
                env["USER"] = user
                env["LOGNAME"] = user

                cmd += [
                    "/usr/bin/env",
                    "-i",
                    f"HOME=/home/{user}",
                    f"USER={user}",
                    f"LOGNAME={user}",
                    "TERM=xterm-256color",
                    "LANG=C.UTF-8",
                    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    shell
                ]

            # ----------------------------
            # ROOT MODE (DEFAULT)
            # ----------------------------
            else:
                env["HOME"] = "/root"
                env["USER"] = "root"
                env["LOGNAME"] = "root"

                cmd.insert(1, "-0")

                cmd += [shell]

            # ----------------------------
            # EXEC
            # ----------------------------
            subprocess.run(
                cmd,
                env=env,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr
            )

        finally:
            print("\n[*] cleanup...\n")
            self._detach()


# ----------------------------
# API
# ----------------------------
def run_distro_temp(name: str, rootfs: str, user: str | None = None):
    TempBindDistro(name, rootfs, user).run()
