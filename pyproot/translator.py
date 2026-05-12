import os

class PathTranslator:
    def __init__(self, rootfs: str, bindings: dict = None):
        self.rootfs = os.path.realpath(rootfs)
        # {guest_path: host_path}
        self.bindings = {
            "/proc": "/proc",
            "/sys":  "/sys",
            "/dev":  "/dev",
        }
        if bindings:
            self.bindings.update(bindings)

    def to_host(self, guest_path: str) -> str:
        """Guest path'i host path'e çevir."""
        if not guest_path.startswith("/"):
            return guest_path  # relative path, dokunma

        # Binding kontrolü (önce uzun eşleşmeye bak)
        for g, h in sorted(self.bindings.items(), key=lambda x: -len(x[0])):
            if guest_path == g or guest_path.startswith(g + "/"):
                return h + guest_path[len(g):]

        # Rootfs'e yönlendir
        # Path traversal engellemek için normpath kullan
        safe = os.path.normpath("/" + guest_path).lstrip("/")
        host = os.path.join(self.rootfs, safe)
        return host

    def to_guest(self, host_path: str) -> str:
        """Host path'i guest path'e çevir (ters işlem)."""
        host_path = os.path.realpath(host_path)
        if host_path.startswith(self.rootfs):
            return host_path[len(self.rootfs):] or "/"
        for g, h in self.bindings.items():
            if host_path.startswith(h):
                return g + host_path[len(h):]
        return host_path