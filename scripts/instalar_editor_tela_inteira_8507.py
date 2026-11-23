#!/usr/bin/env python3
"""Update object management on experimental port 8507 without touching stable 8506.

Recognizes every published 8507 version, updates versioned JS/HTML and
isolated server only, checks syntax/tests, safely restarts the 8507 server,
then verifies the actually served build over localhost:8507.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path("/workspaces/bi-factory-seppe")
SERVER=ROOT/"scripts/serve_echarts_axes_8507.py"
BUILD="lab8507-editor-wide-curtains-20261123-r8"
PREVIOUS=(
    "origin/feat/lab-echarts-eixos-8507-20261119",
    "origin/fix/lab8507-fonte-historica-e-reinicio-20261123",
    "origin/fix/lab8507-rascunho-rota-dedicada-20261123",
    "origin/fix/lab8507-recarregar-assets-20261123",
    "origin/fix/lab8507-python-none-20261123",
    "origin/feat/lab8507-gerenciamento-objetos-20261123",
    "origin/fix/lab8507-canvas-livre-multifiltros-20261123",
    "origin/fix/lab8507-teste-contrato-multifiltro-20261123",
    "origin/fix/lab8507-alca-persistente-20261123",
    "origin/fix/lab8507-preview-fullscreen-filtro-fechar-20261123",
    "origin/fix/lab8507-canvas-livre-multifiltros-20261123",
)
TARGET="origin/feat/lab8507-editor-pagina-inteira-cortinas-20261123"
FILES=(
    "experiments/echarts-axes-8507/index.html",
    "experiments/echarts-axes-8507/app.js",
    "experiments/echarts-axes-8507/engine.js",
    "experiments/echarts-axes-8507/style.css",
    "scripts/serve_echarts_axes_8507.py",
    "scripts/test_lab_8507_draft_route.py",
    "scripts/test_lab_8507_fiscal_fallback.py",
    "scripts/test_lab_8507_object_management.py",
    "scripts/test_lab_8507_object_editor_ui.js",
    "scripts/test_lab_8507_free_canvas_ui.js",
    "scripts/test_lab_8507_multiselect_filters.js",
    "scripts/test_lab_ui_contract_8507.js",
    "scripts/test_lab_8507_persistent_move_handles.js",
    "scripts/test_lab_8507_fullscreen_filter_preview.js",
    "scripts/test_lab_8507_full_width_editor.js",
)
URL="http://127.0.0.1:8507"
LOG=Path("/tmp/bi-factory-seppe-logs/lab-echarts-8507.log")

def git_file(ref,path):
    p=subprocess.run(["git","show",ref+":"+path],cwd=ROOT,capture_output=True)
    return p.stdout if p.returncode==0 else None

def digest(data):
    return hashlib.sha256(data).hexdigest()[:16] if data is not None else "ausente"

def validate_source(name,blob):
    with tempfile.TemporaryDirectory(prefix="lab8507-check-") as tmp:
        dest=Path(tmp)/Path(name).name
        dest.write_bytes(blob)
        if name.endswith(".js"):
            argv=["node","--check",str(dest)]
        elif name.endswith(".py"):
            argv=[sys.executable,"-m","py_compile",str(dest)]
        else:return
        p=subprocess.run(argv,capture_output=True,text=True)
        if p.returncode:
            raise RuntimeError("Sintaxe inválida em "+name+": "+p.stderr[-900:])

def http_bytes(path,timeout=6):
    request=urllib.request.Request(URL+path,headers={
        "Cache-Control":"no-cache","Pragma":"no-cache",
        "User-Agent":"bi-factory-lab8507-version-probe"
    })
    with urllib.request.urlopen(request,timeout=timeout) as response:
        return response.read(),response.headers

def http_json(path,timeout=6):
    result,_=http_bytes(path,timeout)
    return json.loads(result)

def socket_open():
    try:
        with socket.create_connection(("127.0.0.1",8507),timeout=1):
            return True
    except OSError:return False

def identify_pids():
    known=[]
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():continue
        try:
            args=(proc/"cmdline").read_bytes().split(b"\x00")
            argv=[arg.decode("utf-8",errors="replace") for arg in args if arg]
            marker="scripts/serve_echarts_axes_8507.py"
            if not any(arg==str(SERVER) or arg==marker or arg.endswith("/"+marker) for arg in argv):
                continue
            if "--port" in argv:
                index=argv.index("--port")
                if index+1>=len(argv) or argv[index+1]!="8507":continue
            if (proc/"cwd").resolve()!=ROOT:continue
            known.append(int(proc.name))
        except (PermissionError,OSError,IndexError,ValueError):
            continue
    return known

def start_or_restart():
    pids=identify_pids()
    if len(pids)>1:
        raise RuntimeError("Vários processos 8507 identificados. Nenhum foi encerrado.")
    if pids:
        print("Reiniciando EXCLUSIVAMENTE a 8507 (PID",pids[0],")",flush=True)
        os.kill(pids[0],signal.SIGTERM)
        for _ in range(60):
            if not socket_open():break
            time.sleep(0.2)
        else:
            raise RuntimeError("Processo anterior não liberou 8507; preservado sem SIGKILL.")
    elif socket_open():
        raise RuntimeError("8507 ocupada por processo desconhecido; atualização de arquivos concluída, servidor não reiniciado.")
    LOG.parent.mkdir(parents=True,exist_ok=True)
    with LOG.open("ab") as output:
        subprocess.Popen([sys.executable,"-u",str(SERVER),"--host","127.0.0.1","--port","8507"],
            cwd=ROOT,stdin=subprocess.DEVNULL,
            stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    for _ in range(75):
        try:
            health=http_json("/api/health",timeout=2)
            if health.get("lab")=="echarts-axes" and health.get("build")==BUILD:
                print("OK: servidor 8507 reiniciado com build",BUILD)
                return
        except (OSError,ValueError):
            pass
        time.sleep(.2)
    raise RuntimeError("8507 não anunciou build novo. Veja "+str(LOG))

def main():
    if not (ROOT/".git").is_dir():
        raise RuntimeError("Caminho do repositório BI Factory Codespaces não encontrado.")
    updates={}
    for name in FILES:
        file=ROOT/name
        if file.is_symlink() or (file.exists() and not file.is_file()):
            raise RuntimeError("Caminho inseguro recusado: "+name)
        actual=file.read_bytes() if file.exists() else None
        desired=git_file(TARGET,name)
        if desired is None:
            raise RuntimeError("Não foi possível recuperar "+name+" da branch "+TARGET)
        validate_source(name,desired)
        if actual==desired:
            print("JÁ ATUALIZADO:",name)
            continue
        allowed={git_file(ref,name) for ref in PREVIOUS}
        if actual not in allowed:
            raise RuntimeError(
                "Arquivo local divergente, não sobrescrito: "+name+
                " | local "+digest(actual)+" | novo "+digest(desired)
            )
        updates[name]=(actual,desired)
        print("ATUALIZANDO:",name,"de",digest(actual),"para",digest(desired))
    backup=ROOT/".git"/"backups"/(
        "lab8507-editor-full-width-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    if updates:
        for name,(actual,_) in updates.items():
            if actual is not None:
                dest=backup/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(actual)
    done=[]
    try:
        for name,(old,new) in updates.items():
            path=ROOT/name
            path.parent.mkdir(parents=True,exist_ok=True)
            pending=path.with_name(path.name+".8507-new-version")
            if pending.exists():
                raise RuntimeError("Arquivo temporário preexistente: "+str(pending))
            try:
                pending.write_bytes(new)
                if path.exists():os.chmod(pending,path.stat().st_mode&0o777)
                os.replace(pending,path)
                done.append(name)
            finally:pending.unlink(missing_ok=True)
        for command in [
            [sys.executable,"scripts/test_lab_8507_draft_route.py"],
            [sys.executable,"scripts/test_lab_8507_fiscal_fallback.py"],
            [sys.executable,"scripts/test_lab_8507_object_management.py"],
            ["node","scripts/test_lab_8507_object_editor_ui.js"],
            ["node","scripts/test_lab_8507_free_canvas_ui.js"],
            ["node","scripts/test_lab_8507_multiselect_filters.js"],
            ["node","scripts/test_echarts_axes_8507.js"],
            ["node","scripts/test_lab_ui_contract_8507.js"],
            ["node","scripts/test_lab_8507_persistent_move_handles.js"],
            ["node","scripts/test_lab_8507_fullscreen_filter_preview.js"],
            ["node","scripts/test_lab_8507_full_width_editor.js"],
        ]:
            print("TESTE:",' '.join(command),flush=True)
            subprocess.run(command,cwd=ROOT,check=True)
    except Exception:
        for name in done:
            previous=updates[name][0]
            if previous is None:(ROOT/name).unlink(missing_ok=True)
            else:(ROOT/name).write_bytes(previous)
        raise
    if updates:print("Backup dos arquivos experimentais anteriores:",backup)
    start_or_restart()
    health=http_json("/api/health")
    if health.get("build")!=BUILD:
        raise RuntimeError("8507 respondeu com uma versão inesperada: "+repr(health))
    homepage,html_headers=http_bytes("/index.html?v="+BUILD)
    script,script_headers=http_bytes("/app.js?v="+BUILD)
    if BUILD.encode() not in homepage or BUILD.encode() not in script:
        raise RuntimeError("A 8507 ainda está servindo HTML ou JS antigo.")
    if b'requestJSON("/lab/draft")' not in script:
        raise RuntimeError("JS servido não aponta para a rota nova /lab/draft.")
    if b'function startObjectResize(' not in script or b'function deleteObject(' not in script:
        raise RuntimeError("JS servido ainda não contém gerenciamento de objetos da 8507.")
    if b'if(!previewOnly){\n      const moveHandle=node(' not in script:
        raise RuntimeError("Alças de movimentação de todos os objetos não estão ativas no JS servido.")
    if b'function multiSelectControl(' not in script or b'function ensureFreeLayout(' not in script:
        raise RuntimeError("JS servido não contém seleção múltipla ou posicionamento livre.")
    if b'function enterPanelPreview()' not in script or b'function exitPanelPreview()' not in script:
        raise RuntimeError("JS servido não contém a visualização em tela inteira.")
    if b'function syncVisualWorkspaceMode()' not in script or b'function setEditorCurtain(which,open)' not in script:
        raise RuntimeError("JS servido não contém Editor Visual de largura total e cortinas.")
    if b'classList.toggle("lab-edit-workspace",currentScreen==="visual"&&!previewOnly)' not in script:
        raise RuntimeError("JS servido não ativa o modo de edição em tela inteira.")
    if b'const done=node("button","Aplicar e fechar","multi-select-done");' not in script:
        raise RuntimeError("JS servido não oferece ação de aplicar e fechar filtros.")
    if b'active.length+" selecionados"' not in script:
        raise RuntimeError("JS servido não mostra o resumo de filtros selecionados.")
    if b'id="exit-panel-preview"' not in homepage:
        raise RuntimeError("HTML servido sem botão de sair da tela inteira.")
    if b'id="toggle-tools-drawer"' not in homepage or b'id="toggle-props-drawer"' not in homepage:
        raise RuntimeError("HTML servido sem controles das cortinas de Objetos e Propriedades.")
    if b'id="editor-open-echarts"' not in homepage or b'id="editor-save"' not in homepage:
        raise RuntimeError("HTML servido sem botões de ECharts e Salvar durante a edição.")
    if b'const header=node("div",undefined,"object-header")' in script:
        raise RuntimeError("Ainda há cabeçalho interno dos objetos no JS servido.")
    if b'surface.onclick=' not in script or b'picker.click()' not in script:
        raise RuntimeError("Clique direto na imagem não está disponível na versão servida.")
    if b'id="add-kpi"' in homepage:
        raise RuntimeError("HTML antigo ainda mostra KPI na paleta do Editor Visual.")
    if b'id="add-title"' not in homepage or b'id="add-rectangle"' not in homepage:
        raise RuntimeError("HTML novo não apresenta os objetos esperados.")
    style,_=http_bytes("/style.css?v="+BUILD)
    if b".resize-handle" not in style or b".multi-select-options" not in style:
        raise RuntimeError("CSS do redimensionamento e dos filtros múltiplos não foi servido.")
    if b".lab-panel-preview #visual-page.workspace" not in style:
        raise RuntimeError("CSS da visualização em tela inteira não foi servido.")
    if b"body.lab-edit-workspace #visual-page.lab-wide-editor" not in style:
        raise RuntimeError("CSS de edição na largura inteira da página não está disponível.")
    if b"body.lab-edit-workspace #visual-page > #visual-tools-drawer.drawer-open" not in style:
        raise RuntimeError("A cortina de Objetos não foi publicada.")
    if b"body.lab-edit-workspace #visual-page > #visual-props-drawer.drawer-open" not in style:
        raise RuntimeError("A cortina de Propriedades não foi publicada.")
    engine,_=http_bytes("/engine.js?v="+BUILD)
    if b"function filterValues(value)" not in engine:
        raise RuntimeError("Motor ECharts servido ainda não oferece filtros múltiplos.")
    draft=http_json("/lab/draft")
    if draft.get("version")!=1 or not isinstance(draft.get("objects"),list):
        raise RuntimeError("Resposta inválida do armazenamento /lab/draft.")
    if not draft["objects"] and draft.get("selected") is not None:
        raise RuntimeError("Rascunho vazio deveria retornar selected: null.")
    fiscal=http_json("/api/fiscal",timeout=15)
    if not isinstance(fiscal,list) or not fiscal:
        raise RuntimeError("A API fiscal não retornou os períodos.")
    unique={(str(row.get("ano",row.get("exercicio"))),str(row.get("bimestre"))) for row in fiscal}
    print()
    print("OK /index.html: build",BUILD)
    print("OK /app.js: rota /lab/draft e build",BUILD)
    print("OK /lab/draft:",len(draft["objects"]),"objetos preservados")
    print("OK /style.css: canvas livre, alças externas e filtros múltiplos")
    print("OK /engine.js: filtros de Ano, Bimestre e Medida múltiplos")
    print("OK /app.js: excluir, duplicar, editar fonte, cores e sobreposição")
    print("OK /api/fiscal:",len(unique),"bimestres disponíveis")
    print("OK /editor: largura total, cortina Objetos, cortina Propriedades, barra de edição e ECharts")
    print("8507 CONFIRMADA: editor na página inteira e prévia na mesma largura; 8506 preservada.")
    print("Reabra a porta 8507 e pressione Ctrl+Shift+R. Use Objetos e Propriedades para abrir/fechar as cortinas.")
    print("A 8506, a API 8505, os CSV fiscais, a branch e os produtos não foram modificados.")

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("FALHA NA ATUALIZAÇÃO DA 8507:",exc,file=sys.stderr)
        sys.exit(1)
