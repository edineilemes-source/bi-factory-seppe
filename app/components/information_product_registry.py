"""Persistent, shared metadata registry for BI Factory information products."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "storage" / "information_products" / "registry.json"
TYPES = ("Painel", "Portal", "PDF", "Relatório", "Documento")
FOLDERS = ROOT / "storage" / "information_products" / "folders.json"
DEFAULT_FOLDERS = ("Finanças Públicas", "Saúde", "Educação", "Planejamento")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_registry() -> list[dict]:
    if not REGISTRY.exists():
        return []
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Catálogo de produtos inválido")
    return data


def save_registry(products: list[dict]) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    temp = REGISTRY.with_suffix(".tmp")
    temp.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, REGISTRY)


def create_product(name: str, kind: str, description: str = "", refresh_policy: str = "Manual",
                   destination: str = "", folder_id: str | None = None, visibility: str = "Interno") -> dict:
    if kind not in TYPES:
        raise ValueError("Tipo de produto não reconhecido")
    if not name.strip():
        raise ValueError("Informe o nome do produto")
    if folder_id and folder_id not in {folder["id"] for folder in load_folders()}:
        raise ValueError("Pasta não encontrada")
    products = load_registry()
    identifier = str(uuid4())
    now = _now()
    product = {
        "id": identifier, "code": "SEPPE-" + identifier[:8].upper(),
        "name": name.strip(), "type": kind, "description": description.strip(),
        "created_at": now, "updated_at": now, "version": 1,
        "refresh_policy": refresh_policy, "destination": destination,
        "status": "Rascunho", "components": [], "distribution": [],
        "folder_id": folder_id, "visibility": visibility, "display_order": 0,
    }
    products.append(product)
    save_registry(products)
    return product


def update_product(identifier: str, **changes: str) -> dict:
    allowed = {"name", "description", "refresh_policy", "destination", "status", "folder_id", "visibility", "display_order"}
    products = load_registry()
    for product in products:
        if product["id"] == identifier:
            for field, value in changes.items():
                if field not in allowed:
                    raise ValueError("Campo não editável: " + field)
                if field == "folder_id" and value and value not in {folder["id"] for folder in load_folders()}:
                    raise ValueError("Pasta não encontrada")
                if field == "visibility" and value not in ("Público", "Interno", "Restrito"):
                    raise ValueError("Visibilidade inválida")
                product[field] = value
            product["updated_at"] = _now()
            product["version"] += 1
            save_registry(products)
            return product
    raise KeyError(identifier)

def sync_product_components(identifier: str, component_ids: list[str], status: str | None = None) -> dict:
    """Persist the list of components linked to an information product."""
    products = load_registry()
    for product in products:
        if product["id"] == identifier:
            product["components"] = list(dict.fromkeys(component_ids))
            if status is not None:
                product["status"] = status
            product["updated_at"] = _now()
            product["version"] += 1
            save_registry(products)
            return product
    raise KeyError(identifier)

def load_folders() -> list[dict]:
    if not FOLDERS.exists():
        return [{"id": "default-" + str(i), "name": name, "parent_id": None, "order": i}
                for i, name in enumerate(DEFAULT_FOLDERS)]
    data = json.loads(FOLDERS.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Catálogo de pastas inválido")
    return data


def save_folders(folders: list[dict]) -> None:
    FOLDERS.parent.mkdir(parents=True, exist_ok=True)
    temp = FOLDERS.with_suffix(".tmp")
    temp.write_text(json.dumps(folders, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, FOLDERS)


def create_folder(name: str, parent_id: str | None = None) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Informe o nome da pasta")
    folders = load_folders()
    if parent_id and parent_id not in {folder["id"] for folder in folders}:
        raise ValueError("Pasta superior não encontrada")
    if any(folder["name"].casefold() == name.casefold() and folder.get("parent_id") == parent_id for folder in folders):
        raise ValueError("Já existe uma pasta com este nome neste nível")
    folder = {"id": str(uuid4()), "name": name, "parent_id": parent_id, "order": len(folders)}
    folders.append(folder)
    save_folders(folders)
    return folder
