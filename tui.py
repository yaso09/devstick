#!/usr/bin/env python3
"""
devstick_tui.py — Self-contained Devstick TUI.
Includes all backend logic from main.py; no subprocess calls to main.py.
Usage: python devstick_tui.py
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Textual ───────────────────────────────────────────────────────────────────
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Middle, Center
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    DataTable,
    Input,
    Label,
    Static,
    Switch,
)

# ── Project-local helpers (same directory) ────────────────────────────────────
try:
    from pyproot import PRoot
    _HAS_PYPROOT = True
except ImportError:
    _HAS_PYPROOT = False

try:
    from is_termux import is_termux as _is_termux
except ImportError:
    def _is_termux() -> bool:
        return "com.termux" in os.environ.get("PREFIX", "")

try:
    from run_for_termux import run_distro_temp as _run_distro_temp
    _HAS_TERMUX_RUNNER = True
except ImportError:
    _HAS_TERMUX_RUNNER = False
    def _run_distro_temp(*a, **kw):
        raise RuntimeError("run_for_termux module not found")


# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════

BASE_DIR   = Path(__file__).resolve().parent
ROOTFS_DIR = BASE_DIR / "rootfs"
PROOT_DIR  = BASE_DIR / "proot"
DEBIAN     = ROOTFS_DIR / "debian"
UBUNTU     = ROOTFS_DIR / "ubuntu"
USERS_DB   = BASE_DIR / ".users.json"

DISTROS = {"debian": DEBIAN, "ubuntu": UBUNTU}

APP_PREFS_FILE   = BASE_DIR / ".app_prefs.json"
PYPROOT_BIN_DIR  = BASE_DIR / "pyproot" / "binaries"
GITHUB_API       = "https://api.github.com/repos/yaso09/devstick/releases/latest"


# ═══════════════════════════════════════════════════════════════════════════════
# FILE-CATEGORY TABLES
# ═══════════════════════════════════════════════════════════════════════════════

EXT_CATEGORY = {
    "txt": "text", "md": "text", "rst": "text", "log": "text", "json": "text",
    "xml": "text", "yaml": "text", "yml": "text", "toml": "text", "ini": "text",
    "cfg": "text", "conf": "text", "sh": "text", "py": "text", "js": "text",
    "ts": "text", "c": "text", "cpp": "text", "h": "text", "rs": "text",
    "go": "text", "rb": "text", "php": "text", "html": "text", "css": "text",
    "png": "image", "jpg": "image", "jpeg": "image", "gif": "image",
    "bmp": "image", "svg": "image", "webp": "image", "ico": "image",
    "mp4": "video", "mkv": "video", "avi": "video", "mov": "video",
    "webm": "video", "flv": "video",
    "mp3": "audio", "wav": "audio", "ogg": "audio", "flac": "audio",
    "aac": "audio", "m4a": "audio",
    "zip": "archive", "tar": "archive", "gz": "archive", "bz2": "archive",
    "xz": "archive", "7z": "archive", "rar": "archive",
    "pdf": "pdf",
}

CATEGORY_ICONS = {
    "text":    "[TXT]",
    "image":   "[IMG]",
    "video":   "[VID]",
    "audio":   "[AUD]",
    "archive": "[ARC]",
    "pdf":     "[PDF]",
    "dir":     "[DIR]",
    "exec":    "[EXE]",
    "unknown": "[???]",
}

DEFAULT_APP_SUGGESTIONS = {
    "text":    ["nano", "vim", "cat", "less"],
    "image":   ["feh", "eog", "display", "xdg-open"],
    "video":   ["mpv", "vlc", "ffplay", "xdg-open"],
    "audio":   ["mpv", "aplay", "xdg-open"],
    "archive": ["file-roller", "xdg-open"],
    "pdf":     ["evince", "okular", "xdg-open"],
    "exec":    ["bash", "sh"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# RETRO COLOR PALETTE
# ═══════════════════════════════════════════════════════════════════════════════

_GREEN  = "#00ff41"
_AMBER  = "#ffb000"
_DIM    = "#005500"
_BG     = "#0a0a0a"
_SURF   = "#111111"
_RED    = "#ff3333"

RETRO_CSS = f"""
Screen {{
    background: {_BG};
    color: {_GREEN};
}}
ClockBar {{
    background: {_SURF};
    color: {_AMBER};
    text-align: center;
    height: 1;
    border-bottom: solid {_DIM};
    text-style: bold;
    padding: 0 2;
}}
DataTable {{
    background: {_BG};
    color: {_GREEN};
}}
DataTable > .datatable--header {{
    color: {_AMBER};
    text-style: bold;
    background: {_SURF};
}}
DataTable > .datatable--cursor {{
    background: {_DIM};
    color: {_GREEN};
    text-style: bold;
}}
DataTable > .datatable--odd-row {{
    background: {_BG};
}}
DataTable > .datatable--even-row {{
    background: {_SURF};
}}
Input {{
    background: {_BG};
    color: {_GREEN};
    border: solid {_GREEN};
}}
Input:focus {{
    border: solid {_AMBER};
}}
Switch {{
    background: {_BG};
}}
Label {{
    color: {_GREEN};
}}
.KeysBar {{
    background: {_SURF};
    color: {_AMBER};
    text-align: center;
    height: 1;
    border-top: solid {_DIM};
    text-style: bold;
    padding: 0 1;
}}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# ── BACKEND: ported from main.py ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

# ── System ────────────────────────────────────────────────────────────────────

def _arch() -> str:
    return platform.machine()


def _sanitize_env():
    os.environ.pop("SHELL", None)
    os.environ["SHELL"] = "/bin/bash"


def _get_rootfs(name: str) -> Path:
    if name in DISTROS:
        return DISTROS[name]
    raise RuntimeError(f"Unknown distro: '{name}'  (available: debian, ubuntu)")


def _resolve_shell(rootfs: Path) -> str:
    for shell in ("/bin/bash", "/bin/sh"):
        if (rootfs / shell.lstrip("/")).exists():
            return shell
    raise RuntimeError("No valid shell found in rootfs")


# ── proot binary ─────────────────────────────────────────────────────────────

