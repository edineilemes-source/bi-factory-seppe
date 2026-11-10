"""Synthetic-only crash-aware generation journal for SQLite+JSON fixtures.

No operational integration, CLI, network, backups, pruning, or deletions.
A single POSIX host and cooperative lock are assumed. Never point at BI data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile

from backup_fixture_staging import StageRejected, cooperative_lock


def _private_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise StageRejected("Expected private fixture file")
    return path


def _fsync_dir(directory):
    fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_json(path, value):
    """Atomic JSON replacement with fsync, in a private fixture directory."""
    path = Path(path)
    if path.is_symlink() or not path.parent.is_dir():
        raise StageRejected("Unsafe fixture destination")
    fd, tmp = tempfile.mkstemp(prefix=".synthetic-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        _fsync_dir(path.parent)
    finally:
        if fd != -1:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)


def _read_generation(database, layout):
    with sqlite3.connect(f"file:{Path(database).resolve()}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT generation FROM fixture_state").fetchall()
    if len(rows) != 1 or type(rows[0][0]) is not int:
        raise StageRejected("Invalid fixture generation row")
    payload = json.loads(Path(layout).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or type(payload.get("generation")) is not int:
        raise StageRejected("Invalid fixture JSON generation")
    return rows[0][0], payload["generation"]


def _inputs(database, layout, lock, journal):
    database, layout, lock, journal = map(Path, (database, layout, lock, journal))
    for path in (database, layout, lock):
        _private_file(path)
    if journal.is_symlink() or journal.parent.resolve() != layout.parent.resolve():
        raise StageRejected("Unsafe journal location")
    if journal.exists():
        _private_file(journal)
    if not (database.parent.resolve() == layout.parent.resolve() == lock.parent.resolve()):
        raise StageRejected("Fixtures must share a directory")
    if database.parent.stat().st_mode & 0o077:
        raise StageRejected("Fixture directory must be private")
    return database, layout, lock, journal


def commit_generation(database, layout, lock, journal, next_generation, *, inject_crash=None):
    """Advance fixture generation, leaving a journal if interrupted.

    inject_crash is for tests only: 'after_journal' or 'after_database'.
    An interrupted operation is not silently rolled back or accepted.
    """
    if type(next_generation) is not int or next_generation < 1:
        raise StageRejected("Invalid next generation")
    database, layout, lock, journal = _inputs(database, layout, lock, journal)
    with cooperative_lock(lock):
        if journal.exists():
            raise StageRejected("Pending generation requires explicit recovery")
        db_gen, json_gen = _read_generation(database, layout)
        if db_gen != json_gen or next_generation != db_gen + 1:
            raise StageRejected("Fixture generation is not sequential")
        _atomic_json(journal, {"version": 1, "from": db_gen, "to": next_generation,
                               "state": "pending"})
        if inject_crash == "after_journal":
            raise StageRejected("Injected synthetic interruption after journal")
        with sqlite3.connect(database) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE fixture_state SET generation=?", (next_generation,))
            db.commit()
        if inject_crash == "after_database":
            raise StageRejected("Injected synthetic interruption after database")
        payload = json.loads(layout.read_text(encoding="utf-8"))
        payload["generation"] = next_generation
        _atomic_json(layout, payload)
        _atomic_json(journal, {"version": 1, "from": db_gen, "to": next_generation,
                               "state": "committed"})
        return next_generation


def inspect_generation(database, layout, lock, journal):
    """Read-only under cooperative lock. No automatic recovery or deletion."""
    database, layout, lock, journal = _inputs(database, layout, lock, journal)
    with cooperative_lock(lock):
        db_gen, json_gen = _read_generation(database, layout)
        if journal.exists():
            record = json.loads(journal.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or record.get("version") != 1:
                raise StageRejected("Invalid journal")
            if record.get("state") not in ("pending", "committed"):
                raise StageRejected("Invalid journal state")
            if type(record.get("from")) is not int or type(record.get("to")) is not int:
                raise StageRejected("Invalid journal generations")
            if record["to"] != record["from"] + 1:
                raise StageRejected("Invalid journal sequence")
            coherent = (db_gen == json_gen == record["to"] and record["state"] == "committed")
            return {"accepted": coherent, "database": db_gen, "layout": json_gen,
                    "journal": record["state"], "requires_review": not coherent}
        return {"accepted": db_gen == json_gen, "database": db_gen, "layout": json_gen,
                "journal": None, "requires_review": db_gen != json_gen}
