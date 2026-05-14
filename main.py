#!/usr/bin/env python3

from pyproot import PRoot
import os
import sys
import platform
import shutil
import subprocess
import urllib.request
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from is_termux import is_termux
from run_for_termux import run_distro_temp


# ─────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

ROOTFS_DIR = BASE_DIR / "rootfs"
PROOT_DIR  = BASE_DIR / "proot"

DEBIAN = ROOTFS_DIR / "debian"
UBUNTU = ROOTFS_DIR / "ubuntu"

USERS_DB   = BASE_DIR / ".users.json"
GITHUB_API = "https://api.github.com/repos/yaso09/devstick/releases/latest"

PYPROOT_BINARIES_DIR = BASE_DIR / "pyproot" / "binaries"

console = Console()


# ─────────────────────────────────────────
# LOGGING HELPERS
# ─────────────────────────────────────────
def ok(msg):   console.print(f"[bold green][✓][/bold green] {msg}")
def err(msg):  console.print(f"[bold red][✗][/bold red] {msg}")
def info(msg): console.print(f"[bold cyan][*][/bold cyan] {msg}")
def warn(msg): console.print(f"[bold yellow][!][/bold yellow] {msg}")


# ─────────────────────────────────────────
# HELP
# ─────────────────────────────────────────
def print_help():
    commands = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    commands.add_column("Command", style="cyan bold", no_wrap=True)
    commands.add_column("Description")

    commands.add_row("install",               "Install both distros")
    commands.add_row("install <distro>",       "Install a specific distro")
    commands.add_row("  --reinstall",          "Remove existing rootfs before installing")
    commands.add_row("run <distro>",           "Start an interactive shell")
    commands.add_row("  --user <username>",    "Log in as a specific user")
    commands.add_row("  -- <cmd> [args...]",   "Run a command instead of a shell")
    commands.add_row("register <distro>",      "Create a new user")
    commands.add_row("  --username <name>",    "")
    commands.add_row("  --password <pass>",    "")
    commands.add_row("  --root",               "Grant sudo privileges")
    commands.add_row("delete-user <distro>",   "Delete a user")
    commands.add_row("  --username <name>",    "")
    commands.add_row("  --keep-home",          "Do not remove the home directory")
    commands.add_row("list-users <distro>",    "List registered users")
    commands.add_row("remove <distro>",        "Delete a distro's rootfs")
    commands.add_row("update",                 "Check for Devstick updates")

    examples = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    examples.add_column("Example", style="dim")
    for ex in [
        "devstick install",
        "devstick run debian --user yasir",
        "devstick run debian -- python3 app.py",
        "devstick register debian --username yasir --password 123 --root",
        "devstick delete-user debian --username yasir",
        "devstick list-users debian",
    ]:
        examples.add_row(ex)

    console.print(Panel(
        Text("Devstick", style="bold"),
        subtitle="Termux Linux container manager",
        border_style="cyan",
    ))
    console.print("\n[bold]COMMANDS[/bold]")
    console.print(commands)
    console.print("[bold]DISTROS[/bold]   debian, ubuntu\n")
    console.print("[bold]EXAMPLES[/bold]")
    console.print(examples)


# ─────────────────────────────────────────
# SYSTEM
# ─────────────────────────────────────────
def arch():
    return platform.machine()


# ─────────────────────────────────────────
# PASSWORD HASHING  (replaces removed `crypt` module)
# ─────────────────────────────────────────
def _hash_password(password: str) -> str:
    """Return a SHA-512 crypt(3) hash compatible with /etc/shadow."""
    try:
        # passlib is the cleanest cross-platform option
        from passlib.hash import sha512_crypt          # type: ignore
        return sha512_crypt.using(rounds=5000).hash(password)
    except ImportError:
        pass

    try:
        # Python ≤ 3.12 still ships the (deprecated) crypt module
        import crypt  # noqa: PLC0415
        return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
    except ImportError:
        pass

    # Last resort: call openssl directly (available on most Linux/Termux)
    result = subprocess.run(
        ["openssl", "passwd", "-6", "-stdin"],
        input=password.encode(),
        capture_output=True,
    )
    if result.returncode == 0:
        return result.stdout.decode().strip()

    err("Cannot hash password: install passlib  (pip install passlib)")
    sys.exit(1)


# ─────────────────────────────────────────
# USERS DB
# ─────────────────────────────────────────
def load_users() -> dict:
    if USERS_DB.exists():
        return json.loads(USERS_DB.read_text())
    return {}


def save_users(data: dict):
    USERS_DB.write_text(json.dumps(data, indent=2))