def _inject_proot_to_path():
    if not PYPROOT_BIN_DIR.exists():
        return
    a           = _arch()
    android_bin = PYPROOT_BIN_DIR / f"proot-{a}-android"
    desktop_bin = PYPROOT_BIN_DIR / f"proot-{a}"
    proot_link  = PYPROOT_BIN_DIR / "proot"

    source = next((b for b in [android_bin, desktop_bin] if b.exists()), None)
    if source and not proot_link.exists():
        try:
            proot_link.symlink_to(source)
        except OSError:
            shutil.copy2(str(source), str(proot_link))
            proot_link.chmod(proot_link.stat().st_mode | 0o111)

    current = os.environ.get("PATH", "")
    if str(PYPROOT_BIN_DIR) not in current.split(":"):
        os.environ["PATH"] = str(PYPROOT_BIN_DIR) + ":" + current


# ── proot runner ─────────────────────────────────────────────────────────────

def _proot_run(rootfs: Path, cmd: list, fake_root: bool = False) -> subprocess.CompletedProcess:
    if not _HAS_PYPROOT:
        raise RuntimeError("pyproot is not installed (pip install pyproot)")
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


# ── password hashing ─────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """Return a SHA-512 crypt(3) hash compatible with /etc/shadow."""
    try:
        from passlib.hash import sha512_crypt          # type: ignore
        return sha512_crypt.using(rounds=5000).hash(password)
    except ImportError:
        pass
    try:
        import crypt  # noqa
        return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
    except ImportError:
        pass
    result = subprocess.run(
        ["openssl", "passwd", "-6", "-stdin"],
        input=password.encode(),
        capture_output=True,
    )
    if result.returncode == 0:
        return result.stdout.decode().strip()
    raise RuntimeError("Cannot hash password: install passlib  (pip install passlib)")


# ── user-db helpers ───────────────────────────────────────────────────────────

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
    return max((u for u in uids if u >= 1000), default=999) + 1


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


def _manual_create_user(rootfs: Path, username: str, password: str, is_root: bool):
    """Edit /etc/passwd, /etc/shadow, /etc/group directly (proot-safe fallback)."""
    uid = _next_uid(rootfs)
    gid = uid

    passwd_line = f"{username}:x:{uid}:{gid}::/home/{username}:/bin/bash\n"
    _append_if_missing(rootfs / "etc/passwd", username + ":", passwd_line)

    hashed      = _hash_password(password)
    shadow_line = f"{username}:{hashed}:19000:0:99999:7:::\n"
    _append_if_missing(rootfs / "etc/shadow", username + ":", shadow_line)

    group_file  = rootfs / "etc/group"
    group_line  = f"{username}:x:{gid}:\n"
    _append_if_missing(group_file, username + ":", group_line)

    if is_root:
        _add_user_to_group(group_file, "sudo", username)

    home = rootfs / "home" / username
    home.mkdir(parents=True, exist_ok=True)


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
                    members    = [m for m in parts[-1].split(",") if m != username]
                    parts[-1]  = ",".join(members)
                    line       = ":".join(parts) + "\n"
                cleaned.append(line)
            filtered = cleaned

        f.write_text("".join(filtered))

    if not keep_home:
        home = rootfs / "home" / username
        if home.exists():
            shutil.rmtree(str(home))


# ── register user ─────────────────────────────────────────────────────────────

def backend_register_user(distro: str, username: str, password: str, is_root: bool = False):
    rootfs = _get_rootfs(distro)
    if not rootfs.exists():
        raise RuntimeError("Rootfs not installed. Run install first.")

    users = load_users()
    if username in users.get(distro, {}):
        raise RuntimeError(f"User '{username}' already exists in {distro}")

    shell = _resolve_shell(rootfs)

    if is_root:
        sudo_block = (
            f"usermod -aG sudo {username}\n"
            f"mkdir -p /etc/sudoers.d\n"
            f"echo '%sudo ALL=(ALL:ALL) ALL' > /etc/sudoers.d/devstick\n"
            f"chmod 440 /etc/sudoers.d/devstick"
        ) if (rootfs / "etc/debian_version").exists() else f"usermod -aG wheel {username}"
    else:
        sudo_block = ""

    script = (
        "#!/bin/sh\nset -e\n"
        "if command -v apt >/dev/null 2>&1; then\n"
        "    apt-get update -qq\n"
        "    DEBIAN_FRONTEND=noninteractive apt-get install -y passwd login sudo bash coreutils\n"
        "elif command -v apk >/dev/null 2>&1; then\n"
        "    apk add shadow sudo bash\n"
        "elif command -v pacman >/dev/null 2>&1; then\n"
        "    pacman -Sy --noconfirm shadow sudo bash\n"
        "elif command -v dnf >/dev/null 2>&1; then\n"
        "    dnf install -y shadow-utils sudo bash\n"
        "fi\n"
        f"useradd -m -s {shell} {username}\n"
        f"echo '{username}:{password}' | chpasswd\n"
        f"{sudo_block}\n"
    )
    script_path = rootfs / "tmp" / "_devstick_register.sh"
    script_path.write_text(script)
    script_path.chmod(0o700)

    success = False
    try:
        if _is_termux():
            _inject_proot_to_path()
            result = _run_distro_temp(
                rootfs=str(rootfs),
                user=None,
                command=[shell, "/tmp/_devstick_register.sh"],
            )
        else:
            result = _proot_run(rootfs, [shell, "/tmp/_devstick_register.sh"], fake_root=True)

        if result is not None and result.returncode == 0:
            success = True
    except Exception:
        pass
    finally:
        if script_path.exists():
            script_path.unlink()

    if not success:
        _manual_create_user(rootfs, username, password, is_root)

    users.setdefault(distro, {})[username] = {"root": is_root}
    save_users(users)


# ── delete user ───────────────────────────────────────────────────────────────

