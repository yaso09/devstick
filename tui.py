#!/usr/bin/env python3
"""
devstick_tui.py — Textual-based TUI for devstick.
Usage: python devstick_tui.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import stat
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Middle, Center
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    Switch,
)

# ── devstick paths ────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent
ROOTFS_DIR = BASE_DIR / "rootfs"
DEBIAN     = ROOTFS_DIR / "debian"
UBUNTU     = ROOTFS_DIR / "ubuntu"
USERS_DB   = BASE_DIR / ".users.json"

DISTROS = {"debian": DEBIAN, "ubuntu": UBUNTU}

APP_PREFS_FILE = BASE_DIR / ".app_prefs.json"

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

# ── Retro color palette ───────────────────────────────────────────────────────
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
Header {{
    background: {_BG};
    color: {_AMBER};
    border-bottom: solid {_DIM};
    text-style: bold;
}}
Footer {{
    background: {_BG};
    color: {_DIM};
    border-top: solid {_DIM};
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
"""


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
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


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Install Distro
# ═══════════════════════════════════════════════════════════════════════════════

class InstallDistroModal(ModalScreen):
    BINDINGS = [
        Binding("y",      "confirm", "Yes"),
        Binding("n",      "cancel",  "No"),
        Binding("escape", "cancel",  "Cancel"),
    ]

    CSS = f"""
    InstallDistroModal {{ align: center middle; }}
    InstallDistroModal > Vertical {{
        background: {_SURF}; border: double {_GREEN};
        width: 55; height: auto; padding: 1 2;
    }}
    InstallDistroModal .modal-title {{
        text-align: center; text-style: bold; color: {_AMBER}; margin-bottom: 1;
    }}
    InstallDistroModal .modal-hint {{
        text-align: center; color: {_DIM}; margin-top: 2;
    }}
    InstallDistroModal Label {{ color: {_GREEN}; }}
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[ INSTALL: {self.distro.upper()} ]", classes="modal-title")
            yield Label(
                f"[bold]{self.distro}[/bold] is not installed.\n"
                "Do you want to install it now?"
            )
            yield Label("[Y] Yes    [N] No    [Esc] Cancel", classes="modal-hint")

    def action_cancel(self):  self.dismiss(False)
    def action_confirm(self): self.dismiss(True)


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Remove Distro
# ═══════════════════════════════════════════════════════════════════════════════

class RemoveDistroModal(ModalScreen):
    BINDINGS = [
        Binding("y",      "confirm", "Yes"),
        Binding("n",      "cancel",  "No"),
        Binding("escape", "cancel",  "Cancel"),
    ]

    CSS = f"""
    RemoveDistroModal {{ align: center middle; }}
    RemoveDistroModal > Vertical {{
        background: {_SURF}; border: double {_RED};
        width: 55; height: auto; padding: 1 2;
    }}
    RemoveDistroModal .modal-title {{
        text-align: center; text-style: bold; color: {_RED}; margin-bottom: 1;
    }}
    RemoveDistroModal .modal-hint {{
        text-align: center; color: {_DIM}; margin-top: 2;
    }}
    RemoveDistroModal Label {{ color: {_GREEN}; }}
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[ REMOVE: {self.distro.upper()} ]", classes="modal-title")
            yield Label(
                f"[bold red]{self.distro}[/bold red] and ALL its data will be deleted!\n"
                "Are you sure?"
            )
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
    RegisterUserModal .modal-title {{
        text-align: center; text-style: bold; color: {_AMBER}; margin-bottom: 1;
    }}
    RegisterUserModal Label {{ margin-top: 1; color: {_GREEN}; }}
    RegisterUserModal .modal-hint {{
        text-align: center; color: {_DIM}; margin-top: 2;
    }}
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
        Binding("y",      "confirm", "Yes"),
        Binding("n",      "cancel",  "No"),
        Binding("escape", "cancel",  "Cancel"),
    ]

    CSS = f"""
    DeleteUserModal {{ align: center middle; }}
    DeleteUserModal > Vertical {{
        background: {_SURF}; border: double {_RED};
        width: 55; height: auto; padding: 1 2;
    }}
    DeleteUserModal .modal-title {{
        text-align: center; text-style: bold; color: {_RED}; margin-bottom: 1;
    }}
    DeleteUserModal .modal-hint {{
        text-align: center; color: {_DIM}; margin-top: 2;
    }}
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
        keep = self.query_one("#del_keep_home", Switch).value
        self.dismiss({"keep_home": keep})


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
    OpenFileModal .modal-title {{
        text-align: center; text-style: bold; color: {_AMBER}; margin-bottom: 1;
    }}
    OpenFileModal Label {{ color: {_GREEN}; margin-top: 1; }}
    OpenFileModal .modal-hint {{
        text-align: center; color: {_DIM}; margin-top: 1;
    }}
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
        Binding("y",      "confirm", "Yes"),
        Binding("n",      "cancel",  "No"),
        Binding("escape", "cancel",  "Cancel"),
    ]

    CSS = f"""
    ConfirmModal {{ align: center middle; }}
    ConfirmModal > Vertical {{
        background: {_SURF}; border: double {_AMBER};
        width: 55; height: auto; padding: 1 2;
    }}
    ConfirmModal .modal-title {{
        text-align: center; text-style: bold; color: {_AMBER}; margin-bottom: 1;
    }}
    ConfirmModal .modal-hint {{
        text-align: center; color: {_DIM}; margin-top: 2;
    }}
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

