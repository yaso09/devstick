import shutil
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def update_proot_distro():
    print("[*] Updating/Installing proot-distro for Termux")

    PROOT_DISTRO_DIR = BASE_DIR / "proot-distro"

    RESULT_DIR = BASE_DIR / "proot_distro"

    if PROOT_DISTRO_DIR.exists():
        shutil.rmtree(PROOT_DISTRO_DIR)
    if RESULT_DIR.exists():
        shutil.rmtree(RESULT_DIR)

    subprocess.run([
        "git",
        "clone",
        "https://github.com/termux/proot-distro"
    ])

    for item in PROOT_DISTRO_DIR.iterdir():
        if item.name == "proot_distro":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    d = PROOT_DISTRO_DIR / "proot_distro"

    for item in d.iterdir():
        target = PROOT_DISTRO_DIR / item.name
        shutil.move(str(item), str(target))

    shutil.rmtree(d)
    os.rename(PROOT_DISTRO_DIR, RESULT_DIR)

    print("[u2713] proot-distro updated/installed")


if __name__ == "__main__":
    update_proot_distro()