def backend_delete_user(distro: str, username: str, keep_home: bool = False):
    rootfs = _get_rootfs(distro)
    if not rootfs.exists():
        raise RuntimeError("Rootfs not found.")

    users = load_users()
    if username not in users.get(distro, {}):
        raise RuntimeError(f"User '{username}' not found in .users.json for {distro}")

    shell       = _resolve_shell(rootfs)
    flag        = "" if keep_home else "-r"
    script      = f"#!/bin/sh\nuserdel {flag} {username} 2>/dev/null || true\n"
    script_path = rootfs / "tmp" / "_devstick_delete.sh"
    script_path.write_text(script)
    script_path.chmod(0o700)

    try:
        if _is_termux():
            _inject_proot_to_path()
            _run_distro_temp(
                rootfs=str(rootfs),
                user=None,
                command=[shell, "/tmp/_devstick_delete.sh"],
            )
        else:
            _proot_run(rootfs, [shell, "/tmp/_devstick_delete.sh"], fake_root=True)
    except Exception:
        pass
    finally:
        if script_path.exists():
            script_path.unlink()

    _manual_delete_user(rootfs, username, keep_home)
    users[distro].pop(username, None)
    save_users(users)


# ── run distro ────────────────────────────────────────────────────────────────

def backend_run_distro(name: str, user: str | None = None, command: list | None = None):
    rootfs = _get_rootfs(name)
    if not rootfs.exists():
        raise RuntimeError("Rootfs not found. Install the distro first.")

    _sanitize_env()
    shell = _resolve_shell(rootfs)

    if _is_termux():
        _inject_proot_to_path()
        _run_distro_temp(rootfs=rootfs, user=user, command=command)
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


# ── install ───────────────────────────────────────────────────────────────────

def _detect_pkg_manager() -> str | None:
    for m in ["apt", "dnf", "apk", "pacman", "pkg"]:
        if shutil.which(m):
            return m
    return None


def _install_dependencies():
    pm = _detect_pkg_manager()
    if not pm:
        raise RuntimeError("No package manager found")
    cmds = {
        "pkg":    ["pkg", "install", "-y", "debootstrap", "proot"],
        "apt":    ["sudo", "apt", "install", "-y", "debootstrap", "proot"],
        "dnf":    ["sudo", "dnf", "install", "-y", "debootstrap", "proot"],
        "pacman": ["sudo", "pacman", "-S", "--noconfirm", "debootstrap", "proot"],
        "apk":    ["sudo", "apk", "add", "debootstrap", "proot"],
    }
    subprocess.run(cmds.get(pm, cmds["apt"]), check=True)


def _debootstrap(suite: str, target: Path, mirror: str, reinstall: bool):
    if target.exists():
        if reinstall:
            subprocess.run(["rm", "-rf", str(target)], check=True)
        else:
            return  # already installed, skip silently
    cmd = ["debootstrap", "--variant=minbase", suite, str(target), mirror]
    if not _is_termux():
        cmd.insert(0, "sudo")
    subprocess.run(cmd, check=True)


def backend_install_distro(name: str, reinstall: bool = False):
    _install_dependencies()
    ROOTFS_DIR.mkdir(exist_ok=True)
    if name == "debian":
        _debootstrap("stable", DEBIAN, "http://deb.debian.org/debian", reinstall)
    elif name == "ubuntu":
        _debootstrap("jammy",  UBUNTU, "http://archive.ubuntu.com/ubuntu", reinstall)
    else:
        raise RuntimeError(f"Unknown distro: {name}")


# ═══════════════════════════════════════════════════════════════════════════════
# TUI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def load_users() -> dict:
    if USERS_DB.exists():
        return json.loads(USERS_DB.read_text())
    return {}

def save_users(data: dict):
    USERS_DB.write_text(json.dumps(data, indent=2))

def load_app_prefs() -> dict:
    if APP_PREFS_FILE.exists():
        return json.loads(APP_PREFS_FILE.read_text())
    return {}

def save_app_prefs(data: dict):
    APP_PREFS_FILE.write_text(json.dumps(data, indent=2))

def file_category(path: Path) -> str:
    if path.is_dir():
        return "dir"
    ext = path.suffix.lstrip(".").lower()
    if ext in EXT_CATEGORY:
        return EXT_CATEGORY[ext]
    try:
        mode = path.stat().st_mode
        if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            return "exec"
    except OSError:
        pass
    return "unknown"

def human_size(size: int) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.1f}P"

def distro_installed(name: str) -> bool:
    return DISTROS[name].exists()

def user_home_path(rootfs: Path, username: str, root_login: bool) -> Path:
    candidate = (
        rootfs / "root"
        if (root_login or username == "root")
        else rootfs / "home" / username
    )
    return candidate if candidate.exists() else rootfs


# ═══════════════════════════════════════════════════════════════════════════════
# WIDGET: ClockBar
# ═══════════════════════════════════════════════════════════════════════════════

