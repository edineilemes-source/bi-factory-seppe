"""Synthetic-only coordinated SQLite+JSON staging. Not a production backup runner.

No CLI, network, Restic, operational paths or deletion. The caller must supply
a dedicated scratch directory. All writers must cooperate on the same lock;
this module makes no claim about real BI writers or distributed consistency.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile

try:
    import fcntl
except ImportError:
    fcntl = None


class StageRejected(ValueError):
    pass


def _digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _regular_private(path):
    path = Path(path)
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or path.is_symlink() or mode & 0o077:
        raise StageRejected("Expected private regular fixture")


def _safe_directory(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise StageRejected("Expected existing scratch directory")
    if path.resolve() == Path.cwd().resolve():
        raise StageRejected("Scratch directory must not be repository root")
    return path.resolve()


@contextmanager
def cooperative_lock(lock_path):
    """Exclusive POSIX lock; writers must use this lock around both writes."""
    if fcntl is None:
        raise StageRejected("POSIX flock unavailable")
    lock_path = Path(lock_path)
    _regular_private(lock_path)
    fd = os.open(lock_path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def stage_fixture(database, layout, lock_path, scratch, generation):
    """Capture fixtures to a sealed directory, rejecting mismatch and bad inputs.

    The staging directory is created exclusively inside a preexisting private
    scratch root. Never reads a live BI database. No cleanup of existing data.
    """
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        raise StageRejected("Invalid generation")
    scratch = _safe_directory(scratch)
    if scratch.stat().st_mode & 0o077:
        raise StageRejected("Scratch directory must be private")
    database, layout, lock_path = map(Path, (database, layout, lock_path))
    for path in (database, layout, lock_path):
        _regular_private(path)
        if scratch == path.resolve() or scratch in path.resolve().parents:
            raise StageRejected("Fixtures must be outside scratch")
    stage = None
    with cooperative_lock(lock_path):
        try:
            stage = Path(tempfile.mkdtemp(prefix="sealed-fixture-", dir=scratch))
            stage.chmod(0o700)
            db_copy = stage / "snapshot.sqlite3"
            with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as source:
                with sqlite3.connect(db_copy) as target:
                    source.backup(target)
            db_copy.chmod(0o600)
            with sqlite3.connect(f"file:{db_copy.resolve()}?mode=ro", uri=True) as db:
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise StageRejected("Invalid SQLite fixture")
                if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise StageRejected("Invalid SQLite foreign keys")
                db_generation = db.execute("SELECT generation FROM fixture_state").fetchone()
            if db_generation is None or db_generation[0] != generation:
                raise StageRejected("Database generation mismatch")
            with layout.open("rb") as stream:
                raw = stream.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise StageRejected("Fixture JSON too large")
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("generation") != generation or type(data["generation"]) is not int:
                raise StageRejected("Layout generation mismatch")
            json_copy = stage / "layout.json"
            with json_copy.open("xb") as output:
                output.write(raw)
            json_copy.chmod(0o600)
            manifest = {
                "version": 1,
                "kind": "synthetic-fixture-only",
                "generation": generation,
                "files": {
                    name: {"bytes": (stage / name).stat().st_size,
                           "sha256": _digest(stage / name)}
                    for name in ("snapshot.sqlite3", "layout.json")
                },
            }
            manifest_path = stage / "manifest.json"
            with manifest_path.open("x", encoding="utf-8") as output:
                json.dump(manifest, output, sort_keys=True)
            manifest_path.chmod(0o600)
            verify_stage(stage)
            return stage
        except BaseException:
            if stage is not None:
                shutil.rmtree(stage)
            raise


def verify_stage(stage):
    """Verify a previously sealed fixture without modifying its contents."""
    stage = Path(stage)
    if stage.is_symlink() or not stage.is_dir():
        raise StageRejected("Invalid stage")
    expected = {"snapshot.sqlite3", "layout.json", "manifest.json"}
    if {p.name for p in stage.iterdir()} != expected:
        raise StageRejected("Unexpected staged entries")
    for name in expected:
        _regular_private(stage / name)
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or manifest.get("kind") != "synthetic-fixture-only":
        raise StageRejected("Invalid fixture manifest")
    if set(manifest.get("files", {})) != expected - {"manifest.json"}:
        raise StageRejected("Incomplete fixture manifest")
    for name, info in manifest["files"].items():
        if info != {"bytes": (stage / name).stat().st_size,
                    "sha256": _digest(stage / name)}:
            raise StageRejected("Fixture integrity mismatch")
    with sqlite3.connect(f"file:{(stage / 'snapshot.sqlite3').resolve()}?mode=ro", uri=True) as db:
        row = db.execute("SELECT generation FROM fixture_state").fetchone()
        if row is None or row[0] != manifest["generation"]:
            raise StageRejected("SQLite fixture mismatch")
    if json.loads((stage / "layout.json").read_text())["generation"] != manifest["generation"]:
        raise StageRejected("JSON fixture mismatch")
    return manifest
