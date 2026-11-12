"""Independent, checksum-verified updater for Arena Map Veto Staff Edition.

Release tags must be staff-vX.Y.Z, with assets ArenaMapVeto.exe and
ArenaMapVeto.exe.sha256. The installed executable must be writable.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QMessageBox

VERSION = "1.0.0"
REPO = "aykxy/TournamentManager"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
ASSET = "ArenaMapVeto.exe"
MAX_BYTES = 300 * 1024 * 1024


def version_tuple(value):
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("Invalid version")
    return tuple(map(int, value.split(".")))


def latest_staff_release():
    req = urllib.request.Request(API, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "ArenaMapVeto-Staff-Updater"})
    with urllib.request.urlopen(req, timeout=15) as response:
        releases = json.load(response)
    matches = []
    for release in releases:
        tag = release.get("tag_name", "")
        if release.get("draft") or release.get("prerelease") or not tag.startswith("staff-v"):
            continue
        try:
            version = version_tuple(tag[7:])
        except ValueError:
            continue
        assets = {a.get("name"): a for a in release.get("assets", [])}
        if ASSET in assets and ASSET + ".sha256" in assets:
            matches.append((version, release, assets))
    if not matches:
        return None
    version, release, assets = max(matches, key=lambda item: item[0])
    return {"version": ".".join(map(str, version)),
            "notes": release.get("body", "")[:2500],
            "exe": assets[ASSET]["browser_download_url"],
            "sha": assets[ASSET + ".sha256"]["browser_download_url"]}


def download(url, target, limit):
    prefix = f"https://github.com/{REPO}/releases/download/"
    if not url.startswith(prefix):
        raise ValueError("Untrusted update source")
    req = urllib.request.Request(url, headers={"User-Agent": "ArenaMapVeto-Staff-Updater"})
    with urllib.request.urlopen(req, timeout=60) as response:
        final = urllib.parse.urlparse(response.geturl())
        if final.scheme != "https" or final.hostname not in (
            "github.com", "release-assets.githubusercontent.com",
            "objects.githubusercontent.com"):
            raise ValueError("Unexpected update download host")
        total = 0
        with open(target, "wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise ValueError("Update exceeds download limit")
                out.write(chunk)


def stage(info, target):
    target = Path(target).resolve()
    if not target.is_file() or target.name.lower() != ASSET.lower():
        raise ValueError("Updater must be run from the installed ArenaMapVeto.exe")
    staged = target.with_name("ArenaMapVeto.update.exe")
    checksum = target.with_name("ArenaMapVeto.update.sha256")
    try:
        download(info["sha"], checksum, 1024)
        expected = checksum.read_text(encoding="ascii").strip().split()[0].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid checksum")
        download(info["exe"], staged, MAX_BYTES)
        with staged.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("Update checksum mismatch")
        return staged
    except Exception:
        staged.unlink(missing_ok=True)
        raise
    finally:
        checksum.unlink(missing_ok=True)


def wait_for_exit(pid, timeout=90):
    if os.name != "nt":
        raise RuntimeError("Windows only")
    import ctypes
    synchronize = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
    if handle:
        try:
            if ctypes.windll.kernel32.WaitForSingleObject(handle, timeout * 1000) != 0:
                raise TimeoutError("Arena Map Veto did not close")
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)


def install_from_staged(target, parent_pid):
    """Runs inside the new staged executable, after the original exits."""
    target = Path(target).resolve()
    if target.name.lower() != ASSET.lower():
        raise ValueError("Invalid installation target")
    staged = target.with_name("ArenaMapVeto.update.exe")
    if Path(sys.executable).resolve() != staged.resolve():
        raise ValueError("Updater was not launched from the staged executable")
    wait_for_exit(int(parent_pid))
    backup = target.with_name("ArenaMapVeto.previous.exe")
    if backup.exists():
        backup.unlink()
    target.replace(backup)
    try:
        shutil.copy2(staged, target)
        subprocess.Popen([str(target)], cwd=str(target.parent), close_fds=True)
    except Exception:
        target.unlink(missing_ok=True)
        backup.replace(target)
        raise
    # Keep previous executable for recovery; remove it at the next successful update.


class _Signals(QObject):
    checked = Signal(object)
    downloaded = Signal(object)
    error = Signal(str)


class StaffUpdateController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.signals = _Signals()
        self.signals.checked.connect(self._offer)
        self.signals.downloaded.connect(self._install)
        self.signals.error.connect(self._error)
        self._busy = False

    def check(self):
        if self._busy or not getattr(sys, "frozen", False):
            return
        self._busy = True
        def worker():
            try:
                info = latest_staff_release()
                if info and version_tuple(info["version"]) > version_tuple(VERSION):
                    self.signals.checked.emit(info)
                else:
                    self.signals.checked.emit(None)
            except Exception:
                self.signals.checked.emit(None)  # Offline operation remains usable.
        threading.Thread(target=worker, daemon=True).start()

    def _offer(self, info):
        self._busy = False
        if not info:
            return
        text = ("Arena Map Veto " + info["version"] + " is available.\n\n"
                + (info["notes"] or "Install the latest staff update.")[:1500]
                + "\n\nDownload and install now? Your saved veto data will be kept.")
        if QMessageBox.question(self.window, "Staff update available", text,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._busy = True
        self.window.setWindowTitle("Arena Map Veto — Downloading update...")
        def worker():
            try:
                staged = stage(info, sys.executable)
                self.signals.downloaded.emit(str(staged))
            except Exception as exc:
                self.signals.error.emit(str(exc))
        threading.Thread(target=worker, daemon=True).start()

    def _install(self, staged):
        self._busy = False
        try:
            subprocess.Popen([staged, "--install-update", str(Path(sys.executable).resolve()),
                              str(os.getpid())], cwd=str(Path(sys.executable).parent),
                             close_fds=True)
        except OSError as exc:
            self._error(str(exc))
            return
        self.window.close()

    def _error(self, message):
        self._busy = False
        self.window.setWindowTitle("Arena Map Veto — Staff Edition")
        QMessageBox.warning(self.window, "Update could not be installed", message)
