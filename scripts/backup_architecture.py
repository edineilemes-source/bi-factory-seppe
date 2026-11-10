"""Offline backup planner. No subprocess, network, source capture or deletion.

Commands contain symbolic bindings, never credentials or operational paths.
Execution is deliberately absent until consistency and custody are validated.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/backup/policy.json"


def load_policy(path=POLICY):
    policy = json.loads(Path(path).read_text())
    if policy["version"] != 1 or any(policy[k] is not False for k in (
        "execution_enabled", "remote_enabled", "schedule_enabled"
    )):
        raise ValueError("Política deve permanecer desativada nesta missão")
    for key in ("daily", "weekly", "monthly"):
        value = policy["retention"][key]
        if type(value) is not int or value < 1:
            raise ValueError("Retenção inválida")
    return policy


def classify(name, policy):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or not path.parts:
        raise ValueError("Somente caminho relativo normalizado")
    # Secrets are never approved for snapshots, including within B/C/D trees.
    if any(p.lower() in {".git", ".env", "secrets.toml", "credentials"}
           or p.lower().startswith(".env.")
           or p.lower().endswith((".pem", ".key", ".seppekey")) for p in path.parts):
        return "REVIEW_SECRET"
    rules = sorted(policy["rules"], key=lambda r: len(r["prefix"]), reverse=True)
    for rule in rules:
        prefix = PurePosixPath(rule["prefix"])
        if path == prefix or prefix in path.parents:
            return rule["class"]
    return "UNCLASSIFIED"  # Do not silently omit unknown or untracked files.


def file_digest(path):
    """Bounded-memory hashing for synthetic/private staging validation."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def restore_target(destination, protected_roots):
    original = Path(destination).absolute()
    if original.exists() or original.is_symlink():
        raise ValueError("Destino deve ser novo")
    target = original.resolve()
    for root in protected_roots:
        root = Path(root).resolve()
        if target == root or root in target.parents or target in root.parents:
            raise ValueError("Destino sobrepõe árvore protegida")
    if not target.parent.is_dir():
        raise ValueError("Pai do destino deve existir")
    return target


def plan(policy, snapshot=None):
    base = ["restic", "--repository-file", "<REPOSITORY_FILE>",
            "--password-file", "<PASSWORD_FILE>"]
    result = {
        "executable": False,
        "bindings": "Resolver somente em ambiente privado aprovado; não usar shell eval",
        "preconditions": ["inventário completo e revisão de segredos inclusive histórico Git",
                          "barreira global validada e staging consistente B+C selado",
                          "destinos privados independentes, custódia e capacidade aprovados"],
        "code": [
            ["git", "clone", "--mirror", "--no-hardlinks", "<AUDITED_SOURCE>", "<NEW_PRIVATE_MIRROR>"],
            ["git", "-C", "<NEW_PRIVATE_MIRROR>", "fsck", "--full"],
            ["git", "-C", "<NEW_PRIVATE_MIRROR>", "bundle", "create", "<NEW_BUNDLE>", "--all"],
            ["git", "-C", "<NEW_PRIVATE_MIRROR>", "bundle", "verify", "<NEW_BUNDLE>"]
        ],
        "data": {
            "initialize_once": base + ["init", "--repository-version", "2"],
            "backup": base + ["backup", "--host", "seppe", "--tag", "seppe-bc",
                              "--", "."],
            "backup_cwd": "<SEALED_STAGE_WITH_B_C_AND_PRIVATE_MANIFEST>",
            "verify": base + ["check", "--read-data"],
            "versions": base + ["snapshots", "--tag", "seppe-bc"],
            "retention_preview": base + ["forget", "--dry-run", "--host", "seppe",
                "--tag", "seppe-bc", "--group-by", "host,tags",
                "--keep-daily", str(policy["retention"]["daily"]),
                "--keep-weekly", str(policy["retention"]["weekly"]),
                "--keep-monthly", str(policy["retention"]["monthly"])]
        }
    }
    if snapshot is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", snapshot):
            raise ValueError("Exigir ID completo e explícito do snapshot")
        result["data"]["restore"] = base + ["restore", snapshot, "--target", "<NEW_ISOLATED_TARGET>", "--verify"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", help="ID completo para preparar restauração")
    args = parser.parse_args()
    print(json.dumps(plan(load_policy(), args.snapshot), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
