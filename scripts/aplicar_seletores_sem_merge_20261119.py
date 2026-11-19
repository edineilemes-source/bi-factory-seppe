#!/usr/bin/env python3
"""Aplica somente as diferenças pontuais dos seletores sobre HTMLs locais divergentes.
Mutações no código somente após todas as verificações. Não toca nos dados/produtos.
"""
from pathlib import Path
from difflib import SequenceMatcher
import datetime
import os
import subprocess
import sys
import tempfile
import re

ROOT = Path("/workspaces/bi-factory-seppe")
BASE = "origin/feat/stn-produtos-2026"
NEW = "origin/fix/echarts-dimensoes-medidas-20261119"
FILES = ("prototypes/editor-visual/index.html",
         "prototypes/editor-visual/echarts-studio.html")

def remote(ref, path):
    result = subprocess.run(["git", "show", ref + ":" + path],
                            cwd=ROOT, capture_output=True)
    if result.returncode:
        raise RuntimeError("Não foi possível ler " + ref + ":" + path +
                           " — " + result.stderr.decode(errors="replace")[-400:])
    return result.stdout.decode("utf-8")

def atomic_patches(before, after):
    """Hunks pequenos com âncoras; nunca substitui uma linha inteira personalizada."""
    sequence = SequenceMatcher(None, before.splitlines(keepends=True),
                               after.splitlines(keepends=True), autojunk=False)
    patches = []
    a_lines = before.splitlines(keepends=True)
    b_lines = after.splitlines(keepends=True)
    for code, a0, a1, b0, b1 in sequence.get_opcodes():
        if code == "equal":
            continue
        old = "".join(a_lines[a0:a1])
        new = "".join(b_lines[b0:b1])
        if not old:
            left = "".join(a_lines[:a0])[-90:]
            right = "".join(a_lines[a0:])[:90]
            patches.append((left + right, left + new + right))
            continue
        if not new:
            left = "".join(a_lines[:a0])[-90:]
            right = "".join(a_lines[a1:])[:90]
            patches.append((left + old + right, left + right))
            continue
        # Emparelha caracteres mantendo o contexto original ao redor de cada alteração.
        spans = SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
        edits = [(i,j,k,l) for tag,i,j,k,l in spans if tag != "equal"]
        if not edits:
            continue
        groups = []
        for edit in edits:
            if groups and edit[0] - groups[-1][-1][1] <= 100:
                groups[-1].append(edit)
            else:
                groups.append([edit])
        for group in groups:
            a_start,a_end = group[0][0],group[-1][1]
            b_start,b_end = group[0][2],group[-1][3]
            left = old[max(0,a_start-90):a_start]
            right = old[a_end:min(len(old),a_end+90)]
            patches.append((left+old[a_start:a_end]+right,
                            left+new[b_start:b_end]+right))
    return patches

def apply(local, old, target, path):
    if local == target:
        return local, 0
    if local == old:
        return target, 1
    patches = atomic_patches(old, target)
    result = local
    changed = 0
    # Edits com contextos não sobrepostos são aplicados de trás para frente.
    for i,(needle,replacement) in enumerate(reversed(patches),start=1):
        original_count = result.count(needle)
        if original_count == 1:
            result = result.replace(needle,replacement,1)
            changed += 1
        elif result.count(replacement) == 1:
            continue
        else:
            clue = needle.strip()[:130].replace("\n"," ")
            raise RuntimeError(
                "Trecho local diferente em " + path + " (parte " +
                str(len(patches)-i+1) + " de " + str(len(patches)) +
                "; ocorrências=" + str(original_count) + "). " +
                "Trecho esperado: " + repr(clue))
    return result,changed

def check_js(name, text):
    scripts = [m.group(1) for m in re.finditer(
        r"<script[^>]*>(.*?)</script>", text, flags=re.I|re.S)
        if m.group(1).strip()]
    if not scripts:
        raise RuntimeError("Nenhum JavaScript incorporado encontrado em " + name)
    for script in scripts:
        with tempfile.NamedTemporaryFile(mode="w",suffix=".js",encoding="utf-8",delete=False) as file:
            file.write(script)
            tmp = Path(file.name)
        try:
            result = subprocess.run(["node","--check",str(tmp)],capture_output=True,text=True)
            if result.returncode:
                raise RuntimeError("JS inválido em "+name+": "+result.stderr[-1000:])
        finally:
            tmp.unlink(missing_ok=True)

def main():
    if not (ROOT/".git").is_dir():
        raise RuntimeError("Projeto BI Factory não encontrado")
    candidate = {}
    for name in FILES:
        path = ROOT/name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("Arquivo ausente ou link simbólico: "+name)
        current = path.read_text(encoding="utf-8")
        updated,n = apply(current,remote(BASE,name),remote(NEW,name),name)
        check_js(name,updated)
        candidate[name] = (current,updated,n)
        print("VALIDADO:",name,"—",n,"alterações localizadas")
    updates = {name:(a,b) for name,(a,b,_) in candidate.items() if a!=b}
    if not updates:
        print("Os dois editores já estão na versão atualizada.")
        return
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup=ROOT/".git"/"backups"/("seletor-local-"+stamp)
    for name,(old,_) in updates.items():
        destination=backup/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(old,encoding="utf-8")
    written=[]
    try:
        for name,(old,new) in updates.items():
            destination=ROOT/name
            tmp=destination.with_name(destination.name+".seletores-new")
            if tmp.exists():
                raise RuntimeError("Arquivo temporário preexistente: "+str(tmp))
            try:
                tmp.write_text(new,encoding="utf-8")
                os.chmod(tmp,destination.stat().st_mode&0o777)
                os.replace(tmp,destination)
                written.append(name)
            finally:
                tmp.unlink(missing_ok=True)
    except Exception:
        for name in written:
            (ROOT/name).write_text(updates[name][0],encoding="utf-8")
        raise
    print("CORREÇÃO APLICADA aos editores; alterações locais preservadas.")
    print("Backup:",backup)
    print("Feche/reabra ECharts e Editor Visual; Ctrl+Shift+R no navegador.")
    print("Nenhum dado, layout salvo ou produto foi alterado.")

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("NÃO APLICADO:",exc,file=sys.stderr)
        sys.exit(1)
