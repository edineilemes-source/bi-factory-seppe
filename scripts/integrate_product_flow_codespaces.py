#!/usr/bin/env python3
"""One-shot, non-destructive integration of two BI Factory UI files in Codespaces.

Invoked from an authenticated GitHub branch: git show FETCH_HEAD:<this file> | python3 -
Never switches branches, touches operational storage, commits, resets, or pushes.
"""
import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path("/workspaces/bi-factory-seppe")
BRANCH = "feat/fluxo-salvamento-unico-produto-20261116"
LOCAL_BRANCH = "teste/cadastro-filtros-20261113"
BASE = "8d2c34106c6d18d9133592467c425a51baca0cf1"
PATHS = ("web/bi_factory/src/main.jsx", "prototypes/editor-visual/index.html")

def run(args, *, input=None, check=True):
    return subprocess.run(args, cwd=ROOT, input=input, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=check)

def git(*args):
    return run(["git", *args]).stdout

def main():
    if not ROOT.is_dir() or not (ROOT / ".git").exists():
        raise RuntimeError("Repositório Codespaces não localizado; nenhuma alteração feita")
    current_branch = git("branch", "--show-current").decode().strip()
    if current_branch != LOCAL_BRANCH:
        raise RuntimeError(f"Branch local inesperada: {current_branch}; nenhuma alteração feita")
    print("Verificando a origem GitHub...", flush=True)
    git("fetch", "--no-tags", "origin", BRANCH)
    target = git("rev-parse", "FETCH_HEAD").decode().strip()
    git("merge-base", "--is-ancestor", BASE, target)
    # Lock to prevent parallel integration runs.
    lockfile = ROOT / ".git/bi-factory-integration.lock"
    import fcntl
    with lockfile.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        originals = {}
        merged = {}
        with tempfile.TemporaryDirectory(prefix="bi-flow-merge-") as td:
            directory = Path(td)
            for index, rel in enumerate(PATHS):
                file = ROOT / rel
                if not file.is_file() or file.is_symlink():
                    raise RuntimeError(f"Arquivo local ausente ou link: {rel}; nenhuma alteração feita")
                local = file.read_bytes()
                ancestor = git("show", f"{BASE}:{rel}")
                incoming = git("show", f"{target}:{rel}")
                originals[rel] = local
                if local == incoming:
                    result = local
                elif local == ancestor:
                    result = incoming
                elif incoming == ancestor:
                    result = local
                else:
                    a, b, c = [directory / f"{index}-{label}" for label in ("local", "base", "incoming")]
                    a.write_bytes(local); b.write_bytes(ancestor); c.write_bytes(incoming)
                    merge = run(["git", "merge-file", "-p", str(a), str(b), str(c)], check=False)
                    if merge.returncode != 0:
                        # Only the explicitly reviewed, user-published local snapshot may
                        # be reconciled this way. A changed local file always blocks.
                        if rel != "web/bi_factory/src/main.jsx":
                            raise RuntimeError(f"CONFLITO em {rel}; nenhum arquivo alterado")
                        import json
                        fetched = run([
                            "gh", "api",
                            "repos/edineilemes-source/bi-factory-seppe/issues/21/comments",
                            "--paginate",
                        ], check=False)
                        if fetched.returncode:
                            raise RuntimeError(
                                "Não foi possível verificar o snapshot local da issue #21"
                            )
                        try:
                            comments = json.loads(fetched.stdout.decode())
                        except (UnicodeDecodeError, ValueError):
                            raise RuntimeError("Resposta inválida da issue #21")
                        snapshots = [
                            c.get("body", "") for c in comments
                            if c.get("user", {}).get("login") == "edineilemes-source"
                            and c.get("body", "").startswith('import React,')
                        ]
                        if not any(snapshot.encode() == local for snapshot in snapshots):
                            raise RuntimeError(
                                "Arquivo local diverge do snapshot revisado da issue #21; "
                                "nenhum arquivo alterado"
                            )
                        # The incoming main.jsx was reviewed against this exact snapshot:
                        # legacy protections remain; changed lines concern the new workflow.
                        required = [
                            "creationPending.current=true",
                            "finally{creationPending.current=false;setCreatingProduct(false)}",
                            "if(creatingProduct)return;",
                            "function startNewProductEditor()",
                            "async function saveVisualFromEditor(layout)",
                        ]
                        if not all(term in incoming.decode() for term in required):
                            raise RuntimeError("Nova versão não contém todas as proteções exigidas")
                        result = incoming
                        print("main.jsx reconciliado com snapshot exato da issue #21", flush=True)
                    else:
                        result = merge.stdout
                if b"<<<<<<< " in result or b">>>>>>> " in result:
                    raise RuntimeError(f"Marcadores de conflito em {rel}; nenhuma alteração feita")
                merged[rel] = result
            changed = [rel for rel in PATHS if originals[rel] != merged[rel]]
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = ROOT / ".git/backups" / f"integracao-validada-{stamp}"
            # A permanent snapshot before attempting any write.
            for rel, content in originals.items():
                dest = backup / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
            print(f"Backup permanente: {backup}", flush=True)
            def restore():
                for rel in changed:
                    (ROOT / rel).write_bytes(originals[rel])
            try:
                for rel in changed:
                    dst = ROOT / rel
                    temp = dst.with_name(dst.name + ".bi-integration-tmp")
                    if temp.exists():
                        raise RuntimeError(f"Arquivo temporário já existe: {temp}")
                    try:
                        temp.write_bytes(merged[rel])
                        os.chmod(temp, dst.stat().st_mode & 0o777)
                        os.replace(temp, dst)
                    finally:
                        if temp.exists():
                            temp.unlink()
                print("Validando build sem tocar nos produtos...", flush=True)
                build = run(["npm", "run", "build", "--prefix", "web/bi_factory"], check=False)
                if build.returncode:
                    details = (build.stdout + build.stderr).decode(errors="replace")[-3500:]
                    raise RuntimeError("Build falhou; restauração automática efetuada. " + details)
            except Exception:
                restore()
                raise
            print("INTEGRAÇÃO E BUILD APROVADOS", flush=True)
            print("Branch local preservada, sem commit/push/reset.", flush=True)
            print("Alterados:", ", ".join(changed) if changed else "nenhum; código já coincidia", flush=True)
            print("Nenhum arquivo em storage/ foi modificado.", flush=True)
            print(f"Commit remoto de referência: {target}", flush=True)
            print("Atualize o navegador da porta 8506 para homologar.", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"INTEGRAÇÃO BLOQUEADA: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
