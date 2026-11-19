#!/usr/bin/env python3
"""Mescla seletores Ano/Bimestre/Dimensões/Medidas em editores locais existentes.

Protege customizações do Codespaces: aplica diff de três vias com base GitHub,
valida sintaxe do JavaScript e faz backup. Não altera storage nem troca branch.
Qualquer conflito impede todas as gravações.
"""
from __future__ import annotations
import datetime
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/workspaces/bi-factory-seppe")
BASE = "origin/feat/stn-produtos-2026"
TARGET = "origin/fix/echarts-dimensoes-medidas-20261119"
PATHS = [
    "prototypes/editor-visual/index.html",
    "prototypes/editor-visual/echarts-studio.html",
]

def git_show(revision: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", revision + ":" + path], cwd=ROOT, capture_output=True
    )
    if result.returncode:
        raise RuntimeError("Referência Git indisponível: " + revision + ":" + path)
    return result.stdout

def merge_three_way(current: bytes, base: bytes, target: bytes, path: str) -> bytes:
    if current == target:
        return current
    if current == base:
        return target
    with tempfile.TemporaryDirectory(prefix="bi-factory-merge-") as directory:
        paths = [Path(directory) / name for name in ("local", "base", "novo")]
        for name, data in zip(paths, (current, base, target)):
            name.write_bytes(data)
        merged = subprocess.run(
            ["git", "merge-file", "-p", "--diff3", str(paths[0]), str(paths[1]), str(paths[2])],
            cwd=ROOT, capture_output=True
        )
        if merged.returncode != 0:
            if merged.returncode == 1:
                raise RuntimeError(
                    "Conflito real de conteúdo em " + path
                    + ". Nada foi sobrescrito. Precisamos preservar essas personalizações."
                )
            raise RuntimeError("Falha ao mesclar " + path + ": "
                               + merged.stderr.decode("utf-8", errors="replace")[:300])
        result = merged.stdout
        if b"<<<<<<<" in result or b">>>>>>>" in result:
            raise RuntimeError("Marcadores de conflito detectados em " + path)
        return result

def validate_inline_js(path: str, content: bytes) -> None:
    page = content.decode("utf-8")
    chunks = [
        match.group(1)
        for match in re.finditer(r"<script[^>]*>(.*?)</script>", page,
                                 flags=re.IGNORECASE | re.DOTALL)
        if match.group(1).strip()
    ]
    if not chunks:
        raise RuntimeError("Nenhum JavaScript encontrado em " + path)
    with tempfile.TemporaryDirectory(prefix="bi-factory-js-check-") as directory:
        for index, script in enumerate(chunks):
            js_path = Path(directory) / ("inline-" + str(index) + ".js")
            js_path.write_text(script, encoding="utf-8")
            response = subprocess.run(
                ["node", "--check", str(js_path)], capture_output=True, text=True
            )
            if response.returncode:
                raise RuntimeError(
                    "Validação JavaScript falhou em " + path + ": "
                    + response.stderr[-1200:]
                )

def main() -> None:
    if not (ROOT / ".git").is_dir():
        raise RuntimeError("Codespaces BI Factory não encontrado")
    proposed = {}
    for name in PATHS:
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("Arquivo não encontrado ou link simbólico: " + name)
        old = path.read_bytes()
        candidate = merge_three_way(old, git_show(BASE, name), git_show(TARGET, name), name)
        validate_inline_js(name, candidate)
        proposed[name] = (old, candidate)

    changed = {name: pair for name, pair in proposed.items() if pair[0] != pair[1]}
    if not changed:
        print("Os dois editores já estão atualizados e passaram na validação.")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / ".git" / "backups" / ("echarts-merge-" + stamp)
    for name, (old, _new) in changed.items():
        destination = backup / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(old)

    applied = []
    try:
        for name, (old, new) in changed.items():
            destination = ROOT / name
            pending = destination.with_name(destination.name + ".echarts-merge-pending")
            if pending.exists():
                raise RuntimeError("Arquivo temporário existente: " + name)
            try:
                pending.write_bytes(new)
                os.chmod(pending, destination.stat().st_mode & 0o777)
                os.replace(pending, destination)
                applied.append(name)
            finally:
                pending.unlink(missing_ok=True)
    except Exception:
        for name in applied:
            (ROOT / name).write_bytes(changed[name][0])
        raise

    print("MESCLAGEM CONCLUÍDA — Código original preservado.")
    print("Arquivos atualizados:", ", ".join(applied))
    print("Backup:", backup)
    print("JavaScript dos dois editores: válido.")
    print("Feche e reabra o Editor Visual e o ECharts; atualize a página com Ctrl+Shift+R.")
    print("Portas, produtos, dados fiscais e branch atual não foram modificados.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ATUALIZAÇÃO NÃO APLICADA:", exc, file=sys.stderr)
        sys.exit(1)
