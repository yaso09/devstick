import os
import subprocess
import shutil
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent

PROOT_DISTRO_ROOT = os.path.expandvars(
    "$PREFIX/var/lib/proot-distro/installed-rootfs"
)

PYPROOT_BINARIES_DIR = BASE_DIR / "pyproot" / "binaries"


# ----------------------------
# PROOT BINARY
# ----------------------------
def get_proot_binary() -> str:
    import platform

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
# SHELL RESOLUTION
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
# TEMP BIND DISTRO
# ----------------------------
class TempBindDistro:
    def __init__(
        self,
        name: str,
        rootfs_path: str,
        user: str | None = None
    ):
        self.name = name
        self.rootfs_path = os.path.abspath(
            str(rootfs_path)
        )

        self.user = user

        self.target_path = os.path.join(
            PROOT_DISTRO_ROOT,
            name
        )

    # ----------------------------
    # ATTACH
    # ----------------------------
    def _attach(self):
        if os.path.islink(self.target_path):
            os.unlink(self.target_path)

        elif os.path.exists(self.target_path):
            raise RuntimeError(
                f"{self.target_path} gerçek bir dizin — silmiyorum"
            )

        print(f"[*] Binding rootfs: {self.target_path}")

        os.symlink(
            self.rootfs_path,
            self.target_path
        )

    # ----------------------------
    # DETACH
    # ----------------------------
    def _detach(self):
        if os.path.islink(self.target_path):
            print("[*] Removing bind link")

            os.unlink(self.target_path)

    # ----------------------------
    # RUN
    # ----------------------------
    def run(self):
        try:
            self._attach()

            proot = get_proot_binary()
            shell = resolve_shell(self.rootfs_path)

            print(f"[*] proot binary: {proot}")
            print(f"[*] Starting distro: {self.name}")

            if self.user:
                print(f"[*] User: {self.user}")

            print()

            # ----------------------------
            # BASE COMMAND
            # ----------------------------
            cmd = [
                proot,

                "--kill-on-exit",
                "--link2symlink",

                "-0",

                "-r", self.rootfs_path,

                "-b", "/dev",
                "-b", "/proc",
                "-b", "/sys",

                "-b", "/sdcard:/sdcard",

                "-w",
                "/root",

                "--"
            ]

            # ----------------------------
            # USER LOGIN
            # ----------------------------
            if self.user:
                su_path = Path(
                    self.rootfs_path
                ) / "bin" / "su"

                if not su_path.exists():
                    print("[!] /bin/su not found")
                    print("[!] Install login/passwd package")
                    sys.exit(1)

                cmd.extend([
                    "/bin/su",
                    "-",
                    self.user
                ])

            else:
                cmd.append(shell)

            # ----------------------------
            # ENV
            # ----------------------------
            env = os.environ.copy()

            env["PROOT_TMP_DIR"] = str(
                Path(self.rootfs_path) / "tmp"
            )

            env["TERM"] = os.environ.get(
                "TERM",
                "xterm-256color"
            )

            env["LANG"] = "C.UTF-8"

            env.pop("LD_PRELOAD", None)

            # USER ENV
            if self.user:
                env["HOME"] = f"/home/{self.user}"
                env["USER"] = self.user
                env["LOGNAME"] = self.user

            else:
                env["HOME"] = "/root"
                env["USER"] = "root"
                env["LOGNAME"] = "root"

            os.makedirs(
                str(Path(self.rootfs_path) / "tmp"),
                exist_ok=True
            )

            # ----------------------------
            # RUN
            # ----------------------------
            subprocess.run(
                cmd,
                env=env,

                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr
            )

        finally:
            print("\n[*] Cleaning up session...\n")

            self._detach()


# ----------------------------
# PUBLIC API
# ----------------------------
def run_distro_temp(
    name: str,
    rootfs: str,
    user: str | None = None
):
    session = TempBindDistro(
        name=name,
        rootfs_path=rootfs,
        user=user
    )

    session.run()