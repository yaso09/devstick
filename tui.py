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
    Button,
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
    "text": "📄", "image": "🖼️ ", "video": "🎬", "audio": "🎵",
    "archive": "📦", "pdf": "📕", "dir": "📁", "exec": "⚙️ ", "unknown": "❓",
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
    CSS = """
    InstallDistroModal { align: center middle; }
    InstallDistroModal > Vertical {
        background: $surface; border: thick $success;
        width: 55; height: auto; padding: 1 2;
    }
    InstallDistroModal .modal-title {
        text-align: center; text-style: bold; color: $success; margin-bottom: 1;
    }
    InstallDistroModal .modal-buttons { margin-top: 2; height: 3; }
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Kur: {self.distro}", classes="modal-title")
            yield Label(
                f"[bold]{self.distro}[/bold] henüz kurulu değil.\n"
                "Şimdi kurmak istiyor musunuz?"
            )
            with Horizontal(classes="modal-buttons"):
                yield Button("Kur",   variant="success", id="inst_ok")
                yield Button("İptal", variant="default", id="inst_cancel")

    @on(Button.Pressed, "#inst_cancel")
    def cancel(self): self.dismiss(False)

    @on(Button.Pressed, "#inst_ok")
    def confirm(self): self.dismiss(True)


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Remove Distro
# ═══════════════════════════════════════════════════════════════════════════════

class RemoveDistroModal(ModalScreen):
    CSS = """
    RemoveDistroModal { align: center middle; }
    RemoveDistroModal > Vertical {
        background: $surface; border: thick $error;
        width: 55; height: auto; padding: 1 2;
    }
    RemoveDistroModal .modal-title {
        text-align: center; text-style: bold; color: $error; margin-bottom: 1;
    }
    RemoveDistroModal .modal-buttons { margin-top: 2; height: 3; }
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Kaldır: {self.distro}", classes="modal-title")
            yield Label(
                f"[bold red]{self.distro}[/bold red] ve tüm verisi silinecek!\n"
                "Emin misiniz?"
            )
            with Horizontal(classes="modal-buttons"):
                yield Button("Kaldır", variant="error",   id="rem_ok")
                yield Button("İptal",  variant="default", id="rem_cancel")

    @on(Button.Pressed, "#rem_cancel")
    def cancel(self): self.dismiss(False)

    @on(Button.Pressed, "#rem_ok")
    def confirm(self): self.dismiss(True)


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Register User
# ═══════════════════════════════════════════════════════════════════════════════