_SPLASH_BANNER = """\
+--------------------------------------------------+
|                                                  |
|   ____  _____   ____  _____ ______  _____ _  _  |
|  |  _ \\| ____| |  _ \\| ____|_   _ ||_   _| || | |
|  | | | | |_    | | | |  _|   | | | | | | | || | |
|  | |_| | |__   | |_| | |___  | | | | | | | || | |
|  |____/|____|  |____/|_____| |_|_| |_| |_| |_|  |
|                                                  |
|            *** DEVSTICK TUI v1.0 ***             |
|                                                  |
+--------------------------------------------------+"""


class SplashScreen(Screen):
    CSS = f"""
    SplashScreen {{
        align: center middle;
        background: {_BG};
    }}
    #splash-box {{
        width: 56;
        height: auto;
        padding: 1 2;
        border: double {_GREEN};
        background: {_SURF};
    }}
    #splash-banner {{
        text-align: center;
        color: {_GREEN};
        text-style: bold;
        width: 100%;
    }}
    #splash-sub {{
        text-align: center;
        color: {_DIM};
        margin-top: 1;
        width: 100%;
    }}
    #splash-hint {{
        text-align: center;
        color: {_AMBER};
        margin-top: 1;
        width: 100%;
    }}
    """

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                with Vertical(id="splash-box"):
                    yield Static(_SPLASH_BANNER, id="splash-banner")
                    yield Static("by Yasir Eymen Kayabasi", id="splash-sub")
                    yield Static("[ Initializing... ]", id="splash-hint")

    def on_mount(self):
        self.set_timer(2.0, self._go_to_distro)

    def _go_to_distro(self):
        self.app.push_screen(DistroScreen())


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 1: Distro Selection
# ═══════════════════════════════════════════════════════════════════════════════

