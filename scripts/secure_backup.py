"""Offline, fail-closed backup tool. No network or operational restore commands.

cryptography: Apache-2.0 OR BSD-3-Clause; Python standard library: PSF-2.0.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
import time
import zipfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"SEPPE-BACKUP-1\0"
LIMIT = 256 * 1024 * 1024  # bounded in-memory format, including ZIP overhead
MAX_FILES = 10000
ROOT = Path(__file__).resolve().parents[1]
BACKUP_REPOSITORY = "edineilemes-source/bi-factory-seppe-backup"


class BackupError(ValueError):
    """Backup rejected without changing operational data."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def outside(path, root):
    if path == root or root in path.parents:
        raise BackupError("Destino deve ficar fora da área protegida")


def private_write(path, data):
    # O_EXCL also refuses preexisting symlinks and never truncates files.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise


def load_key(path):
    path = Path(path)
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or mode & 0o077:
        raise BackupError("Chave deve ser arquivo regular privado (0600)")
    if path.stat().st_size != 32:
        raise BackupError("Tamanho da chave inválido")
    key = path.read_bytes()
    if len(key) != 32:
        raise BackupError("Chave deve conter exatamente 32 bytes aleatórios")
    return key


def validate_name(name):
    p = PurePosixPath(name)
    if (not name or p.is_absolute() or p.as_posix() == "." or
            ".." in p.parts or "\\" in name or ":" in name or "\0" in name or
            p.as_posix() != name.rstrip("/")):
        raise BackupError("Caminho inseguro")


def inventory(source):
    result = {}
    total = 0
    for path in sorted(source.rglob("*")):
        if len(result) >= MAX_FILES:
            raise BackupError("Limite de arquivos excedido")
        mode = path.lstat().st_mode
        name = path.relative_to(source).as_posix()
        validate_name(name)
        if stat.S_ISDIR(mode):
            result[name + "/"] = None
        elif stat.S_ISREG(mode):
            size = path.stat().st_size
            total += size
            if total > LIMIT or len(result) >= MAX_FILES:
                raise BackupError("Limite de volume/arquivos excedido")
            result[name] = digest(path.read_bytes())
        else:
            raise BackupError("Links e arquivos especiais não são aceitos")
    return result


def sqlite_check(path):
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise BackupError("SQLite inválido")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise BackupError("SQLite com referências inválidas")


def snapshot_sqlite(path, work):
    target = work / "snapshot.sqlite3"
    deadline = time.monotonic() + 30
    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise BackupError("Tempo limite no snapshot SQLite")
    # Never open an operational database with SQLite: even a read-only WAL
    # connection can change shared-memory read marks. Recover a private copy.
    local = work / "input.sqlite3"
    shutil.copyfile(path, local)
    local.chmod(0o600)
    for suffix in ("-wal", "-journal"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists():
            copy = Path(str(local) + suffix)
            shutil.copyfile(sidecar, copy)
            copy.chmod(0o600)
    with sqlite3.connect(local) as src:
        with sqlite3.connect(target) as dst:
            src.backup(dst, pages=256, progress=progress)
    sqlite_check(target)
    data = target.read_bytes()
    target.unlink()
    for copy in work.glob("input.sqlite3*"):
        copy.unlink()
    return data


def create_backup(source, output, key, *, writers_stopped=False):
    source, output = Path(source).resolve(), Path(output).absolute()
    if not writers_stopped:
        raise BackupError("Pause todos os gravadores e confirme writers_stopped")
    if len(key) != 32 or not source.is_dir():
        raise BackupError("Origem/chave inválida")
    outside(output.resolve(), source)
    outside(output.resolve(), ROOT)
    before = inventory(source)
    entries, payload = {}, io.BytesIO()
    with tempfile.TemporaryDirectory(prefix="seppe-snapshot-") as work:
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_STORED) as archive:
            databases = set()
            for name in before:
                if name.endswith("/"):
                    continue
                path = source / name
                with path.open("rb") as stream:
                    header = stream.read(16)
                if header == b"SQLite format 3\0" or path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                    databases.add(name)
            for name in before:
                if any(name == db + suffix for db in databases for suffix in ("-wal", "-shm", "-journal")):
                    continue  # backup API incorporates committed WAL, never copy sidecars
                kind = "directory" if name.endswith("/") else "sqlite" if name in databases else "file"
                data = b"" if kind == "directory" else snapshot_sqlite(source / name, Path(work)) if kind == "sqlite" else (source / name).read_bytes()
                entries[name] = {"size": len(data), "sha256": digest(data), "kind": kind}
                archive.writestr("storage/" + name, data)
                if payload.tell() > LIMIT:
                    raise BackupError("Snapshot excede limite")
            manifest = {"version": 1, "consistency": "writers-stopped", "files": entries}
            archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True).encode())
    if before != inventory(source):
        raise BackupError("Origem mudou durante captura; backup recusado")
    if len(payload.getvalue()) > LIMIT:
        raise BackupError("Snapshot excede limite")
    nonce = os.urandom(12)
    private_write(output, MAGIC + nonce + AESGCM(key).encrypt(nonce, payload.getvalue(), MAGIC))
    return {"files": len(entries), "encrypted_sha256": digest(output.read_bytes())}


