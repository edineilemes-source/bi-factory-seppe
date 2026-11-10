"""Synthetic fixtures only; never use operational storage."""
import io
import json
import os
from pathlib import Path
import sqlite3
import zipfile

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from scripts import secure_backup as b


@pytest.fixture
def sample(tmp_path):
    source = tmp_path / "operational" / "storage"
    source.mkdir(parents=True)
    for name in ("information_products/registry.json", "information_products/layouts/p.json",
                 "information_products/metadata/p.json", "dashboard_projects/products/p.json",
                 "working/prepared/sample.csv", "official/source.json", "reports/data.csv"):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"synthetic": true}')
    (source / "empty").mkdir()
    db = sqlite3.connect(source / "data.sqlite3")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE example (value TEXT)")
    db.execute("INSERT INTO example VALUES ('synthetic')")
    db.commit()
    key = AESGCM.generate_key(bit_length=256)
    backup = tmp_path / "sample.sepbackup"
    yield source, db, key, backup
    db.close()


def create(sample):
    source, _, key, backup = sample
    return b.create_backup(source, backup, key, writers_stopped=True)


def repack(backup, key, mutate):
    blob = backup.read_bytes()
    offset = len(b.MAGIC)
    plain = AESGCM(key).decrypt(blob[offset:offset+12], blob[offset+12:], b.MAGIC)
    with zipfile.ZipFile(io.BytesIO(plain)) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    mutate(entries)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    nonce = os.urandom(12)
    backup.write_bytes(b.MAGIC + nonce + AESGCM(key).encrypt(nonce, output.getvalue(), b.MAGIC))


def test_roundtrip_wal_integrity_and_preservation(sample, tmp_path):
    source, db, key, backup = sample
    before = b.inventory(source)
    create(sample)
    assert b.inventory(source) == before
    manifest, content = b.verify_backup(backup, key)
    assert manifest['files']['data.sqlite3']['kind'] == 'sqlite'
    assert not any(name.endswith(('-wal', '-shm')) for name in content)
    assert stat_mode(backup) == 0o600
    destination = tmp_path / "restored"
    b.restore_backup(backup, destination, key, protected_root=source.parent)
    with sqlite3.connect(destination / 'storage/data.sqlite3') as restored:
        assert restored.execute('SELECT value FROM example').fetchall() == [('synthetic',)]
        assert restored.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    assert (destination / 'storage/empty').is_dir()
    for path in source.rglob('*'):
        if path.is_file() and path.suffix != '.sqlite3' and not path.name.endswith(('-wal', '-shm')):
            assert (destination / 'storage' / path.relative_to(source)).read_bytes() == path.read_bytes()
    assert b.inventory(source) == before


def stat_mode(path):
    return path.stat().st_mode & 0o777


@pytest.mark.parametrize('damage', ['wrong-key', 'flip', 'truncate', 'header'])
def test_authentication_failure_has_no_restore(sample, tmp_path, damage):
    _, _, key, backup = sample
    create(sample)
    blob = bytearray(backup.read_bytes())
    if damage == 'wrong-key':
        key = AESGCM.generate_key(bit_length=256)
    elif damage == 'flip':
        blob[-1] ^= 1
    elif damage == 'truncate':
        blob = blob[:-10]
    else:
        blob[0] ^= 1
    backup.write_bytes(blob)
    destination = tmp_path / 'rejected'
    with pytest.raises(b.BackupError):
        b.restore_backup(backup, destination, key)
    assert not destination.exists()


@pytest.mark.parametrize('damage', ['hash', 'extra', 'traversal', 'sqlite'])
def test_authenticated_malformed_payload_rejected(sample, tmp_path, damage):
    _, _, key, backup = sample
    create(sample)
    def mutate(entries):
        manifest = json.loads(entries['manifest.json'])
        if damage == 'hash':
            manifest['files']['data.sqlite3']['sha256'] = '0' * 64
        elif damage == 'extra':
            entries['unlisted'] = b'x'
        elif damage == 'traversal':
            entry = manifest['files'].pop('data.sqlite3')
            manifest['files']['../escape'] = entry
            entries['storage/../escape'] = entries.pop('storage/data.sqlite3')
        else:
            data = b'invalid sqlite'
            entries['storage/data.sqlite3'] = data
            manifest['files']['data.sqlite3'].update(size=len(data), sha256=b.digest(data))
        entries['manifest.json'] = json.dumps(manifest).encode()
    repack(backup, key, mutate)
    with pytest.raises(b.BackupError):
        b.restore_backup(backup, tmp_path / 'rejected', key)
    assert not (tmp_path / 'rejected').exists()


def test_refuses_overwrite_and_operational_restore(sample, tmp_path):
    source, _, key, backup = sample
    create(sample)
    original = backup.read_bytes()
    with pytest.raises(FileExistsError):
        create(sample)
    assert backup.read_bytes() == original
    for destination in (source, source / 'new', source.parent):
        with pytest.raises(b.BackupError):
            b.restore_backup(backup, destination, key, protected_root=source.parent)
    existing = tmp_path / 'existing'
    existing.mkdir()
    (existing / 'keep').write_text('keep')
    with pytest.raises(b.BackupError):
        b.restore_backup(backup, existing, key)
    assert (existing / 'keep').read_text() == 'keep'