class DistroScreen(Screen):
    BINDINGS = [
        Binding("q",     "app.quit", "Quit"),
        Binding("r",     "refresh",  "Refresh"),
        Binding("i",     "install",  "Install"),
        Binding("d",     "remove",   "Remove"),
        # Enter is handled by DataTable.RowSelected
    ]

    CSS = f"""
    DistroScreen {{ layout: vertical; background: {_BG}; }}

    #distro-screen-title {{
        background: {_SURF}; color: {_AMBER};
        text-align: center; text-style: bold;
        height: 3; content-align: center middle; padding: 0 2;
        border-bottom: solid {_GREEN};
    }}
    #distro-subtitle {{
        background: {_BG}; color: {_DIM};
        text-align: center; height: 1; padding: 0 1;
    }}
    #distro-list {{
        height: 1fr; margin: 1 2; border: solid {_GREEN};
    }}
    #distro-status {{
        background: {_SURF}; height: 1; padding: 0 1;
        border-top: solid {_DIM}; color: {_DIM};
    }}
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("+--[ DEVSTICK :: SELECT DISTRO ]--+", id="distro-screen-title")
        yield Static(
            "[Enter] Open   [I] Install   [D] Remove   [R] Refresh   [Q] Quit",
            id="distro-subtitle",
        )
        yield DataTable(id="distro-list", cursor_type="row", zebra_stripes=True)
        yield Static("", id="distro-status")
        yield Footer()

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
            loc = str(path) if installed else "---"
            t.add_row(name, badge, loc, key=name)

    def _status(self, msg: str):
        self.query_one("#distro-status", Static).update(msg)

    def _get_cursor_key(self) -> str | None:
        t = self.query_one("#distro-list", DataTable)
        keys = list(DISTROS.keys())
        if t.cursor_row < 0 or t.cursor_row >= len(keys):
            return None
        return keys[t.cursor_row]

    def action_refresh(self):
        self._refresh()
        self._status("Refreshed.")

    def action_install(self):
        name = self._get_cursor_key()
        if name is None:
            self.notify("Select a distro first.", severity="warning"); return
        if distro_installed(name):
            self.notify(f"{name} is already installed.", severity="warning"); return
        def on_result(yes):
            if yes: self._do_install(name)
        self.app.push_screen(InstallDistroModal(name), on_result)

    def action_remove(self):
        name = self._get_cursor_key()
        if name is None:
            self.notify("Select a distro first.", severity="warning"); return
        if not distro_installed(name):
            self.notify(f"{name} is not installed.", severity="warning"); return
        def on_result(yes):
            if yes: self._do_remove(name)
        self.app.push_screen(RemoveDistroModal(name), on_result)

    @on(DataTable.RowSelected, "#distro-list")
    def row_selected(self, event: DataTable.RowSelected):
        if not (event.row_key and event.row_key.value):
            return
        name = event.row_key.value
        if not distro_installed(name):
            self.notify(f"{name} is not installed! Install it first.", severity="warning")
            return
        self.app.push_screen(UsersScreen(distro=name))

    @work(thread=True)
    def _do_install(self, name: str):
        self.call_from_thread(self._status, f"Installing: {name}...")
        cmd = ["python3", str(BASE_DIR / "main.py"), "install", name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            self.call_from_thread(self.notify, f"[OK] {name} installed!")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"{name} installed successfully.")
        else:
            msg = result.stderr.strip() or result.stdout.strip()
            self.call_from_thread(self.notify, f"[ERR] {msg}", severity="error")
            self.call_from_thread(self._status, "Installation failed.")

    @work(thread=True)
    def _do_remove(self, name: str):
        self.call_from_thread(self._status, f"Removing: {name}...")
        try:
            shutil.rmtree(str(DISTROS[name]))
            self.call_from_thread(self.notify, f"[OK] {name} removed!")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"{name} removed.")
        except Exception as e:
            self.call_from_thread(self.notify, f"[ERR] {e}", severity="error")


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 2: Users
# ═══════════════════════════════════════════════════════════════════════════════

_ROOT_KEY  = "__root__"
_EMPTY_KEY = "__empty__"


class UsersScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back",     "Back"),
        Binding("n",      "new_user",    "New User"),
        Binding("d",      "delete_user", "Delete"),
        # Enter is handled by DataTable.RowSelected
    ]

    CSS = f"""
    UsersScreen {{ layout: vertical; background: {_BG}; }}

    #users-screen-title {{
        background: {_SURF}; color: {_AMBER};
        text-align: center; text-style: bold;
        height: 3; content-align: center middle; padding: 0 2;
        border-bottom: solid {_GREEN};
    }}
    #users-subtitle {{
        background: {_BG}; color: {_DIM};
        text-align: center; height: 1; padding: 0 1;
    }}
    #users-table {{
        height: 1fr; margin: 1 2; border: solid {_GREEN};
    }}
    #users-status {{
        background: {_SURF}; height: 1; padding: 0 1;
        border-top: solid {_DIM}; color: {_DIM};
    }}
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            f"+--[ DEVSTICK :: USERS :: {self.distro.upper()} ]--+",
            id="users-screen-title",
        )
        yield Static(
            "[Enter] Login   [N] New User   [D] Delete   [Esc] Back",
            id="users-subtitle",
        )
        yield DataTable(id="users-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="users-status")
        yield Footer()

    def on_mount(self):
        t = self.query_one("#users-table", DataTable)
        t.add_columns("Username", "Role")
        self._refresh()

    def _refresh(self):
        t = self.query_one("#users-table", DataTable)
        t.clear()

        # ── Root entry (always shown, passwordless, -0 -w /root) ──────────────
        t.add_row(
            "[bold yellow]root[/bold yellow]",
            "[bold red]ROOT  (no password  |  -0 -w /root)[/bold red]",
            key=_ROOT_KEY,
        )

        users        = load_users()
        distro_users = users.get(self.distro, {})
        if not distro_users:
            t.add_row("[dim]-- no users registered --[/dim]", "", key=_EMPTY_KEY)
        else:
            for uname, meta in distro_users.items():
                role = "[yellow]sudo[/yellow]" if meta.get("root") else "normal"
                t.add_row(uname, role, key=uname)

    def _status(self, msg: str):
        self.query_one("#users-status", Static).update(msg)

    def _get_cursor_key(self) -> str | None:
        t = self.query_one("#users-table", DataTable)
        try:
            cell_key = t.coordinate_to_cell_key(t.cursor_coordinate)
            return cell_key.row_key.value
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
        self.app.push_screen(
            FileManagerScreen(
                distro=self.distro,
                username=uname,
                root_path=rootfs if rootfs and rootfs.exists() else BASE_DIR,
                root_login=False,
            )
        )

    def _open_as_root(self):
        rootfs = DISTROS.get(self.distro)
        self.app.push_screen(
            FileManagerScreen(
                distro=self.distro,
                username="root",
                root_path=rootfs if rootfs and rootfs.exists() else BASE_DIR,
                root_login=True,
            )
        )

    def action_go_back(self):
        self.app.pop_screen()

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
        cmd = [
            "python3", str(BASE_DIR / "main.py"),
            "register", self.distro,
            "--username", username, "--password", password,
        ]
        if is_sudo:
            cmd.append("--root")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            self.call_from_thread(self.notify, f"[OK] User created: {username}")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"User created: {username}")
        else:
            msg = result.stderr.strip() or result.stdout.strip()
            self.call_from_thread(self.notify, f"[ERR] {msg}", severity="error")

    @work(thread=True)
    def _do_delete_user(self, username: str, keep_home: bool):
        cmd = [
            "python3", str(BASE_DIR / "main.py"),
            "delete-user", self.distro, "--username", username,
        ]
        if keep_home:
            cmd.append("--keep-home")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            self.call_from_thread(self.notify, f"[OK] User deleted: {username}")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"User deleted: {username}")
        else:
            msg = result.stderr.strip() or result.stdout.strip()
            self.call_from_thread(self.notify, f"[ERR] {msg}", severity="error")


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 3: File Manager
# ═══════════════════════════════════════════════════════════════════════════════

