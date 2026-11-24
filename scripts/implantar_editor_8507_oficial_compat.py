#!/usr/bin/env python3
"""Promote tested 8507 editor into the official BI Factory product catalogue.

Run from current Codespaces with:
  git fetch origin feat/lab8507-ampliar-grafico-na-visualizacao-20261123 feat/oficializar-editor-8507-ficha-produto-20261123
  git show origin/fix/oficial8507-integracao-sem-sobrescrever-main-20261123:scripts/implantar_editor_8507_oficial_compat.py | python3 -

Does not checkout a branch, replace/delete products, change old GridStack layouts,
or overwrite locally-diverged application files. A failed test restores old code.
"""
from __future__ import annotations
import datetime
import difflib
import json
import os
import re
import shutil
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
BASE="origin/feat/lab8507-ampliar-grafico-na-visualizacao-20261123"
TARGET="origin/fix/oficial8507-integracao-sem-sobrescrever-main-20261123"
MODIFIED=(
 "web/bi_factory/src/main.jsx",
 "web/bi_factory/vite.config.js",
 "prototypes/editor-visual/server.py",
 "scripts/serve_bi_factory_api.py",
 "scripts/start_bi_factory_codespaces.sh",
 "scripts/autostart_bi_factory_codespaces.sh",
)
NEW=(
 "prototypes/editor-visual/official-8507/index.html",
 "prototypes/editor-visual/official-8507/app.js",
 "prototypes/editor-visual/official-8507/engine.js",
 "prototypes/editor-visual/official-8507/style.css",
 "prototypes/editor-visual/official-8507/legacy-migration.js",
 "scripts/test_editor_oficial_8507_integracao.js",
 "scripts/test_editor_oficial_8507_api.py",
)
LOG=Path("/tmp/bi-factory-seppe-logs")
API=ROOT/"scripts/serve_bi_factory_api.py"
LAB=ROOT/"scripts/serve_echarts_axes_8507.py"
MONITOR=ROOT/"scripts/autostart_bi_factory_codespaces.sh"
OLD_WEB=ROOT/"web/bi_factory"

def tracked(ref,name):
    p=subprocess.run(["git","show",ref+":"+name],cwd=ROOT,capture_output=True)
    return p.stdout if p.returncode==0 else None

def git_patch(name,from_bytes,to_bytes):
    old=from_bytes.decode("utf-8").splitlines(keepends=True)
    new=to_bytes.decode("utf-8").splitlines(keepends=True)
    diff="".join(difflib.unified_diff(
        old,new,fromfile="a/"+name,tofile="b/"+name,n=3
    ))
    if not diff:return ""
    return "diff --git a/"+name+" b/"+name+"\n"+diff


