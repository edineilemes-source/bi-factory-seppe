"""Crash-journal tests use private synthetic tmp_path fixtures only."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "fixture_generation", SCRIPTS / "backup_fixture_generation.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def fixtures(tmp_path):
    root = tmp_path / "synthetic"
    root.mkdir(mode=0o700)
    db = root / "state.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE fixture_state (generation INTEGER NOT NULL)")
        connection.execute("INSERT INTO fixture_state VALUES (1)")
    db.chmod(0o600)
    layout = root / "layout.json"
    layout.write_text(json.dumps({"generation": 1, "widgets": ["sample"]}))
    layout.chmod(0o600)
    lock = root / "write.lock"
    lock.touch(mode=0o600)
    journal = root / "generation.journal.json"
    return db, layout, lock, journal


def test_complete_generation_is_accepted(fixtures):
    assert module.commit_generation(*fixtures, 2) == 2
    result = module.inspect_generation(*fixtures)
    assert result == {"accepted": True, "database": 2, "layout": 2,
                      "journal": "committed", "requires_review": False}


@pytest.mark.parametrize("point,db_expected", [
    ("after_journal", 1),
    ("after_database", 2),
])
def test_crash_is_rejected_and_not_overwritten(fixtures, point, db_expected):
    with pytest.raises(module.StageRejected):
        module.commit_generation(*fixtures, 2, inject_crash=point)
    result = module.inspect_generation(*fixtures)
    assert result["accepted"] is False
    assert result["requires_review"] is True
    assert result["database"] == db_expected
    assert result["layout"] == 1
    assert result["journal"] == "pending"
    with pytest.raises(module.StageRejected):
        module.commit_generation(*fixtures, 2)
    assert fixtures[3].exists()


def test_reject_skipped_generation(fixtures):
    with pytest.raises(module.StageRejected):
        module.commit_generation(*fixtures, 4)
    assert not fixtures[3].exists()


def test_reject_existing_symlink_journal(fixtures):
    journal = fixtures[3]
    journal.symlink_to(fixtures[1])
    with pytest.raises(module.StageRejected):
        module.commit_generation(*fixtures, 2)
    assert fixtures[1].exists()


def test_reject_tampered_journal(fixtures):
    module.commit_generation(*fixtures, 2)
    fixtures[3].write_text('{"version":1,"state":"committed","from":1,"to":99}')
    with pytest.raises(module.StageRejected):
        module.inspect_generation(*fixtures)


def test_read_only_inspection_does_not_change_fixtures(fixtures):
    before = fixtures[1].read_bytes()
    assert module.inspect_generation(*fixtures)["accepted"] is True
    assert fixtures[1].read_bytes() == before
    assert not fixtures[3].exists()