class FileManagerScreen(Screen):
    BINDINGS = [
        Binding("escape",    "go_back",       "Back"),
        Binding("backspace", "go_up",         "Parent Dir"),
        Binding("delete",    "delete_file",   "Delete"),
        Binding("r",         "refresh",       "Refresh"),
        Binding("ctrl+r",    "run_distro",    "Run Distro"),
        # Enter is handled by DataTable.RowSelected
    ]

    CSS = f"""
    FileManagerScreen {{ layout: vertical; background: {_BG}; }}

    #fm-screen-title {{
        background: {_SURF}; color: {_AMBER};
        text-align: center; text-style: bold;
        height: 3; content-align: center middle; padding: 0 2;
        border-bottom: solid {_GREEN};
    }}
    #fm-path-bar {{
        background: {_BG}; height: 1; padding: 0 1;
        border-bottom: solid {_DIM};
        color: {_GREEN};
    }}
    #fm-table {{
        height: 1fr; margin: 0 2; border: solid {_GREEN};
    }}
    #fm-status {{
        background: {_SURF}; height: 1; padding: 0 1;
        border-top: solid {_DIM}; color: {_DIM};
    }}
    """

    def __init__(
        self,
        distro: str,
        username: str,
        root_path: Path,
        root_login: bool = False,
    ):
        super().__init__()
        self.distro     = distro
        self.username   = username
        self.root_path  = root_path
        self.root_login = root_login
        self._cur_path  = root_path
        self._entries: list[Path] = []
        self._app_prefs = load_app_prefs()

    def compose(self) -> ComposeResult:
        root_tag = " [ROOT -0 -w /root]" if self.root_login else ""
        yield Header(show_clock=True)
        yield Static(
            f"+--[ FILE MANAGER :: {self.distro.upper()} / {self.username}{root_tag} ]--+",
            id="fm-screen-title",
        )
        yield Static("", id="fm-path-bar")
        yield DataTable(id="fm-table", cursor_type="row", zebra_stripes=True)
        yield Static(
            "[Enter] Open/Enter   [Bksp] Up   [Del] Delete   "
            "[R] Refresh   [Ctrl+R] Run   [Esc] Back",
            id="fm-status",
        )
        yield Footer()

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
            self._status("[ERR] Permission denied")
            return

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

    def _go_up(self):
        if self._cur_path == self.root_path:
            self._status("Already at root directory.")
            return
        self._cur_path = self._cur_path.parent
        self._refresh()

    def _open_entry(self, path: Path):
        if path.is_dir():
            self._cur_path = path
            self._refresh()
        else:
            cat = file_category(path)
            def on_result(app_name):
                if not app_name: return
                self._launch_with_app(app_name, path)
            self.app.push_screen(OpenFileModal(path, cat, self._app_prefs), on_result)

    def _launch_with_app(self, app_name: str, path: Path):
        self._status(f"Opening: {app_name} {path.name}")
        try:
            with self.app.suspend():
                subprocess.run([app_name, str(path)])
        except FileNotFoundError:
            self.notify(f"'{app_name}' not found!", severity="error")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def action_go_back(self):
        self.app.pop_screen()

    def action_go_up(self):
        self._go_up()

    def action_refresh(self):
        self._refresh()
        self._status("Refreshed.")

    def action_open_selected(self):
        t = self.query_one("#fm-table", DataTable)
        if 0 <= t.cursor_row < len(self._entries):
            self._open_entry(self._entries[t.cursor_row])

    def action_delete_file(self):
        t = self.query_one("#fm-table", DataTable)
        if not (0 <= t.cursor_row < len(self._entries)):
            return
        path = self._entries[t.cursor_row]
        def on_confirm(yes):
            if not yes: return
            try:
                shutil.rmtree(str(path)) if path.is_dir() else path.unlink()
                self._status(f"Deleted: {path.name}")
                self._refresh()
            except Exception as e:
                self.notify(f"Could not delete: {e}", severity="error")
        self.app.push_screen(
            ConfirmModal(
                "[ DELETE FILE / DIRECTORY ]",
                f"[bold]{path.name}[/bold] will be permanently removed. Are you sure?\n"
                + (
                    "[bold red]WARNING: Directory and ALL its contents will be erased![/bold red]"
                    if path.is_dir() else ""
                ),
            ),
            on_confirm,
        )

    def action_run_distro(self):
        if self.root_login:
            # Passwordless root login: -0 (fake uid 0) and -w /root (working dir)
            cmd = [
                "python3", str(BASE_DIR / "main.py"),
                "run", self.distro, "-0", "-w", "/root",
            ]
        else:
            cmd = [
                "python3", str(BASE_DIR / "main.py"),
                "run", self.distro, "--user", self.username,
            ]
        self.notify(f"Running: {self.distro} ({self.username})...")
        with self.app.suspend():
            subprocess.run(cmd)

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