# ─────────────────────────────────────────
# ROOTFS / SHELL RESOLVER
# ─────────────────────────────────────────
def get_rootfs(name: str) -> Path:
    if name == "debian":
        return DEBIAN
    if name == "ubuntu":
        return UBUNTU
    err(f"Unknown distro: '{name}'  (available: debian, ubuntu)")
    sys.exit(1)


def resolve_shell(rootfs: Path) -> str:
    for shell in ("/bin/bash", "/bin/sh"):
        if (rootfs / shell.lstrip("/")).exists():
            return shell
    err("No valid shell found in rootfs")
    sys.exit(1)


# ─────────────────────────────────────────
# PROOT BINARY
# ─────────────────────────────────────────
def proot_binary() -> str:
    a       = arch()
    android = is_termux()

    for candidate in [
        PYPROOT_BINARIES_DIR / f"proot-{a}-android" if android else None,
        PYPROOT_BINARIES_DIR / f"proot-{a}",
        PROOT_DIR / ("arm64" if a == "aarch64" else "x86_64") / "proot",
    ]:
        if candidate and candidate.exists():
            return str(candidate)

    system = shutil.which("proot")
    if system:
        return system

    err(f"No proot binary found for arch: {a}")
    sys.exit(1)


# ─────────────────────────────────────────
# PATH INJECTION
# ─────────────────────────────────────────
def _inject_proot_to_path():
    if not PYPROOT_BINARIES_DIR.exists():
        return

    a           = arch()
    android_bin = PYPROOT_BINARIES_DIR / f"proot-{a}-android"
    desktop_bin = PYPROOT_BINARIES_DIR / f"proot-{a}"
    proot_link  = PYPROOT_BINARIES_DIR / "proot"

    source = next(
        (b for b in [android_bin, desktop_bin] if b.exists()), None
    )

    if source and not proot_link.exists():
        try:
            proot_link.symlink_to(source)
        except OSError:
            shutil.copy2(str(source), str(proot_link))
            proot_link.chmod(proot_link.stat().st_mode | 0o111)

    current = os.environ.get("PATH", "")
    if str(PYPROOT_BINARIES_DIR) not in current.split(":"):
        os.environ["PATH"] = str(PYPROOT_BINARIES_DIR) + ":" + current


# ─────────────────────────────────────────
# ENV
# ─────────────────────────────────────────
def sanitize_env():
    os.environ.pop("SHELL", None)
    os.environ["SHELL"] = "/bin/bash"


# ─────────────────────────────────────────
# PROOT RUNNER (desktop)
# ─────────────────────────────────────────
def _proot_run(rootfs: Path, cmd: list, fake_root=False) -> subprocess.CompletedProcess:
    pr = (
        PRoot(rootfs=str(rootfs))
        .bind("/proc")
        .bind("/sys")
        .bind("/dev")
        .workdir("/root")
    )
    argv = pr.build_argv(cmd)
    if fake_root:
        argv.insert(1, "-0")
    return subprocess.run(argv)


# ─────────────────────────────────────────
# MANUAL USER CREATION (proot-safe fallback)
# Used on non-rooted Termux where useradd can't run inside proot
# ─────────────────────────────────────────
def _manual_create_user(rootfs: Path, username: str, password: str, is_root: bool):
    """
    Directly edit /etc/passwd, /etc/shadow, /etc/group inside the rootfs.
    This bypasses useradd entirely and works without real root.
    """
    uid = _next_uid(rootfs)
    gid = uid

    # ── passwd ──────────────────────────────
    passwd_file = rootfs / "etc/passwd"
    passwd_line = f"{username}:x:{uid}:{gid}::/home/{username}:/bin/bash\n"
    _append_if_missing(passwd_file, username + ":", passwd_line)

    # ── shadow ──────────────────────────────
    shadow_file = rootfs / "etc/shadow"
    hashed      = _hash_password(password)
    shadow_line = f"{username}:{hashed}:19000:0:99999:7:::\n"
    _append_if_missing(shadow_file, username + ":", shadow_line)

    # ── group ───────────────────────────────
    group_file = rootfs / "etc/group"
    group_line = f"{username}:x:{gid}:\n"
    _append_if_missing(group_file, username + ":", group_line)

    # sudo group membership
    if is_root:
        _add_user_to_group(group_file, "sudo", username)

    # ── home dir ────────────────────────────
    home = rootfs / "home" / username
    home.mkdir(parents=True, exist_ok=True)

    info(f"Manual user creation complete (uid={uid})")


