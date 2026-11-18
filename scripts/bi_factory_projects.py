"""Project-scoped onboarding and knowledge intake for unified React BI Factory.

Project registry and knowledge sources live under storage/working/projects,
separate from the frozen information_products catalog. The original PMCG project
is represented as a compatibility record and never duplicated or moved.
Search requests are queued, NOT presented as AI execution until an actual
configured research provider exists.
"""
from __future__ import annotations
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "storage" / "working" / "projects"
REGISTRY = DIR / "projects.json"
LOCK = threading.RLock()
LEGACY_ID = "pmcg-financas-publicas"
LEGACY = {
    "id": LEGACY_ID,
    "name": "PMCG — Finanças Públicas",
    "theme": "Execução orçamentária e despesas públicas",
    "description": "Projeto histórico preservado, com produtos existentes.",
    "scope": "Município de Campo Grande, Mato Grosso do Sul",
    "status": "Em andamento",
    "legacy": True,
    "created_at": None,
}
VALID_SOURCE = {".pdf", ".docx", ".txt"}
MAX_SOURCE = 12 * 1024 * 1024
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,90}$")
_ALLOWED_FIELDS = {"name", "theme", "description", "scope", "goal", "audience", "organization"}

def _now():
    return datetime.now(timezone.utc).isoformat()

def _read(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".project-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, indent=2, ensure_ascii=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def _validate_id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Identificador de projeto inválido")
    return value

def _clean(value, key, required=False):
    if not isinstance(value, str) or len(value) > 3000:
        raise ValueError(f"Campo inválido: {key}")
    result = value.strip()
    if required and not result:
        raise ValueError(f"Informe {key}")
    return result

def projects():
    with LOCK:
        records = _read(REGISTRY, [])
        if not isinstance(records, list):
            raise ValueError("Registro de projetos inválido")
        legacy = next((p for p in records if p.get("id") == LEGACY_ID), None)
        return [legacy or dict(LEGACY)] + [p for p in records if p.get("id") != LEGACY_ID]

def get(project_id):
    project_id = _validate_id(project_id)
    result = next((p for p in projects() if p["id"] == project_id), None)
    if result is None:
        raise ValueError("Projeto não encontrado")
    return result

def create(payload):
    if not isinstance(payload, dict):
        raise ValueError("Dados do projeto inválidos")
    name = _clean(payload.get("name", ""), "nome do projeto", True)
    theme = _clean(payload.get("theme", ""), "tema do projeto", True)
    now = _now()
    item = {
        "id": "prj-" + uuid4().hex,
        "name": name,
        "theme": theme,
        "description": _clean(payload.get("description", ""), "descrição"),
        "scope": _clean(payload.get("scope", ""), "âmbito"),
        "goal": _clean(payload.get("goal", ""), "objetivo"),
        "organization": _clean(payload.get("organization", ""), "organização"),
        "status": "Novo",
        "legacy": False,
        "created_at": now,
        "updated_at": now,
    }
    with LOCK:
        records = _read(REGISTRY, [])
        if any(p.get("name", "").casefold() == name.casefold() for p in projects()):
            raise ValueError("Já existe projeto com esse nome")
        records.append(item)
        _write(REGISTRY, records)
    return item

def update(project_id, payload):
    if not isinstance(payload, dict):
        raise ValueError("Dados inválidos")
    project_id = _validate_id(project_id)
    with LOCK:
        records = _read(REGISTRY, [])
        if project_id == LEGACY_ID and not any(p.get("id") == LEGACY_ID for p in records):
            records.append(dict(LEGACY))
        item = next((p for p in records if p.get("id") == project_id), None)
        if not item:
            raise ValueError("Projeto não encontrado")
        for key in _ALLOWED_FIELDS:
            if key in payload:
                item[key] = _clean(payload[key],key,key in {"name","theme"})
        item["updated_at"] = _now()
        _write(REGISTRY, records)
    return item

def _sources_path(project_id):
    get(project_id)
    return DIR / project_id / "knowledge.json"

def summary(project_id):
    project = get(project_id)
    path = _sources_path(project_id)
    rows = _read(path, [])
    if not isinstance(rows, list):
        raise ValueError("Catálogo de conhecimento inválido")
    return {"project": project, "items": rows}

def research(payload):
    if not isinstance(payload, dict):
        raise ValueError("Requisição inválida")
    project_id = _validate_id(payload.get("project_id"))
    project = get(project_id)
    topic = _clean(payload.get("topic") or project.get("theme") or "", "tema", True)
    categories = payload.get("categories")
    valid = {"legislacao", "normas", "manuais", "sites_oficiais", "metodos"}
    if not isinstance(categories, list) or not categories or set(categories) - valid:
        raise ValueError("Escolha os tipos de pesquisa")
    scope = _clean(payload.get("scope") or project.get("scope") or "", "abrangência")
    item = {
        "id": str(uuid4()), "type": "research_request",
        "topic": topic, "categories": categories, "scope": scope,
        "status": "Aguardando integração com serviço de pesquisa IA",
        "created_at": _now(),
        "note": "Solicitação registrada; nenhuma pesquisa na internet foi executada.",
    }
    with LOCK:
        path = _sources_path(project_id)
        rows = _read(path, [])
        rows.append(item)
        _write(path, rows)
    return item

def upload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Dados inválidos")
    project_id = _validate_id(payload.get("project_id"))
    get(project_id)
    name = payload.get("filename")
    if (not isinstance(name, str) or not 1 <= len(name) <= 180 or
        "/" in name or "\\" in name or name in {".", ".."} or
        Path(name).suffix.lower() not in VALID_SOURCE):
        raise ValueError("Documento inválido; utilize PDF, DOCX ou TXT")
    encoded = payload.get("base64")
    if not isinstance(encoded, str) or len(encoded) > 4 * MAX_SOURCE // 3 + 16:
        raise ValueError("Documento maior que 12 MB")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as err:
        raise ValueError("Arquivo inválido") from err
    if not data or len(data) > MAX_SOURCE:
        raise ValueError("Documento vazio ou excede 12 MB")
    ext = Path(name).suffix.lower()
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("Conteúdo não corresponde a PDF")
    if ext == ".docx" and not data.startswith(b"PK"):
        raise ValueError("Conteúdo não corresponde a DOCX")
    digest = hashlib.sha256(data).hexdigest()
    item = {
        "id": str(uuid4()), "type": "document", "filename": name,
        "title": _clean(payload.get("title") or name, "título", True),
        "description": _clean(payload.get("description") or "", "descrição"),
        "source": _clean(payload.get("source") or "", "órgão ou fonte"),
        "reference": _clean(payload.get("reference") or "", "número ou referência"),
        "sha256": digest, "size_bytes": len(data),
        "status": "Documento recebido — interpretação pendente",
        "created_at": _now(),
    }
    with LOCK:
        path = _sources_path(project_id)
        rows = _read(path, [])
        if any(x.get("sha256") == digest for x in rows):
            raise ValueError("Esse documento já foi enviado para este projeto")
        target_dir = DIR / project_id / "originals"
        target_dir.mkdir(parents=True, exist_ok=True)
        destination = target_dir / (digest + ext)
        if not destination.exists():
            fd, tmp = tempfile.mkstemp(prefix=".source-", dir=target_dir)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                os.chmod(tmp, 0o600)
                os.replace(tmp, destination)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        rows.append(item)
        _write(path, rows)
    return item