def test_requires_quiescence_and_rejects_symlinks(sample, tmp_path):
    source, _, key, backup = sample
    with pytest.raises(b.BackupError):
        b.create_backup(source, backup, key)
    (source / 'link').symlink_to(tmp_path)
    with pytest.raises(b.BackupError):
        create(sample)
    assert not backup.exists()


def test_changed_source_rejected(sample, monkeypatch):
    source, _, _, backup = sample
    original = b.snapshot_sqlite
    def changed(*args):
        data = original(*args)
        (source / 'changed.json').write_text('{}')
        return data
    monkeypatch.setattr(b, 'snapshot_sqlite', changed)
    with pytest.raises(b.BackupError):
        create(sample)
    assert not backup.exists()


def test_key_permissions_and_local_handoff(sample, tmp_path):
    _, _, key, backup = sample
    keyfile = tmp_path / 'key'
    b.private_write(keyfile, key)
    assert b.load_key(keyfile) == key
    keyfile.chmod(0o644)
    with pytest.raises(b.BackupError):
        b.load_key(keyfile)
    create(sample)
    destination = tmp_path / 'handoff'
    assert b.prepare_transfer(backup, destination, key)['upload_enabled'] is False
    assert {p.name for p in destination.iterdir()} == {'snapshot.sepbackup', 'transfer-plan.json'}
    plan = json.loads((destination / 'transfer-plan.json').read_text())
    assert plan['repository'] == 'edineilemes-source/bi-factory-seppe-backup'
    assert plan['encrypted_sha256'] == b.digest(backup.read_bytes())
    with pytest.raises(FileExistsError):
        b.prepare_transfer(backup, destination, key)


def test_limits_and_bad_database_fail_closed(sample, monkeypatch):
    source, _, key, backup = sample
    monkeypatch.setattr(b, 'LIMIT', 1)
    with pytest.raises(b.BackupError):
        create(sample)
    monkeypatch.setattr(b, 'LIMIT', 256 * 1024 * 1024)
    (source / 'broken.db').write_bytes(b'not sqlite')
    with pytest.raises(sqlite3.DatabaseError):
        create(sample)
    assert not backup.exists()


def test_cli_lifecycle_without_network(sample, tmp_path):
    import subprocess
    import sys
    source, _, _, _ = sample
    script = str(Path(b.__file__).resolve())
    key = tmp_path / 'cli.key'
    backup = tmp_path / 'cli.sepbackup'
    destination = tmp_path / 'cli-restore'
    def run(*args):
        return subprocess.run([sys.executable, script, *args], capture_output=True, text=True)
    assert run('keygen', '--key-file', str(key)).returncode == 0
    common = ['--key-file', str(key), '--backup', str(backup)]
    rejected = run('create', *common, '--source', str(source))
    assert rejected.returncode == 1
    assert not backup.exists()
    assert run('create', *common, '--source', str(source), '--writers-stopped').returncode == 0
    assert run('verify', *common).returncode == 0
    assert run('restore', *common, '--destination', str(destination)).returncode == 0
    assert run('prepare-transfer', *common, '--destination', str(tmp_path / 'cli-handoff')).returncode == 0
    assert run('keygen', '--key-file', str(key)).returncode == 1


def test_restore_io_failure_cleans_only_new_destination(sample, tmp_path, monkeypatch):
    _, _, key, backup = sample
    create(sample)
    original = b.private_write
    destination = tmp_path / 'failed-restore'
    sentinel = tmp_path / 'keep'
    sentinel.write_text('keep')
    def fail(path, data):
        if destination in Path(path).parents:
            raise OSError('simulated disk full')
        return original(path, data)
    monkeypatch.setattr(b, 'private_write', fail)
    with pytest.raises(OSError):
        b.restore_backup(backup, destination, key)
    assert not destination.exists()
    assert sentinel.read_text() == 'keep'


def test_nondeterministic_encryption_and_output_guards(sample):
    source, _, key, backup = sample
    create(sample)
    other = backup.with_name('other.sepbackup')
    b.create_backup(source, other, key, writers_stopped=True)
    assert other.read_bytes() != backup.read_bytes()
    with pytest.raises(b.BackupError):
        b.create_backup(source, source / 'forbidden', key, writers_stopped=True)
    assert not (source / 'forbidden').exists()


@pytest.mark.parametrize("name", ["bad:name", "bad\\name"])
def test_unrestorable_source_name_rejected(sample, name):
    source, _, _, backup = sample
    (source / name).write_text("synthetic")
    with pytest.raises(b.BackupError):
        create(sample)
    assert not backup.exists()


def test_manifest_root_alias_rejected(sample):
    _, _, key, backup = sample
    create(sample)
    def mutate(entries):
        manifest = json.loads(entries["manifest.json"])
        manifest["files"]["."] = {"kind": "file", "size": 0, "sha256": b.digest(b"")}
        entries["storage/."] = b""
        entries["manifest.json"] = json.dumps(manifest).encode()
    repack(backup, key, mutate)
    with pytest.raises(b.BackupError):
        b.verify_backup(backup, key)