def _next_uid(rootfs: Path) -> int:
    passwd = rootfs / "etc/passwd"
    uids   = []
    if passwd.exists():
        for line in passwd.read_text().splitlines():
            parts = line.split(":")
            if len(parts) >= 3:
                try:
                    uids.append(int(parts[2]))
                except ValueError:
                    pass
    uid = max((u for u in uids if u >= 1000), default=999) + 1
    return uid


def _append_if_missing(path: Path, prefix: str, line: str):
    text = path.read_text() if path.exists() else ""
    if not any(l.startswith(prefix) for l in text.splitlines()):
        path.write_text(text.rstrip("\n") + "\n" + line)


def _add_user_to_group(group_file: Path, group: str, username: str):
    if not group_file.exists():
        return
    lines = group_file.read_text().splitlines(keepends=True)
    new   = []
    for line in lines:
        if line.startswith(group + ":"):
            line = line.rstrip("\n")
            members = line.split(":")[-1]
            if username not in members.split(","):
                line += ("," if members else "") + username
            line += "\n"
        new.append(line)
    group_file.write_text("".join(new))


# ─────────────────────────────────────────
# REGISTER USER
# ─────────────────────────────────────────
def register_user(distro: str, username: str, password: str, is_root: bool = False):
    rootfs = get_rootfs(distro)

    if not rootfs.exists():
        err("Rootfs not installed. Run: devstick install")
        sys.exit(1)

    users = load_users()
    if username in users.get(distro, {}):
        err(f"User '{username}' already exists in {distro}")
        sys.exit(1)

    info(f"Creating user: {username}")

    shell = resolve_shell(rootfs)

    if is_root:
        sudo_block = (
            f"usermod -aG sudo {username}\n"
            f"mkdir -p /etc/sudoers.d\n"
            f"echo '%sudo ALL=(ALL:ALL) ALL' > /etc/sudoers.d/devstick\n"
            f"chmod 440 /etc/sudoers.d/devstick"
        ) if (rootfs / "etc/debian_version").exists() else f"usermod -aG wheel {username}"
    else:
        sudo_block = ""

    script = f"""#!/bin/sh
set -e
if command -v apt >/dev/null 2>&1; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y passwd login sudo bash coreutils
elif command -v apk >/dev/null 2>&1; then
    apk add shadow sudo bash
elif command -v pacman >/dev/null 2>&1; then
    pacman -Sy --noconfirm shadow sudo bash
elif command -v dnf >/dev/null 2>&1; then
    dnf install -y shadow-utils sudo bash
fi
useradd -m -s {shell} {username}
echo '{username}:{password}' | chpasswd
{sudo_block}
"""
    script_path = rootfs / "tmp" / "_devstick_register.sh"
    script_path.write_text(script)
    script_path.chmod(0o700)

    success = False

    try:
        if is_termux():
            _inject_proot_to_path()
            result = run_distro_temp(
                rootfs=str(rootfs),
                user=None,
                command=[shell, "/tmp/_devstick_register.sh"],
            )
        else:
            result = _proot_run(rootfs, [shell, "/tmp/_devstick_register.sh"], fake_root=True)

        if result is not None and result.returncode != 0:
            warn("proot method failed, trying manual fallback...")
        else:
            success = True

    except Exception as e:
        warn(f"proot method error: {e}")

    finally:
        if script_path.exists():
            script_path.unlink()

    if not success:
        info("Using manual user creation (proot-safe fallback)...")
        _manual_create_user(rootfs, username, password, is_root)

    users.setdefault(distro, {})[username] = {"root": is_root}
    save_users(users)

    ok(f"User created: {username}" + (" (sudo)" if is_root else ""))


# ─────────────────────────────────────────
# DELETE USER
# ─────────────────────────────────────────
def delete_user(distro: str, username: str, keep_home: bool = False):
    rootfs = get_rootfs(distro)

    if not rootfs.exists():
        err("Rootfs not found")
        sys.exit(1)

    users = load_users()
    if username not in users.get(distro, {}):
        err(f"User '{username}' not found in .users.json for {distro}")
        sys.exit(1)

    info(f"Deleting user: {username}")

    shell = resolve_shell(rootfs)
    flag  = "" if keep_home else "-r"
    script = f"#!/bin/sh\nuserdel {flag} {username} 2>/dev/null || true\n"

    script_path = rootfs / "tmp" / "_devstick_delete.sh"
    script_path.write_text(script)
    script_path.chmod(0o700)

    try:
        if is_termux():
            _inject_proot_to_path()
            run_distro_temp(
                rootfs=str(rootfs),
                user=None,
                command=[shell, "/tmp/_devstick_delete.sh"],
            )
        else:
            _proot_run(rootfs, [shell, "/tmp/_devstick_delete.sh"], fake_root=True)
    except Exception as e:
        warn(f"userdel failed ({e}), falling back to manual removal...")
    finally:
        if script_path.exists():
            script_path.unlink()

    _manual_delete_user(rootfs, username, keep_home)

    users[distro].pop(username, None)
    save_users(users)

    ok(f"User deleted: {username}")


