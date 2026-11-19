#!/usr/bin/env python3
"""Instala criação de painéis ECharts no Codespaces já atualizado em 19/11/2026.

Somente 2 HTMLs dos editores e 1 biblioteca JS local (Apache ECharts).
Base: instalação bem-sucedida dos combos Ano/Bimestre do usuário.
Checa integridade e JS antes de escrever. Não altera API, storage ou branch.
"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT=Path("/workspaces/bi-factory-seppe")
BASE="origin/fix/echarts-instalar-base-real-20261119"
NEW="origin/feat/echarts-dashboard-estilo-referencia-20261119"
FILES=(
 "prototypes/editor-visual/index.html",
 "prototypes/editor-visual/echarts-studio.html",
 "prototypes/editor-visual/echarts-bi-options.js",
 "scripts/test_echarts_dashboard.js",
)

def git(ref,path):
    cmd=subprocess.run(["git","show",f"{ref}:{path}"],cwd=ROOT,capture_output=True)
    return cmd.stdout if cmd.returncode==0 else None

def check_js(path,blob):
    content=blob.decode("utf-8")
    code=[content] if path.endswith(".js") else [
        m.group(1) for m in re.finditer(
            r"<script[^>]*>(.*?)</script>",content,re.I|re.S
        ) if m.group(1).strip()
    ]
    if not code:raise RuntimeError("Nenhum JS encontrado em "+path)
    for part in code:
        with tempfile.NamedTemporaryFile(
            "w",suffix=".js",encoding="utf-8",delete=False
        ) as output:
            output.write(part)
            tmp=Path(output.name)
        try:
            result=subprocess.run(["node","--check",str(tmp)],capture_output=True,text=True)
            if result.returncode:
                raise RuntimeError("JS inválido: "+path+" "+result.stderr[-1200:])
        finally:tmp.unlink(missing_ok=True)

def sha(value):
    return hashlib.sha256(value).hexdigest()[:16]

def main():
    if not (ROOT/".git").is_dir():raise RuntimeError("Codespaces do BI Factory não encontrado")
    changed={}
    for name in FILES:
        local=ROOT/name
        if local.is_symlink():raise RuntimeError("Link simbólico recusado: "+name)
        previous=git(BASE,name)
        updated=git(NEW,name)
        if updated is None:raise RuntimeError("Código novo indisponível em "+name)
        if local.exists() and not local.is_file():
            raise RuntimeError("Caminho não é arquivo: "+name)
        original=local.read_bytes() if local.exists() else None
        check_js(name,updated)
        if original==updated:
            print("Já instalado:",name)
            continue
        if original!=previous:
            raise RuntimeError("Arquivo local diferente da versão homologada: "+name+
                               " | local="+sha(original or b"")+
                               " | esperado="+sha(previous or b"")+
                               ". Nada foi sobrescrito.")
        changed[name]=(original,updated)
        print("Validado:",name," | origem:",sha(original or b""),
              "| novo:",sha(updated))
    if not changed:
        print("MODELO DE PAINEL JÁ INSTALADO.")
    else:
        stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup=ROOT/".git"/"backups"/("echarts-modelo-painel-"+stamp)
        for name,(previous,_) in changed.items():
            if previous is not None:
                dest=backup/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(previous)
        applied=[]
        try:
            for name,(_,updated) in changed.items():
                target=ROOT/name
                target.parent.mkdir(parents=True,exist_ok=True)
                pending=target.with_name(target.name+".painel-new")
                if pending.exists():raise RuntimeError("Arquivo temporário preexistente: "+name)
                try:
                    pending.write_bytes(updated)
                    if target.exists():
                        os.chmod(pending,target.stat().st_mode&0o777)
                    os.replace(pending,target)
                    applied.append(name)
                finally:pending.unlink(missing_ok=True)
            for name in FILES:
                check_js(name,(ROOT/name).read_bytes())
            subprocess.run(["node","scripts/test_echarts_dashboard.js"],cwd=ROOT,check=True)
        except Exception:
            for name in applied:
                old=changed[name][0]
                if old is None:(ROOT/name).unlink(missing_ok=True)
                else:(ROOT/name).write_bytes(old)
            raise
        print("INSTALAÇÃO CONCLUÍDA:",", ".join(applied))
        print("Backup:",backup)

    # A rota estática existente não requer reinício da API.
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8505/visual-editor/echarts-bi-options.js",timeout=4
        ) as r:
            payload=r.read()
            print("Biblioteca compartilhada no servidor 8505:",r.status,
                  "bytes:",len(payload))
            if r.status!=200 or b"BIFactoryChartOptions" not in payload:
                print("ATENÇÃO: rota estática não serviu a biblioteca esperada.")
    except Exception as exc:
        print("ATENÇÃO: não foi possível testar o JS via porta 8505:",exc)

    try:
        with urllib.request.urlopen("http://127.0.0.1:8505/api/fiscal",timeout=6) as r:
            rows=json.load(r)
        periods={(str(row.get("ano",row.get("exercicio"))),str(row.get("bimestre")))
                 for row in rows}
        print("API fiscal mantida:",len(periods),"períodos disponíveis")
    except Exception as exc:
        print("ATENÇÃO: verificação da API fiscal indisponível:",exc)

    print("Atualize a aplicação (Ctrl+Shift+R), abra Produtos > Editor Visual > ECharts.")
    print("Use 'Montar painel como a referência' > 'Inserir painel completo'.")
    print("O RREO permite Ano/Bimestre e 7 medidas, não elementos de despesa ou filtros mensais.")
    print("Nenhum produto, dado fiscal, layout salvo ou branch foi alterado.")

if __name__=="__main__":
    try:main()
    except Exception as error:
        print("INSTALAÇÃO NÃO APLICADA:",error,file=sys.stderr)
        sys.exit(1)
