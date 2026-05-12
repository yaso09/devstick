from . import tracer
import os

Tracer = tracer.Tracer

class SandboxShell:
    def __init__(self, rootfs: str, bindings=None):
        self.rootfs = rootfs
        self.bindings = bindings or {}

    def run_command(self, cmd: str):
        """
        Tek komut çalıştırır
        """
        if not cmd.strip():
            return

        t = Tracer(
            rootfs=self.rootfs,
            argv=cmd.split(),
            bindings=self.bindings
        )
        return t.run()

    def loop(self):
        """
        Interactive sandbox terminal
        """
        print(f"[sandbox] rootfs: {self.rootfs}")
        print("Çıkmak için: exit veya quit\n")

        # Prompt için daha okunaklı isim
        prompt_name = os.path.basename(self.rootfs.rstrip("/")) or "/"

        while True:
            try:
                cmd = input(f"{prompt_name}> ").strip()

                if cmd in ("exit", "quit"):
                    print("[sandbox] çıkılıyor...")
                    break

                self.run_command(cmd)

            except KeyboardInterrupt:
                print("\n[sandbox] (CTRL+C) komut iptal edildi")
            except Exception as e:
                print(f"[sandbox] hata: {e}")


def start_sandbox(rootfs: str, bindings=None):
    """
    Sandbox terminali başlatır
    """
    shell = SandboxShell(rootfs, bindings)
    shell.loop()