def semantic_local(name, current, target):
    """Apply only the small official-8507 integration points to a divergent file.

    All unrelated local content stays byte-for-byte unchanged, and the
    original file is preserved in .git/backups/ before any write.
    """
    src=current.decode("utf-8")
    wanted=target.decode("utf-8")
    if name=="web/bi_factory/src/main.jsx":
        before=src
        if "/visual-editor/official-8507/index.html?" not in src:
            src,count=re.subn(r'/visual-editor/index\.html\?',
                '/visual-editor/official-8507/index.html?',src)
            if count!=1:
                raise RuntimeError("main.jsx: endereço do editor anterior não foi identificado com segurança")
        begin=src.find("async function saveVisualFromEditor(")
        if begin<0:
            raise RuntimeError("main.jsx: função de gravação do produto não encontrada")
        end=src.find("function startNewProductEditor(",begin)
        if end<0:end=src.find("async function confirmVisual(",begin)
        if end<0:
            raise RuntimeError("main.jsx: fim da função de gravação não identificado")
        segment=src[begin:end]
        if '"/visual-8507"' not in segment and "'/visual-8507'" not in segment:
            segment,count=re.subn(r'(["\x27])/layout\1\s*,\s*\{\s*method\s*:\s*(["\x27])PUT\2',
                lambda m:m.group(1)+"/visual-8507"+m.group(1)+','
                  +'{method:'+m.group(2)+'PUT'+m.group(2),segment,count=1)
            if count!=1:
                raise RuntimeError("main.jsx: PUT de layout antigo não localizado; nenhuma substituição cega")
            src=src[:begin]+segment+src[end:]
        # Confirm official saves also with older user-created parent variants.
        old_reply='type:"bi-factory:save-result"'
        if 'type:"bi-factory:official-save-result"' not in src and old_reply in src:
            src=src.replace(old_reply,'type:"bi-factory:official-save-result"',1)
        if "bi-factory:official-save-request" not in src:
            guard="function visualUrl(mode)"
            if guard not in src:
                raise RuntimeError("main.jsx: ponto da integração do evento iframe não encontrado")
            listener=(
               '/* BI_FACTORY_OFFICIAL_8507_COMPAT */\n'
               'useEffect(()=>{const officialSave=e=>{\n'
               ' if(e.origin!==window.location.origin||'
               'e.source!==document.querySelector(".visualOverlay iframe")?.contentWindow)return;\n'
               ' if(e.data?.type==="bi-factory:official-save-request")'
               'saveVisualFromEditor(e.data.layout);\n'
               '};window.addEventListener("message",officialSave);'
               'return()=>window.removeEventListener("message",officialSave)'
               '},[visualMode,selectedProduct?.id,newVisualDraft]);\n'
            )
            src=src.replace(guard,listener+guard,1)
        if ('fetch("/api/products/"+id+"/visual-8507")' not in src and
            "BI_FACTORY_OFFICIAL_8507_LAYOUT_CHECK" not in src):
            guard="function visualUrl(mode)"
            # Optional upgrade of old hook avoids racing the new and legacy checks.
            base=tracked(BASE,name)
            if base is None:raise RuntimeError("Base main.jsx indisponível")
            original=base.decode("utf-8")
            begin_o=original.find('useEffect(()=>{if(!selectedProduct?.id)return;')
            end_o=original.find('useEffect(()=>{if(!visualMode)return;',begin_o)
            original_hook=original[begin_o:end_o] if begin_o>=0 and end_o>begin_o else ""
            begin_n=wanted.find('useEffect(()=>{\n if(!selectedProduct?.id)return;')
            end_n=wanted.find('useEffect(()=>{if(!visualMode)return;',begin_n)
            new_hook=wanted[begin_n:end_n] if begin_n>=0 and end_n>begin_n else ""
            if original_hook and new_hook and original_hook in src:
                src=src.replace(original_hook,new_hook,1)
            else:
                hook=(
                 '/* BI_FACTORY_OFFICIAL_8507_LAYOUT_CHECK */\n'
                 'useEffect(()=>{if(!selectedProduct?.id)return;let active=true;\n'
                 'const id=encodeURIComponent(selectedProduct.id);\n'
                 'Promise.all([\n'
                 'fetch("/api/products/"+id+"/visual-8507").then(r=>r.ok?r.json():null),\n'
                 'fetch("/api/products/"+id+"/layout").then(r=>r.ok?r.json():null)\n'
                 ']).then(([a,b])=>{if(active&&'
                 '(a?.objects?.length||b?.layout?.length||Object.keys(b?.objects||{}).length))'
                 'setVisualHasLayout(true)}).catch(()=>{});\n'
                 'return()=>{active=false}},[selectedProduct?.id,visualRevision]);\n'
                )
                src=src.replace(guard,hook+guard,1)
        if src==before:
            raise RuntimeError("main.jsx divergente, mas nenhum ponto de integração pôde ser aplicado")
        return src.encode("utf-8")
    if name=="web/bi_factory/vite.config.js":
        if 'port:8507' not in src:
            src,n=re.subn(r'port\s*:\s*(?:8504|8506)\b', 'port:8507',src,count=1)
            if n!=1:raise RuntimeError("Vite: porta não identificada")
        if '"/api"' not in src or '"/visual-editor"' not in src:
            raise RuntimeError("Vite: proxies de API e editor visual ausentes")
        return src.encode("utf-8")
    if name=="scripts/start_bi_factory_codespaces.sh":
        if "8506" in src:
            src=src.replace("8506","8507")
        if "/visual-editor/official-8507/index.html" not in src:
            src=src.replace("/visual-editor/index.html","/visual-editor/official-8507/index.html")
        if "/visual-editor/official-8507/index.html" not in src:
            raise RuntimeError("Starter: não foi possível inserir verificação do editor oficial")
        return src.encode("utf-8")
    if name=="scripts/autostart_bi_factory_codespaces.sh":
        src=src.replace("127.0.0.1:8506/","127.0.0.1:8507/")
        return src.encode("utf-8")
    if name=="scripts/serve_bi_factory_api.py":
        if '"/api/visual-8507/lab-draft"' not in src:
            old='route.startswith("/api/products/")'
            if old not in src:
                raise RuntimeError("API 8505: roteador do catálogo não localizado")
            src=src.replace(old,'(route.startswith("/api/products/") or '
                            'route == "/api/visual-8507/lab-draft")',1)
        return src.encode("utf-8")
    if name=="prototypes/editor-visual/server.py":
        anchor='LAYOUTS = ROOT / "storage" / "information_products" / "layouts"'
        if 'VISUAL_8507 = ROOT' not in src:
            if anchor not in src:raise RuntimeError("Server: pasta de layouts não identificada")
            want_line=[x for x in wanted.splitlines() if x.startswith("VISUAL_8507 =")]
            lab_line=[x for x in wanted.splitlines() if x.startswith("LEGACY_LAB_8507 =")]
            if not want_line or not lab_line:raise RuntimeError("Server: modelo oficial sem caminhos")
            src=src.replace(anchor,anchor+"\n"+want_line[0]+"\n"+lab_line[0],1)
        elif 'LEGACY_LAB_8507 =' not in src:
            lab_line=[x for x in wanted.splitlines() if x.startswith("LEGACY_LAB_8507 =")]
            if not lab_line:raise RuntimeError("Server: rota experimental não está no oficial")
            src=src.replace(anchor,anchor+"\n"+lab_line[0],1)
        src=re.sub(r'(?m)^MAX_BODY\s*=\s*2_000_000\s*$','MAX_BODY = 12_000_000',src,count=1)
        if 'path == "/api/visual-8507/lab-draft"' not in src:
            start=wanted.find('            if path == "/api/visual-8507/lab-draft"')
            finish=wanted.find('            parts = path.strip("/").split("/")',start)
            if start<0 or finish<0:raise RuntimeError("Server: trecho da rota de importação não encontrado")
            marker='            parts = path.strip("/").split("/")'
            if marker not in src:raise RuntimeError("Server: ponto de importação não encontrado")
            src=src.replace(marker,wanted[start:finish]+marker,1)
        if 'parts[3] == "visual-8507"' not in src:
            start=wanted.find('                if len(parts) == 4 and parts[3] == "visual-8507":')
            finish=wanted.find('                if len(parts) == 4 and parts[3] == "layout":',start)
            if start<0 or finish<0:
                raise RuntimeError("Server: implementação do layout oficial não encontrada")
            marker='                if len(parts) == 4 and parts[3] == "layout":'
            if marker not in src:raise RuntimeError("Server: bloco de layouts antigos não encontrado")
            src=src.replace(marker,wanted[start:finish]+marker,1)
        return src.encode("utf-8")
    raise RuntimeError("A conciliação deste arquivo não foi autorizada: "+name)