class ClockBar(Static):
    """Self-updating date/time bar; ticks every second."""

    def on_mount(self) -> None:
        self._tick()
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        now = datetime.now()
        self.update(
            f"{now.strftime('%a, %d %b %Y')}    |    {now.strftime('%H:%M:%S')}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: New File
# ═══════════════════════════════════════════════════════════════════════════════

class NewFileModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "cancel",  "Cancel"),
        Binding("ctrl+s", "confirm", "Create"),
    ]
    CSS = f"""
    NewFileModal {{ align: center middle; }}
    NewFileModal > Vertical {{
        background: {_SURF}; border: double {_GREEN};
        width: 55; height: auto; padding: 1 2;
    }}
    NewFileModal .modal-title {{ text-align: center; text-style: bold; color: {_AMBER}; margin-bottom: 1; }}
    NewFileModal .modal-hint  {{ text-align: center; color: {_DIM}; margin-top: 2; }}
    NewFileModal Label {{ color: {_GREEN}; margin-top: 1; }}
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[ CREATE NEW FILE ]", classes="modal-title")
            yield Label("Filename:")
            yield Input(placeholder="example.txt", id="nf_name")
            yield Label("[Ctrl+S] Create    [Esc] Cancel", classes="modal-hint")

    def action_cancel(self): self.dismiss(None)
    def action_confirm(self):
        name = self.query_one("#nf_name", Input).value.strip()
        if not name:
            self.notify("Filename cannot be empty!", severity="error"); return
        if "/" in name or "\\" in name:
            self.notify("Filename cannot contain path separators!", severity="error"); return
        self.dismiss(name)


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Edit Default App
# ═══════════════════════════════════════════════════════════════════════════════

class EditAppModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "cancel",  "Cancel"),
        Binding("ctrl+s", "confirm", "Save"),
    ]
    CSS = f"""
    EditAppModal {{ align: center middle; }}
    EditAppModal > Vertical {{
        background: {_SURF}; border: double {_GREEN};
        width: 62; height: auto; padding: 1 2;
    }}
    EditAppModal .modal-title {{ text-align: center; text-style: bold; color: {_AMBER}; margin-bottom: 1; }}
    EditAppModal .modal-hint  {{ text-align: center; color: {_DIM}; margin-top: 2; }}
    EditAppModal Label {{ color: {_GREEN}; margin-top: 1; }}
    """

    def __init__(self, category: str, current: str):
        super().__init__()
        self.category = category
        self.current  = current

    def compose(self) -> ComposeResult:
        suggestions = DEFAULT_APP_SUGGESTIONS.get(self.category, [])
        with Vertical():
            yield Label(f"[ SET DEFAULT APP: {self.category.upper()} ]", classes="modal-title")
            yield Label("Application  (leave empty to clear):")
            yield Input(value=self.current, placeholder="e.g. vim", id="edit_app")
            if suggestions:
                yield Label(f"Suggestions: {', '.join(suggestions)}")
            yield Label("[Ctrl+S] Save    [Esc] Cancel", classes="modal-hint")

    def action_cancel(self): self.dismiss(None)
    def action_confirm(self):
        self.dismiss(self.query_one("#edit_app", Input).value.strip())


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Install Distro
# ═══════════════════════════════════════════════════════════════════════════════

class InstallDistroModal(ModalScreen):
    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel",  "No"),
        Binding("escape", "cancel", "Cancel"),
    ]
    CSS = f"""
    InstallDistroModal {{ align: center middle; }}
    InstallDistroModal > Vertical {{
        background: {_SURF}; border: double {_GREEN};
        width: 55; height: auto; padding: 1 2;
    }}
    InstallDistroModal .modal-title {{ text-align: center; text-style: bold; color: {_AMBER}; margin-bottom: 1; }}
    InstallDistroModal .modal-hint  {{ text-align: center; color: {_DIM}; margin-top: 2; }}
    InstallDistroModal Label {{ color: {_GREEN}; }}
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[ INSTALL: {self.distro.upper()} ]", classes="modal-title")
            yield Label(f"[bold]{self.distro}[/bold] is not installed.\nDo you want to install it now?")
            yield Label("[Y] Yes    [N] No    [Esc] Cancel", classes="modal-hint")

    def action_cancel(self):  self.dismiss(False)
    def action_confirm(self): self.dismiss(True)


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Remove Distro
# ═══════════════════════════════════════════════════════════════════════════════

class RemoveDistroModal(ModalScreen):
    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel",  "No"),
        Binding("escape", "cancel", "Cancel"),
    ]
    CSS = f"""
    RemoveDistroModal {{ align: center middle; }}
    RemoveDistroModal > Vertical {{
        background: {_SURF}; border: double {_RED};
        width: 55; height: auto; padding: 1 2;
    }}
    RemoveDistroModal .modal-title {{ text-align: center; text-style: bold; color: {_RED}; margin-bottom: 1; }}
    RemoveDistroModal .modal-hint  {{ text-align: center; color: {_DIM}; margin-top: 2; }}
    RemoveDistroModal Label {{ color: {_GREEN}; }}
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[ REMOVE: {self.distro.upper()} ]", classes="modal-title")
            yield Label(f"[bold red]{self.distro}[/bold red] and ALL its data will be deleted!\nAre you sure?")
            yield Label("[Y] Yes    [N] No    [Esc] Cancel", classes="modal-hint")

    def action_cancel(self):  self.dismiss(False)
    def action_confirm(self): self.dismiss(True)


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Register User
# ═══════════════════════════════════════════════════════════════════════════════

class RegisterUserModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "cancel",  "Cancel"),
        Binding("ctrl+s", "confirm", "Create"),
    ]
    CSS = f"""
    RegisterUserModal {{ align: center middle; }}
    RegisterUserModal > Vertical {{
        background: {_SURF}; border: double {_GREEN};
        width: 60; height: auto; padding: 1 2;
    }}
    RegisterUserModal .modal-title {{ text-align: center; text-style: bold; color: {_AMBER}; margin-bottom: 1; }}
    RegisterUserModal .modal-hint  {{ text-align: center; color: {_DIM}; margin-top: 2; }}
    RegisterUserModal Label {{ margin-top: 1; color: {_GREEN}; }}
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[ NEW USER -- {self.distro.upper()} ]", classes="modal-title")
            yield Label("Username:")
            yield Input(placeholder="username", id="reg_username")
            yield Label("Password:")
            yield Input(placeholder="password", password=True, id="reg_password")
            yield Label("Confirm password:")
            yield Input(placeholder="password again", password=True, id="reg_password2")
            with Horizontal():
                yield Label("Grant sudo:  ")
                yield Switch(id="reg_sudo")
            yield Label("[Tab] Navigate    [Ctrl+S] Create    [Esc] Cancel", classes="modal-hint")

    def action_cancel(self): self.dismiss(None)
    def action_confirm(self):
        username  = self.query_one("#reg_username",  Input).value.strip()
        password  = self.query_one("#reg_password",  Input).value
        password2 = self.query_one("#reg_password2", Input).value
        sudo      = self.query_one("#reg_sudo",      Switch).value
        if not username:
            self.notify("Username cannot be empty!", severity="error"); return
        if not password:
            self.notify("Password cannot be empty!", severity="error"); return
        if password != password2:
            self.notify("Passwords do not match!", severity="error"); return
        self.dismiss({"username": username, "password": password, "sudo": sudo})


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Delete User
# ═══════════════════════════════════════════════════════════════════════════════

