from tracer import Tracer


def run_pyproot(rootfs: str, cmd: list[str], bindings: dict[str, str] | None = None):
    """
    PyProot çalıştırır.

    Args:
        rootfs: Root filesystem path
        cmd: Çalıştırılacak komut ve argümanlar
        bindings: {guest_path: host_path} şeklinde bind mount eşlemeleri
    """
    bindings = bindings or {}

    print(f"[pyproot] rootfs: {rootfs}")
    print(f"[pyproot] komut:  {' '.join(cmd)}")

    t = Tracer(rootfs=rootfs, argv=cmd, bindings=bindings)
    return t.run()


def parse_cli(argv: list[str]):
    """
    Eski CLI davranışını koruyan parser.
    """
    if len(argv) < 3:
        raise ValueError("Yetersiz argüman")

    rootfs = argv[0]
    bindings = {}

    i = 1
    while i < len(argv):
        if argv[i] == "--bind":
            i += 1
            host, guest = argv[i].split(":")
            bindings[guest] = host
        elif argv[i] == "--":
            i += 1
            break
        i += 1

    cmd = argv[i:]
    if not cmd:
        raise ValueError("Komut eksik")

    return rootfs, cmd, bindings


if __name__ == "__main__":
    import sys

    rootfs, cmd, bindings = parse_cli(sys.argv[1:])
    run_pyproot(rootfs, cmd, bindings)