def semantic_verify(name, candidate):
    src=candidate.decode("utf-8")
    rules={
      "web/bi_factory/src/main.jsx":(
        "/visual-editor/official-8507/index.html?",
        "bi-factory:official-save-request",
        "/visual-8507",
        "function saveVisualFromEditor(",
      ),
      "web/bi_factory/vite.config.js":("port:8507","/visual-editor","/api"),
      "scripts/start_bi_factory_codespaces.sh":(
        "--port 8507","/visual-editor/official-8507/index.html"
      ),
      "scripts/autostart_bi_factory_codespaces.sh":("127.0.0.1:8507/",),
      "scripts/serve_bi_factory_api.py":("/api/visual-8507/lab-draft",),
      "prototypes/editor-visual/server.py":(
        'parts[3] == "visual-8507"','path == "/api/visual-8507/lab-draft"',
        'parts[3] == "layout"',"VISUAL_8507"
      )
    }
    for expected in rules.get(name,()):
        if expected not in src:
            raise RuntimeError("Integração incompleta em "+name+
                               ": verificação ausente "+expected)

def merge_compatible(name,current,base,target):
    # Retomar uma implantação parcial deve ser seguro e não repetir alterações.
    try:
        semantic_verify(name,current)
        return current
    except RuntimeError:
        pass
    if name=="web/bi_factory/src/main.jsx":
        # A ficha do usuário é a fonte da verdade. Alterar apenas rotas e eventos.
        integrated=semantic_local(name,current,target)
        semantic_verify(name,integrated)
        return integrated
    with tempfile.TemporaryDirectory(prefix="bi8507-threeway-") as tmp:
        paths=[Path(tmp)/x for x in ("local","base","oficial")]
        for path,blob in zip(paths,(current,base,target)):
            path.write_bytes(blob)
        merged=subprocess.run(["git","merge-file","-p","--diff3",
            *map(str,paths)],capture_output=True)
    if merged.returncode==0:
        try:
            semantic_verify(name,merged.stdout)
            return merged.stdout
        except RuntimeError:
            pass
    # A mesclagem só é aceita com todos os marcadores semânticos presentes.
    integrated=semantic_local(name,current,target)
    semantic_verify(name,integrated)
    return integrated