class DeleteUserModal(ModalScreen):
    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel",  "No"),
        Binding("escape", "cancel", "Cancel"),
    ]
    CSS = f"""
    DeleteUserModal {{ align: center middle; }}
    DeleteUserModal > Vertical {{
        background: {_SURF}; border: double {_RED};
        width: 55; height: auto; padding: 1 2;
    }}
    DeleteUserModal .modal-title {{ text-align: center; text-style: bold; color: {_RED}; margin-bottom: 1; }}
    DeleteUserModal .modal-hint  {{ text-align: center; color: {_DIM}; margin-top: 2; }}
    DeleteUserModal Label {{ color: {_GREEN}; }}
    """

    def __init__(self, distro: str, username: str):
        super().__init__()
        self.distro   = distro
        self.username = username

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[ DELETE USER -- {self.distro.upper()} ]", classes="modal-title")
            yield Label(f"[bold]{self.username}[/bold] will be deleted. Are you sure?")
            with Horizontal():
                yield Label("Keep home directory:  ")
                yield Switch(id="del_keep_home")
            yield Label("[Y] Yes    [N] No    [Esc] Cancel", classes="modal-hint")

    def action_cancel(self): self.dismiss(None)
    def action_confirm(self):
        self.dismiss({"keep_home": self.query_one("#del_keep_home", Switch).value})


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Open File
# ═══════════════════════════════════════════════════════════════════════════════

class OpenFileModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "cancel",  "Cancel"),
        Binding("ctrl+s", "confirm", "Open"),
    ]
    CSS = f"""
    OpenFileModal {{ align: center middle; }}
    OpenFileModal > Vertical {{
        background: {_SURF}; border: double {_GREEN};
        width: 60; height: auto; padding: 1 2;
    }}
    OpenFileModal .modal-title {{ text-align: center; text-style: bold; color: {_AMBER}; margin-bottom: 1; }}
    OpenFileModal .modal-hint  {{ text-align: center; color: {_DIM}; margin-top: 1; }}
    OpenFileModal Label {{ color: {_GREEN}; margin-top: 1; }}
    """

    def __init__(self, filepath: Path, category: str, prefs: dict):
        super().__init__()
        self.filepath = filepath
        self.category = category
        self.prefs    = prefs

    def compose(self) -> ComposeResult:
        default_app = self.prefs.get(self.category, "")
        suggestions = DEFAULT_APP_SUGGESTIONS.get(self.category, [])
        icon        = CATEGORY_ICONS.get(self.category, "[???]")
        with Vertical():
            yield Label(f"[ OPEN FILE -- {icon} {self.category.upper()} ]", classes="modal-title")
            yield Label(f"[dim]{self.filepath.name}[/dim]")
            yield Label("Application:")
            yield Input(value=default_app, placeholder="app name", id="open_app")
            if suggestions:
                yield Label(f"Suggestions: {', '.join(suggestions)}")
            yield Label("[Ctrl+S] Open    [Esc] Cancel", classes="modal-hint")

    def action_cancel(self): self.dismiss(None)
    def action_confirm(self):
        app_name = self.query_one("#open_app", Input).value.strip()
        if not app_name:
            self.notify("Application name cannot be empty!", severity="error"); return
        self.dismiss(app_name)


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Generic Confirm
# ═══════════════════════════════════════════════════════════════════════════════

