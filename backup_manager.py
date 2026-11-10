"""Validated, atomic, local backup operations for Arena Tournament Manager."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

REQUIRED = {'tournaments': list, 'players': dict, 'teams_db': dict}

def validate(payload):
    if not isinstance(payload, dict):
        raise ValueError('Database root must be a JSON object')
    for key, typ in REQUIRED.items():
        if key not in payload or not isinstance(payload[key], typ):
            raise ValueError(f'Invalid or missing database field: {key}')
    return payload

def read_validated(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))

def atomic_write(path, payload):
    path = Path(path)
    validate(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.arena_', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def snapshot(data_path, backup_dir, kind='protected', reason='manual', keep_rolling=25):
    data_path, backup_dir = Path(data_path), Path(backup_dir)
    if not data_path.exists():
        raise FileNotFoundError('No saved database to back up')
    read_validated(data_path)
    if kind not in ('rolling', 'protected', 'manual', 'pre_restore'):
        raise ValueError('Unknown backup category')
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    safe_reason = ''.join(c if c.isalnum() or c in '-_' else '_' for c in reason)[:48]
    dest = backup_dir / f'{kind}_{timestamp}_{safe_reason}.json'
    shutil.copy2(data_path, dest)
    if hashlib.sha256(dest.read_bytes()).digest() != hashlib.sha256(data_path.read_bytes()).digest():
        dest.unlink(missing_ok=True)
        raise IOError('Backup checksum mismatch')
    if kind == 'rolling':
        for old in sorted(backup_dir.glob('rolling_*.json'))[:-keep_rolling]:
            old.unlink(missing_ok=True)
    return dest

def list_snapshots(backup_dir):
    result = []
    for path in sorted(Path(backup_dir).glob('*.json'), reverse=True):
        try:
            payload = read_validated(path)
            status = 'Valid'
            counts = f"{len(payload['tournaments'])} tournaments, {len(payload['players'])} players"
        except Exception as e:
            status, counts = 'Invalid', str(e)
        result.append((path, status, counts))
    return result

def restore(backup_path, data_path, backup_dir):
    """Validate first, safeguard current state, then atomically replace. Returns safety snapshot."""
    payload = read_validated(backup_path)
    safety = snapshot(data_path, backup_dir, 'pre_restore', 'before_restore') if Path(data_path).exists() else None
    atomic_write(data_path, payload)
    return safety
