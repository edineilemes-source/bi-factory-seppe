#!/usr/bin/env python3
"""Instala somente a correção visual do formulário Conhecimento; nunca altera storage."""
from pathlib import Path
import datetime
import os
import subprocess
import sys

ROOT = Path("/workspaces/bi-factory-seppe")
BASE = "origin/feat/onboarding-projetos-conhecimento-20261117"
TARGET = "origin/fix/conhecimento-selecao-documentos-20261119"
PATHS = ["web/bi_factory/src/KnowledgeStart.jsx", "web/bi_factory/src/style.css"]

def git_show(ref, path):
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT)

def main():
    if not (ROOT / ".git").is_dir():
        raise RuntimeError("Diretório do projeto não encontrado")
    changes = {}
    for path in PATHS:
        file = ROOT / path
        if not file.is_file() or file.is_symlink():
            raise RuntimeError("Arquivo ausente ou link simbólico: " + path)
        current = file.read_bytes()
        before, after = git_show(BASE, path), git_show(TARGET, path)
        if current == after:
            continue
        if current != before:
            raise RuntimeError("Arquivo possui mudanças locais diferentes da base; preservado: " + path)
        changes[path] = (current, after)
    if not changes:
        print("Interface já possui a correção visual. Atualize o navegador.")
        return
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / ".git" / "backups" / ("conhecimento-ui-" + stamp)
    for path, (old, _) in changes.items():
        saved = backup / path
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(old)
    try:
        for path, (_, new) in changes.items():
            file = ROOT / path
            temp = file.with_name(file.name + ".knowledge-ui-new")
            temp.write_bytes(new)
            os.chmod(temp, file.stat().st_mode & 0o777)
            os.replace(temp, file)
        subprocess.run(["npm", "run", "build"], cwd=ROOT / "web/bi_factory", check=True)
    except Exception:
        for path, (old, _) in changes.items():
            (ROOT / path).write_bytes(old)
        raise
    print("CORREÇÃO VISUAL INSTALADA. Build aprovado.")
    print("Arquivos alterados:", ", ".join(changes))
    print("Backup:", backup)
    print("Atualize a página da porta 8506 com Ctrl+Shift+R.")
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("INSTALAÇÃO BLOQUEADA / REVERTIDA:", exc, file=sys.stderr)
        sys.exit(1)
