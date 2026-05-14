import importlib.util
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import os
import shutil

BASE_DIR = Path(__file__).resolve().parent


@contextmanager
def temp_path(path):
    sys.path.insert(0, path)
    try:
        yield
    finally:
        sys.path.remove(path)


def update_pyproot():
    print("[*] Updating/Installing PyPRoot")

    PYPROOT_DIR = BASE_DIR / "pyproot"

    if PYPROOT_DIR.exists():
        shutil.rmtree(PYPROOT_DIR)

    subprocess.run([
        "git",
        "clone",
        "https://github.com/yaso09/pyproot.git"
    ])

    print("[*] Downloading PRoot binaries")

    with temp_path(PYPROOT_DIR):
        spec = importlib.util.spec_from_file_location(
            "download_binaries", PYPROOT_DIR / "scripts" / "download_binaries.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        original_argv = sys.argv
        sys.argv = ["download_binaries.py"]

        try:
            module.main()
        except SystemExit as e:
            if e.code not in (0, None):
                print(f"Failed to download binaries: exit code {e.code}")
        finally:
            sys.argv = original_argv

    for item in PYPROOT_DIR.iterdir():
        if item.name == "pyproot":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    d = PYPROOT_DIR / "pyproot"

    for item in d.iterdir():
        target = PYPROOT_DIR / item.name
        shutil.move(str(item), str(target))

    shutil.rmtree(d)

    print("[u2713] PyPRoot updated/installed")


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
        "https://github.com/termux/proot-distro.git"
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


update_pyproot()
