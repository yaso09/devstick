from . import tracer
import os

Tracer = tracer.Tracer

class SandboxSession:
    def __init__(self, rootfs: str, cmd: list[str], bindings=None):
        self.rootfs = rootfs
        self.cmd = cmd
        self.bindings = bindings or {}

    def start(self):
        prompt = os.path.basename(self.rootfs.rstrip("/")) or "/"

        print(f"[sandbox] rootfs: {self.rootfs}")
        print(f"[sandbox] cmd: {' '.join(self.cmd)}")
        print("Çıkış için: exit\n")

        t = Tracer(
            rootfs=self.rootfs,
            argv=self.cmd,
            bindings=self.bindings
        )

        return t.run()


def start_sandbox(rootfs: str, cmd: list[str], bindings=None):
    """
    Sandbox başlatır.

    Args:
        rootfs: sandbox filesystem
        cmd: çalıştırılacak komut (örn: ["/bin/bash"])
        bindings: host -> guest mount map
    """
    session = SandboxSession(
        rootfs=rootfs,
        cmd=cmd,
        bindings=bindings
    )
    return session.start()