def syntax_check(name,data):
    if not name.endswith((".py",".js")):return
    with tempfile.TemporaryDirectory(prefix="bi-official-8507-check-") as folder:
        file=Path(folder)/Path(name).name
        file.write_bytes(data)
        cmd=[sys.executable,"-m","py_compile",str(file)] if name.endswith(".py") else [
            "node","--check",str(file)
        ]
        p=subprocess.run(cmd,capture_output=True,text=True)
        if p.returncode:
            raise RuntimeError("Sintaxe inválida em "+name+": "+p.stderr[-1200:])

def safe_port(port):
    try:
        with socket.create_connection(("127.0.0.1",port),timeout=0.5):return True
    except OSError:return False

def process_list(fragment,cwd):
    matches=[]
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():continue
        try:
            argv=[x.decode("utf-8","replace") for x in
                  (entry/"cmdline").read_bytes().split(b"\x00") if x]
            if not any(fragment in x for x in argv):continue
            if (entry/"cwd").resolve()!=cwd:continue
            matches.append((int(entry.name),argv))
        except (OSError,PermissionError,ValueError):
            continue
    return matches

def stop_known(pids,label,port=None):
    if not pids:return False
    if len(pids)!=1:
        raise RuntimeError("Vários processos "+label+" detectados; nenhuma finalização automática")
    pid,args=pids[0]
    if port and "--port" in args:
        index=args.index("--port")
        if index+1>=len(args) or args[index+1]!=str(port):
            raise RuntimeError("Parâmetros divergentes do servidor "+label)
    print("Desativando",label,"PID",pid,flush=True)
    os.kill(pid,signal.SIGTERM)
    for _ in range(50):
        if port:
            if not safe_port(port):return True
        else:
            if not (Path("/proc")/str(pid)).exists():return True
        time.sleep(0.2)
    if port and safe_port(port):
        raise RuntimeError(label+" não liberou a porta "+str(port))
    return True

def http(path,port=8507,timeout=10):
    with urllib.request.urlopen(
        urllib.request.Request("http://127.0.0.1:"+str(port)+path,
          headers={"Cache-Control":"no-cache","Accept":"*/*"}),
        timeout=timeout
    ) as reply:
        return reply.read().decode("utf-8","replace")

def wait_http(path,port=8507,loops=60):
    last=None
    for _ in range(loops):
        try:return http(path,port,timeout=2)
        except (OSError,urllib.error.URLError) as exc:
            last=exc
            time.sleep(.25)
    raise RuntimeError("Sem resposta em "+str(port)+path+": "+str(last))

