import os
import subprocess
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROOT_DIR = BASE_DIR / "proot"

def proot_distro_binary():
    p = PROOT_DIR / "proot-distro"
    return str(p) if p.exists() else "proot-distro"

PROOT_DISTRO_ROOT = os.path.expandvars(
    "$PREFIX/var/lib/proot-distro/installed-rootfs"
)


class TempBindDistro:
    def __init__(self, name: str, rootfs_path: str):
        self.name = name
        self.rootfs_path = os.path.abspath(rootfs_path)
        self.target_path = os.path.join(PROOT_DISTRO_ROOT, name)

    # ----------------------------
    # ATTACH ROOTFS (NO COPY)
    # ----------------------------
    def _attach(self):
        if os.path.exists(self.target_path):
            raise RuntimeError(f"{self.target_path} already exists")

        print(f"[*] Binding rootfs → {self.target_path}")

        # 🔥 bind mount yerine symlink (Termux için en stabil yöntem)
        os.symlink(self.rootfs_path, self.target_path)

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

            print(f"\n[*] Starting proot-distro: {self.name}\n")

            subprocess.run([
                proot_distro_binary(),
                "login",
                self.name,
                "--shared-tmp"
            ])

        finally:
            print("\n[*] Cleaning up session...\n")
            self._detach()


# ----------------------------
# PUBLIC API
# ----------------------------
def run_distro_temp(name: str, rootfs_path: str):
    session = TempBindDistro(name, rootfs_path)
    session.run()