class ConfirmModal(ModalScreen):
    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel",  "No"),
        Binding("escape", "cancel", "Cancel"),
    ]
    CSS = f"""
    ConfirmModal {{ align: center middle; }}
    ConfirmModal > Vertical {{
        background: {_SURF}; border: double {_AMBER};
        width: 55; height: auto; padding: 1 2;
    }}
    ConfirmModal .modal-title {{ text-align: center; text-style: bold; color: {_AMBER}; margin-bottom: 1; }}
    ConfirmModal .modal-hint  {{ text-align: center; color: {_DIM}; margin-top: 2; }}
    ConfirmModal Label {{ color: {_GREEN}; }}
    """

    def __init__(self, title: str, message: str):
        super().__init__()
        self._title   = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title,   classes="modal-title")
            yield Label(self._message)
            yield Label("[Y] Yes    [N] No    [Esc] Cancel", classes="modal-hint")

    def action_cancel(self):  self.dismiss(False)
    def action_confirm(self): self.dismiss(True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 0: Splash
# ═══════════════════════════════════════════════════════════════════════════════

_SPLASH_BANNER = (
    "+--------------------------------------------------+\n"
    "|                                                  |\n"
    "|   ____  _____   ____  _____ ______  _____ _  _  |\n"
    r"|  |  _ \| ____| |  _ \| ____|_   _ ||_   _| || | |" + "\n"
    "|  | | | | |_    | | | |  _|   | | | | | | | || | |\n"
    r"|  | |_| | |__   | |_| | |___  | | | | | | | || | |" + "\n"
    r"|  |____/|____|  |____/|_____| |_|_| |_| |_| |_|  |" + "\n"
    "|                                                  |\n"
    "|            *** DEVSTICK TUI v1.0 ***             |\n"
    "|                                                  |\n"
    "+--------------------------------------------------+"
)


class SplashScreen(Screen):
    CSS = f"""
    SplashScreen {{ align: center middle; background: {_BG}; }}
    #splash-box {{
        width: 56; height: auto; padding: 1 2;
        border: double {_GREEN}; background: {_SURF};
    }}
    #splash-banner {{ text-align: center; color: {_GREEN}; text-style: bold; width: 100%; }}
    #splash-sub    {{ text-align: center; color: {_DIM};   margin-top: 1; width: 100%; }}
    #splash-hint   {{ text-align: center; color: {_AMBER}; margin-top: 1; width: 100%; }}
    """

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                with Vertical(id="splash-box"):
                    yield Static(_SPLASH_BANNER, id="splash-banner")
                    yield Static("by Yasir Eymen Kayabasi", id="splash-sub")
                    yield Static("[ Initializing... ]", id="splash-hint")

    def on_mount(self):
        self.set_timer(2.0, lambda: self.app.push_screen(DistroScreen()))


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 1: Distro Selection
# ═══════════════════════════════════════════════════════════════════════════════

class DistroScreen(Screen):
    BINDINGS = [
        Binding("q", "app.quit",  "Quit"),
        Binding("i", "install",   "Install"),
        Binding("d", "remove",    "Remove"),
        Binding("r", "refresh",   "Refresh"),
        Binding("s", "settings",  "Settings"),
    ]
    CSS = f"""
    DistroScreen {{ layout: vertical; background: {_BG}; }}
    #distro-screen-title {{
        background: {_SURF}; color: {_AMBER};
        text-align: center; text-style: bold;
        height: 3; content-align: center middle; padding: 0 2;
        border-bottom: solid {_GREEN};
    }}
    #distro-list   {{ height: 1fr; margin: 1 2; border: solid {_GREEN}; }}
    #distro-status {{ background: {_SURF}; height: 1; padding: 0 1; border-top: solid {_DIM}; color: {_DIM}; }}
    """

    def compose(self) -> ComposeResult:
        yield ClockBar()
        yield Static("+--[ DEVSTICK :: SELECT DISTRO ]--+", id="distro-screen-title")
        yield DataTable(id="distro-list", cursor_type="row", zebra_stripes=True)
        yield Static("", id="distro-status")
        yield Static(
            "[bold]Enter[/bold] Open  [bold]I[/bold] Install  [bold]D[/bold] Remove  "
            "[bold]R[/bold] Refresh  [bold]S[/bold] Settings  [bold]Q[/bold] Quit",
            classes="KeysBar",
        )

    def on_mount(self):
        t = self.query_one("#distro-list", DataTable)
        t.add_columns("Distro", "Status", "Location")
        self._refresh()

    def _refresh(self):
        t = self.query_one("#distro-list", DataTable)
        t.clear()
        for name, path in DISTROS.items():
            installed = path.exists()
            badge = (
                "[bold green][ INSTALLED     ][/bold green]"
                if installed else
                "[bold red][ NOT INSTALLED ][/bold red]"
            )
            t.add_row(name, badge, str(path) if installed else "---", key=name)

    def _status(self, msg: str):
        self.query_one("#distro-status", Static).update(msg)

    def _get_cursor_key(self) -> str | None:
        t    = self.query_one("#distro-list", DataTable)
        keys = list(DISTROS.keys())
        if t.cursor_row < 0 or t.cursor_row >= len(keys):
            return None
        return keys[t.cursor_row]

    def action_install(self):
        name = self._get_cursor_key()
        if not name:
            self.notify("Select a distro first.", severity="warning"); return
        if distro_installed(name):
            self.notify(f"{name} is already installed.", severity="warning"); return
        self.app.push_screen(InstallDistroModal(name),
                             lambda yes: self._do_install(name) if yes else None)

    def action_remove(self):
        name = self._get_cursor_key()
        if not name:
            self.notify("Select a distro first.", severity="warning"); return
        if not distro_installed(name):
            self.notify(f"{name} is not installed.", severity="warning"); return
        self.app.push_screen(RemoveDistroModal(name),
                             lambda yes: self._do_remove(name) if yes else None)

    def action_refresh(self):
        self._refresh(); self._status("Refreshed.")

    def action_settings(self):
        self.app.push_screen(SettingsScreen())

    @on(DataTable.RowSelected, "#distro-list")
    def row_selected(self, event: DataTable.RowSelected):
        if not (event.row_key and event.row_key.value): return
        name = event.row_key.value
        if not distro_installed(name):
            self.notify(f"{name} is not installed! Press [I] to install.", severity="warning")
            return
        self.app.push_screen(UsersScreen(distro=name))

    @work(thread=True)
    def _do_install(self, name: str):
        self.call_from_thread(self._status, f"Installing {name} (this may take a while)...")
        try:
            backend_install_distro(name)
            self.call_from_thread(self.notify, f"[OK] {name} installed!")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"{name} installed successfully.")
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")
            self.call_from_thread(self._status, "Installation failed.")

    @work(thread=True)
    def _do_remove(self, name: str):
        self.call_from_thread(self._status, f"Removing {name}...")
        try:
            shutil.rmtree(str(DISTROS[name]))
            self.call_from_thread(self.notify, f"[OK] {name} removed!")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"{name} removed.")
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 1b: Settings
# ═══════════════════════════════════════════════════════════════════════════════

class SettingsScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back",        "Back"),
        Binding("r",      "reset_selected", "Reset to Default"),
    ]
    CSS = f"""
    SettingsScreen {{ layout: vertical; background: {_BG}; }}
    #settings-screen-title {{
        background: {_SURF}; color: {_AMBER};
        text-align: center; text-style: bold;
        height: 3; content-align: center middle; padding: 0 2;
        border-bottom: solid {_GREEN};
    }}
    #settings-table   {{ height: 1fr; margin: 1 2; border: solid {_GREEN}; }}
    #settings-status  {{ background: {_SURF}; height: 1; padding: 0 1; border-top: solid {_DIM}; color: {_DIM}; }}
    """

    def compose(self) -> ComposeResult:
        yield ClockBar()
        yield Static("+--[ DEVSTICK :: SETTINGS :: DEFAULT APPLICATIONS ]--+", id="settings-screen-title")
        yield DataTable(id="settings-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="settings-status")
        yield Static(
            "[bold]Enter[/bold] Edit App  [bold]R[/bold] Reset to Default  [bold]Esc[/bold] Back",
            classes="KeysBar",
        )

    def on_mount(self):
        t = self.query_one("#settings-table", DataTable)
        t.add_columns("Category", "Type", "Current App", "Suggestions")
        self._refresh()

    def _refresh(self):
        t = self.query_one("#settings-table", DataTable)
        t.clear()
        prefs = load_app_prefs()
        for cat in sorted(DEFAULT_APP_SUGGESTIONS.keys()):
            icon    = CATEGORY_ICONS.get(cat, "[???]")
            current = prefs.get(cat, "")
            suggs   = ", ".join(DEFAULT_APP_SUGGESTIONS.get(cat, []))
            display = f"[bold green]{current}[/bold green]" if current else "[dim](not set)[/dim]"
            t.add_row(cat, icon, display, suggs, key=cat)

    def _status(self, msg: str):
        self.query_one("#settings-status", Static).update(msg)

    def _get_cursor_key(self) -> str | None:
        t = self.query_one("#settings-table", DataTable)
        try:
            return t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value
        except Exception:
            return None

    def action_go_back(self):
        self.app.pop_screen()

    def action_reset_selected(self):
        cat = self._get_cursor_key()
        if not cat: return
        prefs = load_app_prefs()
        if cat in prefs:
            del prefs[cat]; save_app_prefs(prefs)
            self._refresh(); self._status(f"Reset: {cat}")
        else:
            self._status(f"{cat} already using default.")

    @on(DataTable.RowSelected, "#settings-table")
    def row_selected(self, event: DataTable.RowSelected):
        if not (event.row_key and event.row_key.value): return
        cat     = event.row_key.value
        current = load_app_prefs().get(cat, "")

        def on_result(val):
            if val is None: return
            prefs = load_app_prefs()
            if val:
                prefs[cat] = val
            else:
                prefs.pop(cat, None)
            save_app_prefs(prefs)
            self._refresh()
            self._status(f"[OK] {cat} -> '{val}'" if val else f"[OK] {cat} cleared")

        self.app.push_screen(EditAppModal(cat, current), on_result)


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 2: Users
# ═══════════════════════════════════════════════════════════════════════════════

_ROOT_KEY  = "__root__"
_EMPTY_KEY = "__empty__"


class UsersScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back",     "Back"),
        Binding("n",      "new_user",    "New User"),
        Binding("d",      "delete_user", "Delete User"),
    ]
    CSS = f"""
    UsersScreen {{ layout: vertical; background: {_BG}; }}
    #users-screen-title {{
        background: {_SURF}; color: {_AMBER};
        text-align: center; text-style: bold;
        height: 3; content-align: center middle; padding: 0 2;
        border-bottom: solid {_GREEN};
    }}
    #users-table  {{ height: 1fr; margin: 1 2; border: solid {_GREEN}; }}
    #users-status {{ background: {_SURF}; height: 1; padding: 0 1; border-top: solid {_DIM}; color: {_DIM}; }}
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        yield ClockBar()
        yield Static(f"+--[ DEVSTICK :: USERS :: {self.distro.upper()} ]--+", id="users-screen-title")
        yield DataTable(id="users-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="users-status")
        yield Static(
            "[bold]Enter[/bold] Login  [bold]N[/bold] New User  "
            "[bold]D[/bold] Delete User  [bold]Esc[/bold] Back",
            classes="KeysBar",
        )

    def on_mount(self):
        t = self.query_one("#users-table", DataTable)
        t.add_columns("Username", "Role", "Home Directory")
        self._refresh()

    def _refresh(self):
        t = self.query_one("#users-table", DataTable)
        t.clear()
        t.add_row(
            "[bold yellow]root[/bold yellow]",
            "[bold red]ROOT  (passwordless  |  -0 -w /root)[/bold red]",
            "/root",
            key=_ROOT_KEY,
        )
        distro_users = load_users().get(self.distro, {})
        if not distro_users:
            t.add_row("[dim]-- no users registered --[/dim]", "", "", key=_EMPTY_KEY)
        else:
            for uname, meta in distro_users.items():
                role = "[yellow]sudo[/yellow]" if meta.get("root") else "normal"
                t.add_row(uname, role, f"/home/{uname}", key=uname)

    def _status(self, msg: str):
        self.query_one("#users-status", Static).update(msg)

    def _get_cursor_key(self) -> str | None:
        t = self.query_one("#users-table", DataTable)
        try:
            return t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value
        except Exception:
            return None

    def _login(self, key: str):
        if key == _ROOT_KEY:
            self._open_as_root()
        elif key == _EMPTY_KEY:
            self.notify("No users registered. Press [N] to add one.", severity="warning")
        else:
            self._open_fm(key)

    def _open_fm(self, uname: str):
        rootfs = DISTROS.get(self.distro)
        if rootfs and rootfs.exists():
            start = user_home_path(rootfs, uname, root_login=False)
        else:
            rootfs = start = BASE_DIR
        self.app.push_screen(FileManagerScreen(
            distro=self.distro, username=uname,
            root_path=rootfs, start_path=start, root_login=False,
        ))

    def _open_as_root(self):
        rootfs = DISTROS.get(self.distro)
        if rootfs and rootfs.exists():
            start = user_home_path(rootfs, "root", root_login=True)
        else:
            rootfs = start = BASE_DIR
        self.app.push_screen(FileManagerScreen(
            distro=self.distro, username="root",
            root_path=rootfs, start_path=start, root_login=True,
        ))

    def action_go_back(self):    self.app.pop_screen()

    def action_new_user(self):
        def on_result(result):
            if not result: return
            self._status(f"Creating: {result['username']}...")
            self._do_register_user(result["username"], result["password"], result["sudo"])
        self.app.push_screen(RegisterUserModal(self.distro), on_result)

    def action_delete_user(self):
        key = self._get_cursor_key()
        if not key or key in (_ROOT_KEY, _EMPTY_KEY):
            self.notify("Select a regular user to delete.", severity="warning"); return
        def on_result(result):
            if not result: return
            self._do_delete_user(key, result["keep_home"])
        self.app.push_screen(DeleteUserModal(self.distro, key), on_result)

    @on(DataTable.RowSelected, "#users-table")
    def row_selected(self, event: DataTable.RowSelected):
        if event.row_key and event.row_key.value:
            self._login(event.row_key.value)

    @work(thread=True)
    def _do_register_user(self, username: str, password: str, is_sudo: bool):
        try:
            backend_register_user(self.distro, username, password, is_sudo)
            self.call_from_thread(self.notify, f"[OK] User created: {username}")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"User created: {username}")
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    @work(thread=True)
    def _do_delete_user(self, username: str, keep_home: bool):
        try:
            backend_delete_user(self.distro, username, keep_home)
            self.call_from_thread(self.notify, f"[OK] User deleted: {username}")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"User deleted: {username}")
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 3: File Manager
# ═══════════════════════════════════════════════════════════════════════════════

class FileManagerScreen(Screen):
    BINDINGS = [
        Binding("escape",    "go_back",     "Back"),
        Binding("backspace", "go_up",       "Parent Dir"),
        Binding("ctrl+n",    "new_file",    "New File"),
        Binding("delete",    "delete_file", "Delete"),
        Binding("r",         "refresh",     "Refresh"),
        Binding("ctrl+r",    "run_distro",  "Run Distro"),
    ]
    CSS = f"""
    FileManagerScreen {{ layout: vertical; background: {_BG}; }}
    #fm-screen-title {{
        background: {_SURF}; color: {_AMBER};
        text-align: center; text-style: bold;
        height: 3; content-align: center middle; padding: 0 2;
        border-bottom: solid {_GREEN};
    }}
    #fm-path-bar {{ background: {_BG}; height: 1; padding: 0 1; border-bottom: solid {_DIM}; color: {_GREEN}; }}
    #fm-table    {{ height: 1fr; margin: 0 2; border: solid {_GREEN}; }}
    #fm-status   {{ background: {_SURF}; height: 1; padding: 0 1; border-top: solid {_DIM}; color: {_DIM}; }}
    """

    def __init__(
        self,
        distro: str,
        username: str,
        root_path: Path,
        root_login: bool = False,
        start_path: Path | None = None,
    ):
        super().__init__()
        self.distro     = distro
        self.username   = username
        self.root_path  = root_path
        self.root_login = root_login
        self._cur_path  = start_path if start_path is not None else root_path
        self._entries: list[Path] = []
        self._app_prefs = load_app_prefs()

    def compose(self) -> ComposeResult:
        root_tag = " [ROOT -0 -w /root]" if self.root_login else ""
        yield ClockBar()
        yield Static(
            f"+--[ FILE MANAGER :: {self.distro.upper()} / {self.username}{root_tag} ]--+",
            id="fm-screen-title",
        )
        yield Static("", id="fm-path-bar")
        yield DataTable(id="fm-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="fm-status")
        yield Static(
            "[bold]Enter[/bold] Open  [bold]Ctrl+N[/bold] New File  [bold]Del[/bold] Delete  "
            "[bold]Bksp[/bold] Up  [bold]R[/bold] Refresh  [bold]Ctrl+R[/bold] Run  [bold]Esc[/bold] Back",
            classes="KeysBar",
        )

    def on_mount(self):
        t = self.query_one("#fm-table", DataTable)
        t.add_columns("Type", "Name", "Size", "Category")
        self._refresh()

    def _refresh(self):
        try:
            rel     = self._cur_path.relative_to(ROOTFS_DIR)
            display = f">> /{rel}"
        except ValueError:
            display = f">> {self._cur_path}"
        self.query_one("#fm-path-bar", Static).update(display)

        t = self.query_one("#fm-table", DataTable)
        t.clear()
        self._entries = []

        try:
            entries = sorted(
                self._cur_path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except PermissionError:
            self._status("[ERR] Permission denied"); return

        for entry in entries:
            cat  = file_category(entry)
            icon = CATEGORY_ICONS.get(cat, "[???]")
            try:
                size = human_size(entry.stat().st_size) if entry.is_file() else "---"
            except OSError:
                size = "?"
            t.add_row(icon, entry.name, size, cat, key=str(entry))
            self._entries.append(entry)

    def _status(self, msg: str):
        self.query_one("#fm-status", Static).update(msg)

    def _open_entry(self, path: Path):
        if path.is_dir():
            self._cur_path = path; self._refresh()
        else:
            self._app_prefs = load_app_prefs()
            cat = file_category(path)
            def on_result(app_name):
                if not app_name: return
                self._status(f"Opening: {app_name} {path.name}")
                try:
                    with self.app.suspend():
                        subprocess.run([app_name, str(path)])
                except FileNotFoundError:
                    self.notify(f"'{app_name}' not found!", severity="error")
                except Exception as e:
                    self.notify(str(e), severity="error")
            self.app.push_screen(OpenFileModal(path, cat, self._app_prefs), on_result)

    def action_go_back(self):    self.app.pop_screen()
    def action_refresh(self):    self._refresh(); self._status("Refreshed.")

    def action_go_up(self):
        if self._cur_path == self.root_path:
            self._status("Already at filesystem root."); return
        self._cur_path = self._cur_path.parent; self._refresh()

    def action_new_file(self):
        def on_result(name):
            if not name: return
            new_path = self._cur_path / name
            try:
                if new_path.exists():
                    self.notify(f"'{name}' already exists!", severity="warning"); return
                new_path.touch()
                self._status(f"Created: {name}"); self._refresh()
            except Exception as e:
                self.notify(str(e), severity="error")
        self.app.push_screen(NewFileModal(), on_result)

    def action_delete_file(self):
        t = self.query_one("#fm-table", DataTable)
        if not (0 <= t.cursor_row < len(self._entries)): return
        path = self._entries[t.cursor_row]
        def on_confirm(yes):
            if not yes: return
            try:
                shutil.rmtree(str(path)) if path.is_dir() else path.unlink()
                self._status(f"Deleted: {path.name}"); self._refresh()
            except Exception as e:
                self.notify(str(e), severity="error")
        self.app.push_screen(ConfirmModal(
            "[ DELETE FILE / DIRECTORY ]",
            f"[bold]{path.name}[/bold] will be permanently removed. Are you sure?\n"
            + ("[bold red]WARNING: Directory and ALL its contents will be erased![/bold red]"
               if path.is_dir() else ""),
        ), on_confirm)

    def action_run_distro(self):
        self.notify(f"Running: {self.distro} ({self.username})...")
        with self.app.suspend():
            try:
                # root login: no --user flag → proot with fake_root=True + workdir=/root
                backend_run_distro(
                    self.distro,
                    user=None if self.root_login else self.username,
                )
            except Exception as e:
                self.notify(str(e), severity="error")

    @on(DataTable.RowSelected, "#fm-table")
    def row_selected(self, event: DataTable.RowSelected):
        if event.row_key and event.row_key.value:
            self._open_entry(Path(event.row_key.value))


# ═══════════════════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════════════════

class DevstickTUI(App):
    TITLE = "Devstick"
    CSS   = RETRO_CSS

    def on_mount(self):
        self.push_screen(SplashScreen())


if __name__ == "__main__":
    DevstickTUI().run()