def _manual_delete_user(rootfs: Path, username: str, keep_home: bool):
    for filepath in ["etc/passwd", "etc/shadow", "etc/group", "etc/gshadow"]:
        f = rootfs / filepath
        if not f.exists():
            continue
        lines    = f.read_text().splitlines(keepends=True)
        filtered = [l for l in lines if not l.startswith(username + ":")]

        if filepath in ("etc/group", "etc/gshadow"):
            cleaned = []
            for line in filtered:
                parts = line.rstrip("\n").split(":")
                if len(parts) >= 4:
                    members = [m for m in parts[-1].split(",") if m != username]
                    parts[-1] = ",".join(members)
                    line = ":".join(parts) + "\n"
                cleaned.append(line)
            filtered = cleaned

        f.write_text("".join(filtered))

    if not keep_home:
        home = rootfs / "home" / username
        if home.exists():
            shutil.rmtree(str(home))
            info(f"Removed home directory: /home/{username}")
        else:
            info("Home directory not found, skipping")


# ─────────────────────────────────────────
# LIST USERS
# ─────────────────────────────────────────
def list_users(distro: str):
    get_rootfs(distro)  # validate distro name

    users        = load_users()
    distro_users = users.get(distro, {})

    if not distro_users:
        info(f"No registered users for {distro}")
        return

    table = Table(title=f"Users in {distro}", box=box.ROUNDED, border_style="cyan")
    table.add_column("Username", style="cyan bold")
    table.add_column("Role", justify="center")

    for name, meta in distro_users.items():
        role = "[yellow]sudo[/yellow]" if meta.get("root") else "normal"
        table.add_row(name, role)

    console.print(table)


# ─────────────────────────────────────────
# RUN DISTRO
# ─────────────────────────────────────────
def run_distro(name: str, user: str = None, command: list = None):
    rootfs = get_rootfs(name)

    if not rootfs.exists():
        err("Rootfs not found. Run: devstick install")
        sys.exit(1)

    sanitize_env()
    shell = resolve_shell(rootfs)

    info(f"Arch: {arch()}")
    info(f"Distro: {name}")
    info(f"Shell: {shell}")
    if user:
        info(f"User: {user}")
    console.print("[bold][*] Starting Devstick...[/bold]\n")

    if is_termux():
        _inject_proot_to_path()
        run_distro_temp(rootfs=rootfs, user=user, command=command)
        return

    if user:
        cmd = ["/bin/su", "-", user]
        if command:
            cmd += ["-c", " ".join(command)]
        _proot_run(rootfs, cmd)
    else:
        cmd = [shell]
        if command:
            cmd += ["-c", " ".join(command)]
        _proot_run(rootfs, cmd, fake_root=True)


# ─────────────────────────────────────────
# PACKAGE MANAGER
# ─────────────────────────────────────────
def detect_pkg_manager() -> str | None:
    for m in ["apt", "dnf", "apk", "pacman", "pkg"]:
        if shutil.which(m):
            return m
    return None


def install_dependencies():
    pm = detect_pkg_manager()
    if not pm:
        err("No package manager found")
        sys.exit(1)

    info(f"Package manager: {pm}")
    cmds = {
        "pkg":    ["pkg", "install", "-y", "debootstrap", "proot"],
        "apt":    ["sudo", "apt", "install", "-y", "debootstrap", "proot"],
        "dnf":    ["sudo", "dnf", "install", "-y", "debootstrap", "proot"],
        "pacman": ["sudo", "pacman", "-S", "--noconfirm", "debootstrap", "proot"],
        "apk":    ["sudo", "apk", "add", "debootstrap", "proot"],
    }
    subprocess.run(cmds.get(pm, cmds["apt"]))


# ─────────────────────────────────────────
# INSTALL DISTROS
# ─────────────────────────────────────────
def _debootstrap(suite: str, target: Path, mirror: str, reinstall: bool):
    if target.exists():
        if reinstall:
            info(f"Removing existing rootfs: {target.name}")
            subprocess.run(["rm", "-rf", str(target)])
        else:
            warn(f"{target.name} already installed. Use --reinstall to overwrite")
            return

    info(f"Installing {target.name} ({suite})...")
    cmd = ["debootstrap", "--variant=minbase", suite, str(target), mirror]
    if not is_termux():
        cmd.insert(0, "sudo")
    subprocess.run(cmd, check=True)


