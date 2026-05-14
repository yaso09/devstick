import os
import subprocess
import shutil
from pathlib import Path
import sys
import platform

BASE_DIR = Path(__file__).resolve().parent
PYPROOT_BINARIES_DIR = BASE_DIR / "pyproot" / "binaries"


# ----------------------------
# PROOT BINARY
# ----------------------------
def get_proot_binary() -> str:
    arch = platform.machine()

    for name in [f"proot-{arch}-android", f"proot-{arch}", "proot"]:
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
class ProotSession:
    def __init__(self, rootfs_path: str, user: str | None = None):
        self.rootfs_path = str(Path(rootfs_path).resolve())
        self.user = user

    def run(self, command: list[str] | None = None):
        proot = get_proot_binary()
        shell = resolve_shell(self.rootfs_path)
        user = self.user

        print(f"[*] proot:  {proot}")
        print(f"[*] rootfs: {self.rootfs_path}")
        print(f"[*] user:   {user if user else 'root'}")
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
        env["PATH"] = (
            "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        )
        env["TERM"] = os.environ.get("TERM", "xterm-256color")
        env["LANG"] = "C.UTF-8"
        env.pop("LD_PRELOAD", None)

        if user:
            env.update({"HOME": home, "USER": user, "LOGNAME": user})
            cmd += [
                "/usr/bin/env", "-i",
                f"HOME={home}", f"USER={user}", f"LOGNAME={user}",
                "TERM=xterm-256color", "LANG=C.UTF-8",
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                shell,
            ]
        else:
            env.update({"HOME": "/root", "USER": "root", "LOGNAME": "root"})
            cmd.insert(1, "-0")
            cmd.append(shell)

        # Komut verilmişse shell'e -c ile ilet
        if command:
            cmd += ["-c", " ".join(command)]

        subprocess.run(
            cmd,
            env=env,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )


# ----------------------------
# API
# ----------------------------
def run_distro_temp(
    rootfs: str,
    user: str | None = None,
    command: list[str] | None = None,
):
    ProotSession(rootfs, user).run(command)