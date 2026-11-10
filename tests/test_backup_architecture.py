import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "architecture", Path(__file__).resolve().parents[1] / "scripts/backup_architecture.py")
architecture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(architecture)


@pytest.mark.parametrize("name,expected", [
    ("storage/information_products/layouts/example.json", "B"),
    ("storage/dashboard_projects/products/example.json", "B"),
    ("storage/working/prepared-real-test/example.jsonl", "C"),
    ("storage/new-module/example.bin", "C"),
    ("artifacts/staged/example.csv", "C"),
    ("web/bi_factory/dist/index.html", "D"),
    ("storage2/example", "UNCLASSIFIED"),
    ("unknown.bak", "UNCLASSIFIED"),
    ("storage/.env", "REVIEW_SECRET"),
    ("storage/nested/key.pem", "REVIEW_SECRET"),
    (".git/config", "REVIEW_SECRET"),
])
def test_classification(name, expected):
    assert architecture.classify(name, architecture.load_policy()) == expected


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../b", "a\\b", "."])
def test_invalid_names(name):
    with pytest.raises(ValueError):
        architecture.classify(name, architecture.load_policy())


@pytest.mark.parametrize("flag", ["execution_enabled", "remote_enabled", "schedule_enabled"])
def test_fail_closed_policy(tmp_path, flag):
    policy = copy.deepcopy(architecture.load_policy())
    policy[flag] = True
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError):
        architecture.load_policy(path)


def test_plan_has_no_execution_or_destructive_retention():
    plan = architecture.plan(architecture.load_policy(), "a" * 64)
    assert plan["executable"] is False
    assert "--dry-run" in plan["data"]["retention_preview"]
    assert "--verify" in plan["data"]["restore"]
    assert "--all" in plan["code"][2]
    assert "--mirror" in plan["code"][0]
    assert "--read-data" in plan["data"]["verify"]
    assert "prune" not in json.dumps(plan)


@pytest.mark.parametrize("snapshot", ["latest", "abc123", "../escape", "a" * 63])
def test_explicit_snapshot(snapshot):
    with pytest.raises(ValueError):
        architecture.plan(architecture.load_policy(), snapshot)


def test_restore_protection(tmp_path):
    protected = tmp_path / "source"
    protected.mkdir()
    sentinel = protected / "keep"
    sentinel.write_text("synthetic")
    alias = tmp_path / "alias"
    alias.symlink_to(protected, target_is_directory=True)
    for destination in (protected, sentinel, protected / "new", alias / "new", tmp_path):
        with pytest.raises(ValueError):
            architecture.restore_target(destination, [protected])
    target = tmp_path / "isolated"
    assert architecture.restore_target(target, [protected]) == target
    assert not target.exists()
    assert sentinel.read_text() == "synthetic"


def test_streaming_digest_multichunk(tmp_path):
    path = tmp_path / "synthetic.bin"
    data = b"synthetic" * 400000
    path.write_bytes(data)
    assert architecture.file_digest(path) == hashlib.sha256(data).hexdigest()


def test_streaming_multi_gigabyte_without_allocation():
    # Simulate >4 GiB reads. Not a throughput or real Restic capacity test.
    from unittest.mock import patch
    block = b"x" * (1024 * 1024)

    class Stream:
        remaining = 4097
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, size):
            assert size == len(block)
            self.remaining -= 1
            return block if self.remaining >= 0 else b""

    with patch.object(Path, "open", return_value=Stream()):
        assert len(architecture.file_digest("synthetic")) == 64