class RegisterUserModal(ModalScreen):
    CSS = """
    RegisterUserModal { align: center middle; }
    RegisterUserModal > Vertical {
        background: $surface; border: thick $primary;
        width: 60; height: auto; padding: 1 2;
    }
    RegisterUserModal .modal-title {
        text-align: center; text-style: bold; color: $primary; margin-bottom: 1;
    }
    RegisterUserModal Label { margin-top: 1; }
    RegisterUserModal .modal-buttons { margin-top: 2; height: 3; }
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Yeni Kullanıcı — {self.distro}", classes="modal-title")
            yield Label("Kullanıcı adı")
            yield Input(placeholder="username", id="reg_username")
            yield Label("Şifre")
            yield Input(placeholder="password", password=True, id="reg_password")
            yield Label("Şifre tekrar")
            yield Input(placeholder="password again", password=True, id="reg_password2")
            with Horizontal():
                yield Label("Sudo yetkisi ver: ")
                yield Switch(id="reg_sudo")
            with Horizontal(classes="modal-buttons"):
                yield Button("Oluştur", variant="primary", id="reg_ok")
                yield Button("İptal",   variant="default", id="reg_cancel")

    @on(Button.Pressed, "#reg_cancel")
    def cancel(self): self.dismiss(None)

    @on(Button.Pressed, "#reg_ok")
    def confirm(self):
        username  = self.query_one("#reg_username",  Input).value.strip()
        password  = self.query_one("#reg_password",  Input).value
        password2 = self.query_one("#reg_password2", Input).value
        sudo      = self.query_one("#reg_sudo",      Switch).value
        if not username:
            self.notify("Kullanıcı adı boş olamaz!", severity="error"); return
        if not password:
            self.notify("Şifre boş olamaz!", severity="error"); return
        if password != password2:
            self.notify("Şifreler eşleşmiyor!", severity="error"); return
        self.dismiss({"username": username, "password": password, "sudo": sudo})


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Delete User
# ═══════════════════════════════════════════════════════════════════════════════

class DeleteUserModal(ModalScreen):
    CSS = """
    DeleteUserModal { align: center middle; }
    DeleteUserModal > Vertical {
        background: $surface; border: thick $error;
        width: 55; height: auto; padding: 1 2;
    }
    DeleteUserModal .modal-title {
        text-align: center; text-style: bold; color: $error; margin-bottom: 1;
    }
    DeleteUserModal .modal-buttons { margin-top: 2; height: 3; }
    """

    def __init__(self, distro: str, username: str):
        super().__init__()
        self.distro   = distro
        self.username = username

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Kullanıcıyı Sil — {self.distro}", classes="modal-title")
            yield Label(f"[bold]{self.username}[/bold] silinecek. Emin misiniz?")
            with Horizontal():
                yield Label("Home dizinini koru: ")
                yield Switch(id="del_keep_home")
            with Horizontal(classes="modal-buttons"):
                yield Button("Sil",   variant="error",   id="del_ok")
                yield Button("İptal", variant="default", id="del_cancel")

    @on(Button.Pressed, "#del_cancel")
    def cancel(self): self.dismiss(None)

    @on(Button.Pressed, "#del_ok")
    def confirm(self):
        keep = self.query_one("#del_keep_home", Switch).value
        self.dismiss({"keep_home": keep})


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Open File
# ═══════════════════════════════════════════════════════════════════════════════

class OpenFileModal(ModalScreen):
    CSS = """
    OpenFileModal { align: center middle; }
    OpenFileModal > Vertical {
        background: $surface; border: thick $primary;
        width: 60; height: auto; padding: 1 2;
    }
    OpenFileModal .modal-title {
        text-align: center; text-style: bold; color: $primary; margin-bottom: 1;
    }
    OpenFileModal .modal-buttons { margin-top: 1; height: 3; }
    """

    def __init__(self, filepath: Path, category: str, prefs: dict):
        super().__init__()
        self.filepath = filepath
        self.category = category
        self.prefs    = prefs

    def compose(self) -> ComposeResult:
        default_app = self.prefs.get(self.category, "")
        suggestions = DEFAULT_APP_SUGGESTIONS.get(self.category, [])
        icon        = CATEGORY_ICONS.get(self.category, "❓")
        with Vertical():
            yield Label(f"Dosyayı Aç — {icon} {self.category}", classes="modal-title")
            yield Label(f"[dim]{self.filepath.name}[/dim]")
            yield Label("Uygulama:")
            yield Input(value=default_app, placeholder="uygulama adı", id="open_app")
            if suggestions:
                yield Label(f"Öneriler: {', '.join(suggestions)}", classes="dim")
            with Horizontal(classes="modal-buttons"):
                yield Button("Aç",    variant="primary", id="open_ok")
                yield Button("İptal", variant="default", id="open_cancel")

    @on(Button.Pressed, "#open_cancel")
    def cancel(self): self.dismiss(None)

    @on(Button.Pressed, "#open_ok")
    def confirm(self):
        app_name = self.query_one("#open_app", Input).value.strip()
        if not app_name:
            self.notify("Uygulama adı boş olamaz!", severity="error"); return
        self.dismiss(app_name)


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL: Generic Confirm
# ═══════════════════════════════════════════════════════════════════════════════

class ConfirmModal(ModalScreen):
    CSS = """
    ConfirmModal { align: center middle; }
    ConfirmModal > Vertical {
        background: $surface; border: thick $warning;
        width: 55; height: auto; padding: 1 2;
    }
    ConfirmModal .modal-title {
        text-align: center; text-style: bold; color: $warning; margin-bottom: 1;
    }
    ConfirmModal .modal-buttons { margin-top: 2; height: 3; }
    """

    def __init__(self, title: str, message: str):
        super().__init__()
        self._title   = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title,   classes="modal-title")
            yield Label(self._message)
            with Horizontal(classes="modal-buttons"):
                yield Button("Evet",  variant="warning", id="conf_ok")
                yield Button("İptal", variant="default", id="conf_cancel")

    @on(Button.Pressed, "#conf_cancel")
    def cancel(self): self.dismiss(False)

    @on(Button.Pressed, "#conf_ok")
    def confirm(self): self.dismiss(True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 0: Splash
# ═══════════════════════════════════════════════════════════════════════════════

class SplashScreen(Screen):
    CSS = """
    SplashScreen {
        align: center middle;
        background: $background;
    }
    #splash-box {
        width: 40;
        height: auto;
        padding: 3 4;
        border: double $primary;
        background: $surface;
    }
    #splash-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        width: 100%;
    }
    #splash-sub {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
        width: 100%;
    }
    #splash-hint {
        text-align: center;
        color: $text-disabled;
        margin-top: 2;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                with Vertical(id="splash-box"):
                    yield Static("Devstick", id="splash-title")
                    yield Static("by Yasir Eymen Kayabaşı", id="splash-sub")
                    yield Static("Yükleniyor...", id="splash-hint")

    def on_mount(self):
        self.set_timer(2.0, self._go_to_distro)

    def _go_to_distro(self):
        self.app.push_screen(DistroScreen())


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 1: Distro Selection
# ═══════════════════════════════════════════════════════════════════════════════

