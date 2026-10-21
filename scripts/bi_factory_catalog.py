"""Safe JSON-backed catalog operations for React migration.
Existing registry, folders and dashboard files are preserved. Writes are atomic.
"""
import json
import os
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ROOT / "storage/information_products/folders.json"
REGISTRY = ROOT / "storage/information_products/registry.json"
COMPONENTS = ROOT / "storage/information_products/shared_components.json"
PRODUCT_FILES = ROOT / "storage/dashboard_projects/products"
TYPES = {"Painel", "Relatório", "PDF", "Site", "Portal", "Outro"}

def read(path):
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Formato de catálogo incompatível")
    return data

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".catalog-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def required(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Campo obrigatório: {key}")
    return value.strip()

def create_folder(data):
    name = required(data, "name")
    parent = data.get("parent_id") or None
    folders = read(FOLDERS)
    if parent and not any(str(f.get("id")) == str(parent) for f in folders):
        raise ValueError("Pasta pai inexistente")
    item = {"id": str(uuid.uuid4()), "name": name, "parent_id": parent}
    folders.append(item)
    write(FOLDERS, folders)
    return item

def create_product(data):
    name = required(data, "name")
    kind = required(data, "type")
    if kind not in TYPES:
        raise ValueError("Tipo de produto não suportado")
    folder = data.get("folder_id") or None
    if folder and not any(str(f.get("id")) == str(folder) for f in read(FOLDERS)):
        raise ValueError("Pasta inexistente")
    products = read(REGISTRY)
    pid = str(uuid.uuid4())
    item = {"id": pid, "name": name, "type": kind, "folder_id": folder,
            "code": str(data.get("code") or "").strip(), "description": str(data.get("description") or "").strip(),
            "status": "Rascunho"}
    products.append(item)
    write(REGISTRY, products)
    return item

def create_component(data):
    name = required(data, "name")
    kind = required(data, "type")
    library = read(COMPONENTS)
    item = {"id": str(uuid.uuid4()), "name": name, "type": kind, "status": "Rascunho",
            "version": 1, "content": data.get("content") if isinstance(data.get("content"), dict) else {}}
    library.append(item)
    write(COMPONENTS, library)
    return item

def attach_component(data):
    product_id = required(data, "product_id")
    component_id = required(data, "component_id")
    if not any(str(p.get("id")) == product_id for p in read(REGISTRY)):
        raise ValueError("Produto não cadastrado")
    component = next((c for c in read(COMPONENTS) if c.get("id") == component_id), None)
    if not component:
        raise ValueError("Componente não encontrado na biblioteca")
    path = PRODUCT_FILES / (product_id + ".json")
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        doc = {"id": product_id, "pages": [{"name": "Página 1", "components": []}]}
    pages = doc.setdefault("pages", [])
    if not pages:
        pages.append({"name": "Página 1", "components": []})
    if any(c.get("library_component_id") == component_id for page in pages for c in page.get("components", []) if isinstance(c, dict)):
        raise ValueError("Componente já vinculado a este produto")
    pages[0].setdefault("components", []).append({
        "id": str(uuid.uuid4()), "library_component_id": component_id,
        "library_version": component["version"], "type": component["type"], "title": component["name"]
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    write_object(path, doc)
    return {"product_id": product_id, "component_id": component_id}

def write_object(path, doc):
    fd, name = tempfile.mkstemp(prefix=".dashboard-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(doc, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

OPERATIONS = {"folder": create_folder, "product": create_product, "component": create_component, "attach": attach_component}