def install_debian(reinstall: bool = False):
    install_dependencies()
    ROOTFS_DIR.mkdir(exist_ok=True)
    _debootstrap("stable", DEBIAN, "http://deb.debian.org/debian", reinstall)


def install_ubuntu(reinstall: bool = False):
    install_dependencies()
    ROOTFS_DIR.mkdir(exist_ok=True)
    _debootstrap("jammy", UBUNTU, "http://archive.ubuntu.com/ubuntu", reinstall)


def install(reinstall: bool = False):
    install_dependencies()
    ROOTFS_DIR.mkdir(exist_ok=True)
    install_debian(reinstall)
    install_ubuntu(reinstall)
    ok("Install complete")


# ─────────────────────────────────────────
# REMOVE ROOTFS
# ─────────────────────────────────────────
def remove(name: str):
    rootfs = get_rootfs(name)
    if not rootfs.exists():
        err("Rootfs not found")
        sys.exit(1)
    subprocess.run(["rm", "-rf", str(rootfs)])
    ok(f"Removed {name}")


# ─────────────────────────────────────────
# UPDATE
# ─────────────────────────────────────────
def get_latest_release() -> str | None:
    try:
        data = json.loads(urllib.request.urlopen(GITHUB_API).read().decode())
        return data["tag_name"]
    except Exception as e:
        err(f"Update check failed: {e}")
        return None


def update():
    info("Checking for updates...")
    latest = get_latest_release()
    if not latest:
        return

    version_file = BASE_DIR / ".version"
    current      = version_file.read_text().strip() if version_file.exists() else "none"

    info(f"Current : {current}")
    info(f"Latest  : {latest}")

    if current == latest:
        ok("Already up to date")
        return

    warn("Update available!")
    version_file.write_text(latest)


# ─────────────────────────────────────────
# ARG HELPERS
# ─────────────────────────────────────────
def _get(args: list, flag: str, default=None):
    if flag in args:
        idx = args.index(flag)
        try:
            return args[idx + 1]
        except IndexError:
            err(f"Missing value for {flag}")
            sys.exit(1)
    return default


def _has(args: list, flag: str) -> bool:
    return flag in args


# ─────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print_help()
        return

    cmd = args[0]

    # ── install ──────────────────────────
    if cmd == "install":
        reinstall = _has(args, "--reinstall")
        if len(args) >= 2 and not args[1].startswith("-"):
            distro = args[1]
            if distro == "debian":
                install_debian(reinstall)
            elif distro == "ubuntu":
                install_ubuntu(reinstall)
            else:
                err(f"Unknown distro: {distro}")
        else:
            install(reinstall)

    # ── run ──────────────────────────────
    elif cmd == "run":
        if len(args) < 2:
            err("Usage: devstick run <distro> [--user <name>] [-- cmd]")
            sys.exit(1)

        distro = args[1]
        user   = _get(args, "--user")

        command = None
        if "--" in args:
            sep_idx = args.index("--")
            command = args[sep_idx + 1:]

        run_distro(distro, user=user, command=command)

    # ── register ─────────────────────────
    elif cmd == "register":
        if len(args) < 2:
            err("Usage: devstick register <distro> --username <n> --password <p> [--root]")
            sys.exit(1)
        distro   = args[1]
        username = _get(args, "--username")
        password = _get(args, "--password")
        is_root  = _has(args, "--root")

        if not username or not password:
            err("--username and --password are required")
            sys.exit(1)

        register_user(distro, username, password, is_root)

    # ── delete-user ──────────────────────
    elif cmd == "delete-user":
        if len(args) < 2:
            err("Usage: devstick delete-user <distro> --username <n>")
            sys.exit(1)
        distro    = args[1]
        username  = _get(args, "--username")
        keep_home = _has(args, "--keep-home")

        if not username:
            err("--username is required")
            sys.exit(1)

        delete_user(distro, username, keep_home)

    # ── list-users ───────────────────────
    elif cmd == "list-users":
        if len(args) < 2:
            err("Usage: devstick list-users <distro>")
            sys.exit(1)
        list_users(args[1])

    # ── remove ───────────────────────────
    elif cmd == "remove":
        if len(args) < 2:
            err("Usage: devstick remove <distro>")
            sys.exit(1)
        remove(args[1])

    # ── update ───────────────────────────
    elif cmd == "update":
        update()

    else:
        err(f"Unknown command: '{cmd}'")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
