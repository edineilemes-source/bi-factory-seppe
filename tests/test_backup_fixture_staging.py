"""Tests use only tmp_path fixtures; never open BI Factory operational data."""
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

spec = importlib.util.spec_from_file_location(
    "fixture_staging", Path(__file__).resolve().parents[1] / "scripts/backup_fixture_staging.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def fixture_set(tmp_path):
    source = tmp_path / "fixtures"
    source.mkdir(mode=0o700)
    scratch = tmp_path / "scratch"
    scratch.mkdir(mode=0o700)
    db = source / "test.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE fixture_state (generation INTEGER NOT NULL)")
        connection.execute("INSERT INTO fixture_state VALUES (7)")
    db.chmod(0o600)
    layout = source / "layout.json"
    layout.write_text(json.dumps({"generation": 7, "widgets": ["synthetic"]}))
    layout.chmod(0o600)
    lock = source / "writer.lock"
    lock.touch(mode=0o600)
    return db, layout, lock, scratch


def test_coordinated_stage_and_integrity(fixture_set):
    db, layout, lock, scratch = fixture_set
    stage = module.stage_fixture(db, layout, lock, scratch, 7)
    manifest = module.verify_stage(stage)
    assert manifest["generation"] == 7
    assert manifest["kind"] == "synthetic-fixture-only"
    assert {p.name for p in stage.iterdir()} == {
        "snapshot.sqlite3", "layout.json", "manifest.json"}
    assert db.exists() and layout.exists()
    assert stage.parent == scratch


def test_reject_mismatched_generation_without_leaving_stage(fixture_set):
    db, layout, lock, scratch = fixture_set
    layout.write_text('{"generation":6}')
    with pytest.raises(module.StageRejected):
        module.stage_fixture(db, layout, lock, scratch, 7)
    assert list(scratch.iterdir()) == []
    assert layout.read_text() == '{"generation":6}'


def test_reject_database_generation_without_leaving_stage(fixture_set):
    db, layout, lock, scratch = fixture_set
    with pytest.raises(module.StageRejected):
        module.stage_fixture(db, layout, lock, scratch, 8)
    assert list(scratch.iterdir()) == []


def test_detect_tampering(fixture_set):
    db, layout, lock, scratch = fixture_set
    stage = module.stage_fixture(db, layout, lock, scratch, 7)
    (stage / "layout.json").write_text('{"generation":7,"tampered":true}')
    with pytest.raises(module.StageRejected):
        module.verify_stage(stage)


def test_reject_symlink_and_preserve_origin(fixture_set):
    db, layout, lock, scratch = fixture_set
    alias = db.parent / "db-alias"
    alias.symlink_to(db)
    with pytest.raises(module.StageRejected):
        module.stage_fixture(alias, layout, lock, scratch, 7)
    assert db.exists() and list(scratch.iterdir()) == []


def test_reject_public_scratch(fixture_set):
    db, layout, lock, scratch = fixture_set
    scratch.chmod(0o755)
    with pytest.raises(module.StageRejected):
        module.stage_fixture(db, layout, lock, scratch, 7)


def test_reject_extra_staged_entries(fixture_set):
    db, layout, lock, scratch = fixture_set
    stage = module.stage_fixture(db, layout, lock, scratch, 7)
    (stage / "unexpected.txt").write_text("synthetic")
    with pytest.raises(module.StageRejected):
        module.verify_stage(stage)