def deploy():
    if not (ROOT/".git").is_dir():
        raise RuntimeError("Abra o Codespace original /workspaces/bi-factory-seppe")
    pending={}
    for name in (*MODIFIED,*NEW):
        target=tracked(TARGET,name)
        if target is None:raise RuntimeError("Arquivo oficial ausente no GitHub: "+name)
        local=ROOT/name
        if local.is_symlink() or (local.exists() and not local.is_file()):
            raise RuntimeError("Arquivo local inseguro: "+name)
        current=local.read_bytes() if local.exists() else None
        syntax_check(name,target)
        if current==target:
            print("OK JÁ INSTALADO:",name)
            continue
        if name in NEW:
            if current is not None:
                raise RuntimeError("Novo arquivo oficial já existe com diferenças: "+name+
                                   ". Nenhum arquivo foi substituído.")
            pending[name]=(current,target,None)
            continue
        base=tracked(BASE,name)
        if base is None or current is None:
            raise RuntimeError("Arquivo base não encontrado: "+name)
        if current==base:
            pending[name]=(current,target,None)
        else:
            patch=git_patch(name,base,target)
            if not patch:
                raise RuntimeError("Código local divergente: "+name)
            test=subprocess.run(["git","apply","--check","--whitespace=nowarn"],
                  cwd=ROOT,input=patch,capture_output=True,text=True)
            if test.returncode:
                raise RuntimeError("O arquivo possui alterações locais incompatíveis: "+name+
                  ". Nenhum dado será sobrescrito. "+test.stderr[-1000:])
            pending[name]=(current,target,patch)
    if not pending:
        print("Arquivos oficiais já instalados.")
    backup=ROOT/".git"/"backups"/(
        "oficializacao-8507-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    written=[]
    try:
        for name,(previous,wanted,patch) in pending.items():
            dest=ROOT/name
            if previous is not None:
                saved=backup/name
                saved.parent.mkdir(parents=True,exist_ok=True)
                saved.write_bytes(previous)
            dest.parent.mkdir(parents=True,exist_ok=True)
            if patch:
                p=subprocess.run(["git","apply","--whitespace=nowarn"],
                    cwd=ROOT,input=patch,capture_output=True,text=True)
                if p.returncode:raise RuntimeError("Patch falhou: "+name+": "+p.stderr[-800:])
            else:
                pending_file=dest.with_name(dest.name+".official8507-pending")
                if pending_file.exists():raise RuntimeError("Arquivo temporário ocupado: "+str(pending_file))
                try:
                    pending_file.write_bytes(wanted)
                    if dest.exists():os.chmod(pending_file,dest.stat().st_mode&0o777)
                    os.replace(pending_file,dest)
                finally:pending_file.unlink(missing_ok=True)
            written.append(name)
            print("INSTALADO:",name,flush=True)
        for cmd in (
            ["node","scripts/test_editor_oficial_8507_integracao.js"],
            [sys.executable,"scripts/test_editor_oficial_8507_api.py"],
        ):
            print("TESTANDO:",' '.join(cmd),flush=True)
            subprocess.run(cmd,cwd=ROOT,check=True)
        if not (OLD_WEB/"node_modules/.bin/vite").is_file():
            print("Instalando dependências travadas em package-lock.json...",flush=True)
            subprocess.run(["npm","ci"],cwd=OLD_WEB,check=True)
        print("TESTANDO: compilação do catálogo React",flush=True)
        subprocess.run(["npm","run","build"],cwd=OLD_WEB,check=True)
    except Exception:
        print("Falha de compilação/testes: restaurando arquivos anteriores.",flush=True)
        for name in reversed(written):
            prev=pending[name][0]
            path=ROOT/name
            if prev is None:path.unlink(missing_ok=True)
            else:path.write_bytes(prev)
        raise
    if backup.exists():print("BACKUP do código anterior:",backup,flush=True)
    print("Código instalado e testes concluídos. Ativando a porta 8507.",flush=True)
    # O monitor anterior ainda verificava a porta 8506; parar apenas a
    # instância identificada e iniciar o monitor oficial após a troca.
    old_monitors=process_list("scripts/autostart_bi_factory_codespaces.sh",ROOT)
    old_monitors=[item for item in old_monitors if "--monitor" in item[1]]
    if old_monitors:stop_known(old_monitors,"monitor anterior de serviços")
    # Never terminate unrelated port owners.
    if safe_port(8507):
        lab=process_list(str(LAB),ROOT)
        if not lab:
            lab=process_list("scripts/serve_echarts_axes_8507.py",ROOT)
        if lab:stop_known(lab,"laboratório isolado 8507",8507)
        else:
            try:
                html=http("/",8507)
                if "BI Factory" not in html and "bi-factory" not in html.lower():
                    raise RuntimeError("Porta 8507 ocupada por processo desconhecido")
            except (OSError,urllib.error.URLError) as exc:
                raise RuntimeError("Porta 8507 ocupada e não identificada") from exc
    if safe_port(8505):
        api=process_list(str(API),ROOT)
        if not api:api=process_list("scripts/serve_bi_factory_api.py",ROOT)
        if not api:
            raise RuntimeError("8505 ocupada por processo desconhecido; não reiniciá-lo.")
        stop_known(api,"API 8505",8505)
    subprocess.run(["bash","scripts/start_bi_factory_codespaces.sh"],cwd=ROOT,check=True)
    # Validate the effective API and the new product editor, without changing real products.
    homepage=wait_http("/")
    if "bi-factory" not in homepage.lower() and "src/main.jsx" not in homepage:
        raise RuntimeError("A porta 8507 não parece servir a aplicação oficial React")
    page=wait_http("/visual-editor/official-8507/index.html")
    js=wait_http("/visual-editor/official-8507/app.js")
    legacy=wait_http("/visual-editor/official-8507/legacy-migration.js")
    if "bi-factory-editor-oficial-8507-r1" not in page:
        raise RuntimeError("HTML servido não pertence ao Editor Visual oficial 8507")
    if "bi-factory:official-save-request" not in js or "visual-8507" not in js:
        raise RuntimeError("JS servido ainda é o laboratório antigo, sem salvar por produto")
    if "migrateLegacy" not in legacy:
        raise RuntimeError("Conversor de produtos antigos não está disponível")
    # A opção de trazer rascunho da antiga 8507 é opcional; um 404 é normal.
    try:
        experimental=json.loads(http("/api/visual-8507/lab-draft"))
        if not isinstance(experimental.get("objects"),list):
            raise RuntimeError("Rascunho experimental tem formato inesperado")
        print("OK importação opcional: rascunho disponível, sem alterar sua origem.",flush=True)
    except urllib.error.HTTPError as error:
        if error.code!=404:raise
        print("Sem rascunho experimental anterior; botão de importação informará isso.",flush=True)
    products=json.loads(wait_http("/api/products"))
    if not isinstance(products,list):
        raise RuntimeError("Catálogo oficial de produtos indisponível")
    for product in products:
        identifier=str(product.get("id",""))
        if re.fullmatch(r"[a-fA-F0-9]{8}-[a-fA-F0-9-]{27,}",identifier):
            record=json.loads(wait_http("/api/products/"+identifier+"/visual-8507"))
            if record is not None and (not isinstance(record,dict) or record.get("version")!=1):
                raise RuntimeError("Contrato de layout oficial inválido para produto "+identifier)
            print("OK: layout individual de produto existente consultado sem escrita",flush=True)
            break
    print("OFICIAL 8507: catálogo, ficha, novo editor e API por produto verificados.",flush=True)
    # Só depois do sucesso é seguro aposentar a antiga interface na 8506.
    old_vite=[
        item for item in process_list("vite",OLD_WEB)
        if "--port" in item[1]
        and item[1].index("--port")+1<len(item[1])
        and item[1][item[1].index("--port")+1]=="8506"
    ]
    if old_vite:
        stop_known(old_vite,"Vite legado 8506",8506)
        print("8506 anterior desativada; código e dados preservados para recuperação.",flush=True)
    elif safe_port(8506):
        print("8506 ainda ocupada por processo não identificado; não foi interrompida.",flush=True)
    # Iniciar o monitor persistente atualizado, com verificação 8507 em lugar de 8506.
    subprocess.run(["bash","scripts/autostart_bi_factory_codespaces.sh"],
                   cwd=ROOT,check=True);
    print("OK monitor: vigia API 8505 e aplicativo oficial 8507.",flush=True)
    # O serviço antigo foi aposentado somente quando seu processo era identificável.
    # O código está protegido por backup, não pela execução simultânea na 8506.
    print("Porta oficial: 8507. O editor antigo da 8506 não é mais a interface principal.",flush=True)
    print("Nenhum registry/folders/layout antigo foi modificado ou apagado.",flush=True)
    print("No Codespaces, abra PORTAS > 8507 (Private) > Abrir no navegador.",flush=True)

if __name__=="__main__":
    try:deploy()
    except Exception as exc:
        print("ERRO NA OFICIALIZAÇÃO 8507:",exc,file=sys.stderr,flush=True)
        sys.exit(1)
