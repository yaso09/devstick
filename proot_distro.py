import os
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROOT_DIR = BASE_DIR / "proot"

def proot_distro_binary():
    p = PROOT_DIR / "proot-distro"
    return str(p) if p.exists() else "proot-distro"

PROOT_DISTRO_ROOT = os.path.expandvars(
    "$PREFIX/var/lib/proot-distro/installed-rootfs"
)

class TempDistroSession:
    def __init__(self, name: str, source_path: str, shell="/bin/bash"):
        self.name = name
        self.source_path = os.path.abspath(source_path)
        self.target_path = os.path.join(PROOT_DISTRO_ROOT, name)
        self.shell = shell
        self.proc = None

    # ----------------------------
    # INSTALL ROOTFS
    # ----------------------------
    def _install(self):
        if os.path.exists(self.target_path):
            shutil.rmtree(self.target_path)

        shutil.copytree(self.source_path, self.target_path)

    # ----------------------------
    # RESTORE ROOTFS
    # ----------------------------
    def _restore(self):
        if os.path.exists(self.source_path):
            return  # güvenli davran

        shutil.move(self.target_path, self.source_path)

    # ----------------------------
    # START SESSION
    # ----------------------------
    def start(self):
        self._install()

        self.proc = subprocess.Popen([
            proot_distro_binary(),
            "login",
            self.name,
            "--shared-tmp"
        ])

        return self.proc

    # ----------------------------
    # WAIT SESSION END
    # ----------------------------
    def wait(self):
        if self.proc:
            self.proc.wait()

    # ----------------------------
    # STOP + CLEANUP
    # ----------------------------
    def close(self):
        try:
            if self.proc:
                self.proc.terminate()
        finally:
            self._restore()

    # ----------------------------
    # CONTEXT MANAGER SUPPORT
    # ----------------------------
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


# ----------------------------
# PUBLIC API
# ----------------------------
def run_temp_distro(name: str, path: Path):
    session = TempDistroSession(name, path)
    session.start()
    session.wait()
    session.close()