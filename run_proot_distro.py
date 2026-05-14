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
    a = platform.machine()

    for name in [
        f"proot-{a}-android",
        f"proot-{a}",
        "proot"
    ]:
        candidate = PYPROOT_BINARIES_DIR / name
        if candidate.exists():
            return str(candidate)

    system = shutil.which("proot")
    if system:
        return system

    print("[!] No proot binary found")
    sys.exit(1)


# ----------------------------
# SHELL RESOLVE
# ----------------------------
def resolve_shell(rootfs: str) -> str:
    rootfs = Path(rootfs)

    if (rootfs / "bin/bash").exists():
        return "/bin/bash"

    if (rootfs / "bin/sh").exists():
        return "/bin/sh"

    print("[!] No shell found in rootfs")
    sys.exit(1)


# ----------------------------
# TEMP DISTRO SESSION
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
    # BIND ROOTFS
    # ----------------------------
    def _attach(self):
        if os.path.islink(self.target_path):
            os.unlink(self.target_path)

        elif os.path.exists(self.target_path):
            raise RuntimeError(
                f"{self.target_path} exists and is not symlink"
            )

        os.symlink(self.rootfs_path, self.target_path)

    # ----------------------------
    # CLEANUP
    # ----------------------------
    def _detach(self):
        if os.path.islink(self.target_path):
            os.unlink(self.target_path)

    # ----------------------------
    # RUN SESSION (DEVSTICK STYLE)
    # ----------------------------
    def run(self):
        try:
            self._attach()

            proot = get_proot_binary()
            shell = resolve_shell(self.rootfs_path)

            print(f"[*] proot: {proot}")
            print(f"[*] rootfs: {self.rootfs_path}")
            if self.user:
                print(f"[*] user: {self.user}")
            print()

            # ----------------------------
            # BASE PROOT COMMAND
            # ----------------------------
            home = f"/home/{self.user}" if self.user else "/root"

            cmd = [
                proot,
                "--kill-on-exit",
                "-r", self.rootfs_path,

                "-b", "/dev",
                "-b", "/proc",
                "-b", "/sys",
                "-b", "/sdcard:/sdcard",

                "-w", home,

                "--"
            ]

            # ----------------------------
            # DEVSTICK LOGIN LOGIC (IMPORTANT PART)
            # ----------------------------
            env = os.environ.copy()

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

            if self.user:
                # Devstick-style: NO su, NO login shell
                env["HOME"] = f"/home/{self.user}"
                env["USER"] = self.user
                env["LOGNAME"] = self.user

                cmd += [
                    "/usr/bin/env",
                    "-i",
                    f"HOME=/home/{self.user}",
                    f"USER={self.user}",
                    f"LOGNAME={self.user}",
                    "TERM=xterm-256color",
                    "LANG=C.UTF-8",
                    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    shell
                ]

            else:
                env["HOME"] = "/root"
                env["USER"] = "root"
                env["LOGNAME"] = "root"
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
# PUBLIC API
# ----------------------------
def run_distro_temp(name: str, rootfs: str, user: str | None = None):
    session = TempBindDistro(
        name=name,
        rootfs_path=rootfs,
        user=user
    )
    session.run()