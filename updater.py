"""External Windows updater for Arena Tournament Manager.

Packaged as a separate updater.exe and copied into the user's temp directory
before execution, so the installed updater.exe may itself be replaced.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

REPO = 'aykxy/TournamentManager'
API = f'https://api.github.com/repos/{REPO}/releases/latest'
ASSET = 'ArenaTournamentManager-Windows.zip'
MAX_SIZE = 350 * 1024 * 1024


def get_latest():
    req = urllib.request.Request(API, headers={'Accept':'application/vnd.github+json','User-Agent':'ArenaTournamentManager-Updater'})
    with urllib.request.urlopen(req, timeout=12) as response:
        release = json.load(response)
    tag = release.get('tag_name', '')
    if not tag.startswith('v'):
        raise ValueError('Invalid release version')
    assets = {a['name']: a for a in release.get('assets', [])}
    if ASSET not in assets or ASSET+'.sha256' not in assets:
        raise ValueError('Latest release is missing Windows update assets')
    return {'version': tag[1:], 'download_url': assets[ASSET]['browser_download_url'],
            'checksum_url': assets[ASSET+'.sha256']['browser_download_url'],
            'notes': release.get('body', '')[:4000]}


def _download(url, target, limit):
    if not url.startswith('https://github.com/'):
        raise ValueError('Untrusted release URL')
    req = urllib.request.Request(url, headers={'User-Agent':'ArenaTournamentManager-Updater'})
    with urllib.request.urlopen(req, timeout=45) as response:
        if not response.geturl().startswith('https://'):
            raise ValueError('Insecure download redirect')
        with Path(target).open('wb') as output:
            while chunk := response.read(1024*1024):
                output.write(chunk)
                if output.tell() > limit:
                    raise ValueError('Download exceeds limit')


def stage_update(info, data_dir):
    if not info['download_url'].startswith(f'https://github.com/{REPO}/releases/download/'):
        raise ValueError('Release URL does not match configured repository')
    stage = Path(tempfile.mkdtemp(prefix='arena-update-'))
    try:
        archive = stage / ASSET
        checksum = stage / (ASSET+'.sha256')
        _download(info['download_url'], archive, MAX_SIZE)
        _download(info['checksum_url'], checksum, 1024)
        expected = checksum.read_text(encoding='ascii').split()[0].lower()
        if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('Invalid checksum file')
        with archive.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if digest != expected:
            raise ValueError('Release checksum mismatch')
        with zipfile.ZipFile(archive) as z:
            entries = [i for i in z.infolist() if not i.is_dir()]
            if not entries or not any(i.filename == 'ArenaTournamentManager.exe' for i in entries):
                raise ValueError('Release has no application executable')
            for entry in entries:
                path = Path(entry.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename:
                    raise ValueError('Unsafe path in release archive')
                if entry.file_size > MAX_SIZE:
                    raise ValueError('Oversized archive member')
            if sum(i.file_size for i in entries) > 900*1024*1024:
                raise ValueError('Unpacked release is too large')
        return archive
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _wait_for_process(pid, timeout=90):
    if os.name != 'nt':
        raise RuntimeError('Updater can only install on Windows')
    SYNCHRONIZE = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
    if handle:
        try:
            result = ctypes.windll.kernel32.WaitForSingleObject(handle, timeout*1000)
            if result != 0:
                raise TimeoutError('Application did not close in time')
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)


def apply(package, app_dir, parent_pid):
    _wait_for_process(parent_pid)
    app_dir = Path(app_dir).resolve()
    package = Path(package).resolve()
    if not (app_dir / 'ArenaTournamentManager.exe').exists():
        raise RuntimeError('Application executable not found; update cancelled')
    staging = Path(tempfile.mkdtemp(prefix='arena-install-', dir=app_dir.parent))
    backup = app_dir.parent / (app_dir.name + '.previous')
    try:
        with zipfile.ZipFile(package) as z:
            z.extractall(staging)
        if not (staging / 'ArenaTournamentManager.exe').is_file():
            raise ValueError('Missing executable after extraction')
        if backup.exists():
            shutil.rmtree(backup)
        app_dir.rename(backup)
        try:
            staging.rename(app_dir)
        except Exception:
            backup.rename(app_dir)
            raise
        # Keep the previous app version available for manual rollback.
        subprocess.Popen([str(app_dir/'ArenaTournamentManager.exe')], cwd=str(app_dir), close_fds=True)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(package.parent, ignore_errors=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply', nargs=3, metavar=('ZIP','APP_DIR','PARENT_PID'))
    args=parser.parse_args()
    if args.apply:
        try:
            apply(args.apply[0], args.apply[1], int(args.apply[2]))
        except Exception as exc:
            # Preserve error details for troubleshooting.
            log=Path.home()/'ArenaTournamentManager'/'updater-error.log'
            log.parent.mkdir(exist_ok=True)
            log.write_text(f'{time.ctime()}: {exc}\n',encoding='utf-8')
            if os.name == 'nt':
                ctypes.windll.user32.MessageBoxW(None, str(exc), 'Arena update failed', 0x10)
            raise

if __name__ == '__main__':
    main()