class DistroScreen(Screen):
    BINDINGS = [
        Binding("q", "app.quit", "Çıkış"),
        Binding("r", "refresh",  "Yenile"),
    ]

    CSS = """
    DistroScreen { layout: vertical; background: $background; }

    #distro-screen-title {
        background: $primary; color: $background;
        text-align: center; text-style: bold;
        height: 3; content-align: center middle; padding: 0 2;
    }
    #distro-subtitle {
        background: $surface; color: $text-muted;
        text-align: center; height: 1; padding: 0 1;
    }
    #distro-list {
        height: 1fr; margin: 1 2; border: solid $primary-darken-2;
    }
    #distro-btn-row {
        height: auto; layout: horizontal; padding: 0 2; margin-bottom: 1;
    }
    #distro-btn-row Button { margin: 0 1; height: 3; }
    #distro-status {
        background: $surface; height: 1; padding: 0 1;
        border-top: solid $primary-darken-3; color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("📦  İşletim Sistemi Seçimi", id="distro-screen-title")
        yield Static("Enter ile açın  •  I ile kurun  •  R ile kaldırın", id="distro-subtitle")
        yield DataTable(id="distro-list", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="distro-btn-row"):
            yield Button("⏎  Aç",      id="btn_distro_open",    variant="success")
            yield Button("📥 Kur",     id="btn_distro_install", variant="primary")
            yield Button("🗑  Kaldır",  id="btn_distro_remove",  variant="error")
            yield Button("🔄 Yenile",  id="btn_distro_refresh", variant="default")
        yield Static("", id="distro-status")
        yield Footer()

    def on_mount(self):
        t = self.query_one("#distro-list", DataTable)
        t.add_columns("Dağıtım", "Durum", "Konum")
        self._refresh()

    def _refresh(self):
        t = self.query_one("#distro-list", DataTable)
        t.clear()
        for name, path in DISTROS.items():
            installed = path.exists()
            badge = (
                "[bold green]✔ Kurulu[/bold green]"
                if installed else
                "[bold red]✘ Kurulu değil[/bold red]"
            )
            loc = str(path) if installed else "—"
            t.add_row(name, badge, loc, key=name)

    def _status(self, msg: str):
        self.query_one("#distro-status", Static).update(msg)

    def _get_cursor_key(self) -> str | None:
        t    = self.query_one("#distro-list", DataTable)
        keys = list(DISTROS.keys())
        if t.cursor_row < 0 or t.cursor_row >= len(keys):
            return None
        return keys[t.cursor_row]

    def action_refresh(self):
        self._refresh()
        self._status("Yenilendi.")

    @on(DataTable.RowSelected, "#distro-list")
    def row_selected(self, event: DataTable.RowSelected):
        if not (event.row_key and event.row_key.value):
            return
        name = event.row_key.value
        if not distro_installed(name):
            self.notify(f"{name} kurulu değil! Önce kurun.", severity="warning")
            return
        self.app.push_screen(UsersScreen(distro=name))

    @on(Button.Pressed, "#btn_distro_open")
    def btn_open(self):
        name = self._get_cursor_key()
        if name is None:
            self.notify("Bir dağıtım seçin.", severity="warning"); return
        if not distro_installed(name):
            self.notify(f"{name} kurulu değil!", severity="warning"); return
        self.app.push_screen(UsersScreen(distro=name))

    @on(Button.Pressed, "#btn_distro_install")
    def btn_install(self):
        name = self._get_cursor_key()
        if name is None:
            self.notify("Bir dağıtım seçin.", severity="warning"); return
        if distro_installed(name):
            self.notify(f"{name} zaten kurulu.", severity="warning"); return
        def on_result(yes):
            if yes: self._do_install(name)
        self.app.push_screen(InstallDistroModal(name), on_result)

    @on(Button.Pressed, "#btn_distro_remove")
    def btn_remove(self):
        name = self._get_cursor_key()
        if name is None:
            self.notify("Bir dağıtım seçin.", severity="warning"); return
        if not distro_installed(name):
            self.notify(f"{name} zaten kurulu değil.", severity="warning"); return
        def on_result(yes):
            if yes: self._do_remove(name)
        self.app.push_screen(RemoveDistroModal(name), on_result)

    @on(Button.Pressed, "#btn_distro_refresh")
    def btn_refresh(self):
        self._refresh()
        self._status("Yenilendi.")

    @work(thread=True)
    def _do_install(self, name: str):
        self.call_from_thread(self._status, f"Kuruluyor: {name}…")
        cmd = ["python3", str(BASE_DIR / "main.py"), "install", name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            self.call_from_thread(self.notify, f"✅ {name} kuruldu!")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"{name} başarıyla kuruldu.")
        else:
            msg = result.stderr.strip() or result.stdout.strip()
            self.call_from_thread(self.notify, f"❌ Hata: {msg}", severity="error")
            self.call_from_thread(self._status, "Kurulum başarısız.")

    @work(thread=True)
    def _do_remove(self, name: str):
        self.call_from_thread(self._status, f"Kaldırılıyor: {name}…")
        try:
            shutil.rmtree(str(DISTROS[name]))
            self.call_from_thread(self.notify, f"✅ {name} kaldırıldı!")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"{name} kaldırıldı.")
        except Exception as e:
            self.call_from_thread(self.notify, f"❌ Hata: {e}", severity="error")


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 2: Users
# ═══════════════════════════════════════════════════════════════════════════════

class UsersScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back",     "Geri"),
        Binding("n",      "new_user",    "Yeni Kullanıcı"),
        Binding("d",      "delete_user", "Sil"),
    ]

    CSS = """
    UsersScreen { layout: vertical; background: $background; }

    #users-screen-title {
        background: $primary; color: $background;
        text-align: center; text-style: bold;
        height: 3; content-align: center middle; padding: 0 2;
    }
    #users-subtitle {
        background: $surface; color: $text-muted;
        text-align: center; height: 1; padding: 0 1;
    }
    #users-table {
        height: 1fr; margin: 1 2; border: solid $primary-darken-2;
    }
    #users-btn-row {
        height: auto; layout: horizontal; padding: 0 2; margin-bottom: 1;
    }
    #users-btn-row Button { margin: 0 1; height: 3; }
    #users-status {
        background: $surface; height: 1; padding: 0 1;
        border-top: solid $primary-darken-3; color: $text-muted;
    }
    """

    def __init__(self, distro: str):
        super().__init__()
        self.distro = distro

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(f"👤  Kullanıcılar — {self.distro}", id="users-screen-title")
        yield Static("Enter ile giriş yapın", id="users-subtitle")
        yield DataTable(id="users-table", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="users-btn-row"):
            yield Button("⏎  Giriş Yap",      id="btn_user_login", variant="success")
            yield Button("➕ Yeni Kullanıcı",  id="btn_user_add",   variant="primary")
            yield Button("🗑  Sil",             id="btn_user_del",   variant="error")
            yield Button("← Geri",             id="btn_user_back",  variant="default")
        yield Static("", id="users-status")
        yield Footer()

    def on_mount(self):
        t = self.query_one("#users-table", DataTable)
        t.add_columns("Kullanıcı Adı", "Rol")
        self._refresh()

    def _refresh(self):
        t            = self.query_one("#users-table", DataTable)
        t.clear()
        users        = load_users()
        distro_users = users.get(self.distro, {})
        if not distro_users:
            t.add_row("[dim]— kullanıcı yok —[/dim]", "")
            return
        for uname, meta in distro_users.items():
            role = "[yellow]sudo[/yellow]" if meta.get("root") else "normal"
            t.add_row(uname, role, key=uname)

    def _status(self, msg: str):
        self.query_one("#users-status", Static).update(msg)

    def _get_cursor_key(self) -> str | None:
        t    = self.query_one("#users-table", DataTable)
        keys = list(load_users().get(self.distro, {}).keys())
        if t.cursor_row < 0 or t.cursor_row >= len(keys):
            return None
        return keys[t.cursor_row]

    def _open_fm(self, uname: str):
        rootfs = DISTROS.get(self.distro)
        self.app.push_screen(
            FileManagerScreen(
                distro=self.distro,
                username=uname,
                root_path=rootfs if rootfs and rootfs.exists() else BASE_DIR,
            )
        )

    def action_go_back(self):
        self.app.pop_screen()

    def action_new_user(self):
        def on_result(result):
            if not result: return
            self._status(f"Oluşturuluyor: {result['username']}…")
            self._do_register_user(result["username"], result["password"], result["sudo"])
        self.app.push_screen(RegisterUserModal(self.distro), on_result)

    def action_delete_user(self):
        uname = self._get_cursor_key()
        if not uname:
            self.notify("Bir kullanıcı seçin.", severity="warning"); return
        def on_result(result):
            if not result: return
            self._do_delete_user(uname, result["keep_home"])
        self.app.push_screen(DeleteUserModal(self.distro, uname), on_result)

    @on(DataTable.RowSelected, "#users-table")
    def row_selected(self, event: DataTable.RowSelected):
        if event.row_key and event.row_key.value:
            self._open_fm(event.row_key.value)

    @on(Button.Pressed, "#btn_user_login")
    def btn_login(self):
        uname = self._get_cursor_key()
        if not uname:
            self.notify("Bir kullanıcı seçin.", severity="warning"); return
        self._open_fm(uname)

    @on(Button.Pressed, "#btn_user_add")
    def btn_add(self): self.action_new_user()

    @on(Button.Pressed, "#btn_user_del")
    def btn_del(self): self.action_delete_user()

    @on(Button.Pressed, "#btn_user_back")
    def btn_back(self): self.action_go_back()

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
            self.call_from_thread(self.notify, f"✅ Kullanıcı oluşturuldu: {username}")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"Kullanıcı oluşturuldu: {username}")
        else:
            msg = result.stderr.strip() or result.stdout.strip()
            self.call_from_thread(self.notify, f"❌ Hata: {msg}", severity="error")

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
            self.call_from_thread(self.notify, f"✅ Kullanıcı silindi: {username}")
            self.call_from_thread(self._refresh)
            self.call_from_thread(self._status, f"Kullanıcı silindi: {username}")
        else:
            msg = result.stderr.strip() or result.stdout.strip()
            self.call_from_thread(self.notify, f"❌ Hata: {msg}", severity="error")


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 3: File Manager
# ═══════════════════════════════════════════════════════════════════════════════

class FileManagerScreen(Screen):
    BINDINGS = [
        Binding("escape",    "go_back",       "Geri"),
        Binding("backspace", "go_up",         "Üst Klasör"),
        Binding("enter",     "open_selected", "Aç / Gir"),
        Binding("delete",    "delete_file",   "Sil"),
        Binding("r",         "refresh",       "Yenile"),
        Binding("ctrl+r",    "run_distro",    "Distro'yu Çalıştır"),
    ]

    CSS = """
    FileManagerScreen { layout: vertical; background: $background; }

    #fm-screen-title {
        background: $accent; color: $background;
        text-align: center; text-style: bold;
        height: 3; content-align: center middle; padding: 0 2;
    }
    #fm-path-bar {
        background: $surface; height: 1; padding: 0 1;
        border-bottom: solid $accent-darken-2;
    }
    #fm-table {
        height: 1fr; margin: 0 2; border: solid $accent-darken-2;
    }
    #fm-btn-row {
        height: auto; layout: horizontal;
        padding: 0 2; margin-top: 1; margin-bottom: 1;
    }
    #fm-btn-row Button { margin: 0 1; height: 3; }
    #fm-status {
        background: $surface; height: 1; padding: 0 1;
        border-top: solid $accent-darken-3; color: $text-muted;
    }
    """

    def __init__(self, distro: str, username: str, root_path: Path):
        super().__init__()
        self.distro     = distro
        self.username   = username
        self.root_path  = root_path
        self._cur_path  = root_path
        self._entries: list[Path] = []
        self._app_prefs = load_app_prefs()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            f"📁  Dosya Yöneticisi — {self.distro} / {self.username}",
            id="fm-screen-title",
        )
        yield Static("", id="fm-path-bar")
        yield DataTable(id="fm-table", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="fm-btn-row"):
            yield Button("↩ Üst",      id="btn_fm_up",   variant="default")
            yield Button("⏎ Aç",       id="btn_fm_open", variant="primary")
            yield Button("🗑  Sil",     id="btn_fm_del",  variant="error")
            yield Button("🔄 Yenile",  id="btn_fm_ref",  variant="default")
            yield Button("▶  Çalıştır", id="btn_fm_run",  variant="success")
            yield Button("← Geri",     id="btn_fm_back", variant="default")
        yield Static("", id="fm-status")
        yield Footer()

    def on_mount(self):
        t = self.query_one("#fm-table", DataTable)
        t.add_columns("İkon", "Ad", "Boyut", "Tür")
        self._refresh()

    def _refresh(self):
        try:
            rel     = self._cur_path.relative_to(ROOTFS_DIR)
            display = f"📁  /{rel}"
        except ValueError:
            display = f"📁  {self._cur_path}"
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
            self._status("❌ Erişim reddedildi")
            return

        for entry in entries:
            cat  = file_category(entry)
            icon = CATEGORY_ICONS.get(cat, "❓")
            try:
                size = human_size(entry.stat().st_size) if entry.is_file() else "—"
            except OSError:
                size = "?"
            t.add_row(icon, entry.name, size, cat, key=str(entry))
            self._entries.append(entry)

    def _status(self, msg: str):
        self.query_one("#fm-status", Static).update(msg)

    def _go_up(self):
        if self._cur_path == self.root_path:
            self._status("Zaten kök dizindesiniz.")
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
        self._status(f"Açılıyor: {app_name} {path.name}")
        try:
            with self.app.suspend():
                subprocess.run([app_name, str(path)])
        except FileNotFoundError:
            self.notify(f"'{app_name}' bulunamadı!", severity="error")
        except Exception as e:
            self.notify(f"Hata: {e}", severity="error")

    def action_go_back(self):
        self.app.pop_screen()

    def action_go_up(self):
        self._go_up()

    def action_refresh(self):
        self._refresh()
        self._status("Yenilendi.")

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
                self._status(f"Silindi: {path.name}")
                self._refresh()
            except Exception as e:
                self.notify(f"Silinemedi: {e}", severity="error")
        self.app.push_screen(
            ConfirmModal(
                "Dosya / Klasörü Sil",
                f"[bold]{path.name}[/bold] kalıcı olarak silinecek. Emin misiniz?\n"
                + ("[bold red]⚠ Klasör ve tüm içeriği silinecek![/bold red]"
                   if path.is_dir() else ""),
            ),
            on_confirm,
        )

    def action_run_distro(self):
        cmd = [
            "python3", str(BASE_DIR / "main.py"),
            "run", self.distro, "--user", self.username,
        ]
        self.notify(f"Çalıştırılıyor: {self.distro} ({self.username})…")
        with self.app.suspend():
            subprocess.run(cmd)

    @on(DataTable.RowSelected, "#fm-table")
    def row_selected(self, event: DataTable.RowSelected):
        if event.row_key and event.row_key.value:
            self._open_entry(Path(event.row_key.value))

    @on(Button.Pressed, "#btn_fm_up")
    def btn_up(self): self._go_up()

    @on(Button.Pressed, "#btn_fm_open")
    def btn_open(self): self.action_open_selected()

    @on(Button.Pressed, "#btn_fm_del")
    def btn_del(self): self.action_delete_file()

    @on(Button.Pressed, "#btn_fm_ref")
    def btn_ref(self):
        self._refresh()
        self._status("Yenilendi.")

    @on(Button.Pressed, "#btn_fm_run")
    def btn_run(self): self.action_run_distro()

    @on(Button.Pressed, "#btn_fm_back")
    def btn_back(self): self.action_go_back()


# ═══════════════════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════════════════

class DevstickTUI(App):
    TITLE = "Devstick"

    def on_mount(self):
        self.push_screen(SplashScreen())


if __name__ == "__main__":
    DevstickTUI().run()