def verify_backup(backup, key):
    backup = Path(backup)
    if backup.stat().st_size > LIMIT + 128:
        raise BackupError("Backup excede limite")
    blob = backup.read_bytes()
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 28:
        raise BackupError("Formato inválido")
    offset = len(MAGIC)
    try:
        plain = AESGCM(key).decrypt(blob[offset:offset + 12], blob[offset + 12:], MAGIC)
    except (InvalidTag, ValueError) as exc:
        raise BackupError("Falha de autenticação: chave incorreta ou corrupção") from exc
    try:
        with zipfile.ZipFile(io.BytesIO(plain)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or len(names) > MAX_FILES + 1:
                raise BackupError("Entradas duplicadas ou limite excedido")
            if sum(info.file_size for info in archive.infolist()) > LIMIT:
                raise BackupError("Conteúdo excede limite")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest["version"] != 1 or manifest["consistency"] != "writers-stopped":
                raise BackupError("Manifesto incompatível")
            files = manifest["files"]
            if set(names) != {"manifest.json"} | {"storage/" + name for name in files}:
                raise BackupError("Manifesto não corresponde ao conteúdo")
            content = {}
            for name, entry in files.items():
                validate_name(name)
                kind = entry["kind"]
                if kind not in {"file", "sqlite", "directory"} or (kind == "directory") != name.endswith("/"):
                    raise BackupError("Tipo inválido")
                data = archive.read("storage/" + name)
                if len(data) != entry["size"] or digest(data) != entry["sha256"] or (kind == "directory" and data):
                    raise BackupError("Integridade SHA-256 inválida")
                content[name] = data
            # Check SQLite before creating any restoration directory.
            with tempfile.TemporaryDirectory(prefix="seppe-verify-") as work:
                for name, data in content.items():
                    if files[name]["kind"] == "sqlite":
                        path = Path(work) / "check.sqlite3"
                        private_write(path, data)
                        sqlite_check(path)
                        path.unlink()
            return manifest, content
    except (KeyError, TypeError, AttributeError, zipfile.BadZipFile, json.JSONDecodeError, sqlite3.DatabaseError) as exc:
        raise BackupError("Conteúdo/manifesto inválido") from exc


def restore_backup(backup, destination, key, *, protected_root=ROOT):
    destination = Path(destination).absolute()
    outside(destination.resolve(), Path(protected_root).resolve())
    if destination.exists() or destination.is_symlink():
        raise BackupError("Restauração exige destino inexistente")
    manifest, content = verify_backup(backup, key)
    destination.mkdir(mode=0o700)  # exclusive reservation; parent must already exist
    try:
        storage = destination / "storage"
        storage.mkdir(mode=0o700)
        for name, data in content.items():
            path = storage / name
            if manifest["files"][name]["kind"] == "directory":
                path.mkdir(mode=0o700, parents=True, exist_ok=True)
            else:
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                private_write(path, data)
        private_write(destination / "manifest.json", json.dumps(manifest, sort_keys=True).encode())
    except BaseException:
        shutil.rmtree(destination)  # only the new isolated directory owned by this call
        raise
    return {"files": len(content), "restored": True}


def prepare_transfer(backup, destination, key):
    """Local encrypted-only handoff, deliberately without git/network operations."""
    if Path(backup).stat().st_size > LIMIT + 128:
        raise BackupError("Backup excede limite")
    blob = Path(backup).read_bytes()
    verify_backup(backup, key)
    if blob != Path(backup).read_bytes():
        raise BackupError("Backup mudou durante verificação")
    destination = Path(destination).absolute()
    outside(destination.resolve(), ROOT)
    destination.mkdir(mode=0o700)
    try:
        private_write(destination / "snapshot.sepbackup", blob)
        plan = {"repository": BACKUP_REPOSITORY, "upload_enabled": False,
                "encrypted_sha256": digest(blob), "artifact": "snapshot.sepbackup"}
        private_write(destination / "transfer-plan.json", json.dumps(plan, indent=2).encode())
    except BaseException:
        shutil.rmtree(destination)
        raise
    return {"prepared": True, "upload_enabled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("keygen")
    generate.add_argument("--key-file", required=True, type=Path)
    for command in ("create", "verify", "restore", "prepare-transfer"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--key-file", required=True, type=Path)
        cmd.add_argument("--backup", required=True, type=Path)
        if command == "create":
            cmd.add_argument("--source", type=Path, default=ROOT / "storage")
            cmd.add_argument("--writers-stopped", action="store_true")
        if command in {"restore", "prepare-transfer"}:
            cmd.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "keygen":
            outside(args.key_file.resolve(), ROOT)
            private_write(args.key_file, AESGCM.generate_key(bit_length=256))
            result = {"key_created": True}
        else:
            key = load_key(args.key_file)
            if args.command == "create":
                outside(args.key_file.resolve(), args.source.resolve())
                result = create_backup(args.source, args.backup, key, writers_stopped=args.writers_stopped)
            elif args.command == "verify":
                manifest, _ = verify_backup(args.backup, key)
                result = {"verified": True, "files": len(manifest["files"])}
            elif args.command == "restore":
                result = restore_backup(args.backup, args.destination, key)
            else:
                result = prepare_transfer(args.backup, args.destination, key)
        print(json.dumps(result))
    except (BackupError, OSError, sqlite3.DatabaseError) as exc:
        # Do not log filenames, SQL, key material or data on errors.
        parser.exit(1, "Operação recusada (" + type(exc).__name__ + "). Consulte o procedimento seguro.\n")


if __name__ == "__main__":
    main()
