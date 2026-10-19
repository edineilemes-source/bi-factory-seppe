"""Catalog of BI information products and their published components."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st
from app.components.information_product_registry import TYPES, create_product, load_registry, update_product, load_folders, create_folder

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = ROOT / "storage" / "dashboard_projects" / "published.json"


def render_object_library() -> None:
    st.subheader("Biblioteca de Objetos de Informação")
    st.caption("Inventário dos produtos, componentes, destinos e configurações disponíveis. "
               "Metadados não registrados aparecem como 'Não informado', sem datas inventadas.")
    folders = load_folders()
    folder_labels = {"Sem pasta": None}
    folder_labels.update({("↳ " if f.get("parent_id") else "") + f["name"] + " · " + f["id"][:8]: f["id"] for f in folders})
    with st.expander("Gerenciar pastas e subpastas"):
        with st.form("create_folder"):
            folder_name = st.text_input("Nome da pasta")
            parent_label = st.selectbox("Dentro de", list(folder_labels))
            add_folder = st.form_submit_button("Criar pasta")
        if add_folder:
            try:
                created_folder = create_folder(folder_name, folder_labels[parent_label])
                st.success("Pasta criada: " + created_folder["name"])
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    with st.expander("Criar produto de informação"):
        with st.form("create_information_product"):
            name = st.text_input("Nome")
            kind = st.selectbox("Tipo", TYPES)
            description = st.text_area("Descrição")
            refresh = st.selectbox("Atualização", ["Manual", "Conforme fonte", "Diária", "Semanal", "Mensal"])
            destination = st.text_input("Destino")
            folder_label = st.selectbox("Pasta", list(folder_labels))
            visibility = st.selectbox("Visibilidade", ["Interno", "Público", "Restrito"])
            submit = st.form_submit_button("Criar produto", type="primary")
        if submit:
            try:
                product = create_product(name, kind, description, refresh, destination, folder_labels[folder_label], visibility)
                st.success("Produto criado: " + product["code"])
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    st.markdown("### Produtos cadastrados")
    try:
        registered = load_registry()
    except (ValueError, OSError) as exc:
        st.error(str(exc))
        registered = []
    for product in registered:
        with st.expander(product["code"] + " · " + product["name"] + " (" + product["type"] + ")"):
            st.caption("ID: " + product["id"] + " · Criado: " + product["created_at"] + " · Alterado: " + product["updated_at"])
            with st.form("edit_" + product["id"]):
                edited_name = st.text_input("Nome", value=product["name"])
                edited_description = st.text_area("Descrição", value=product.get("description", ""))
                edited_refresh = st.text_input("Regra de atualização", value=product.get("refresh_policy", "Manual"))
                edited_destination = st.text_input("Destino", value=product.get("destination", ""))
                current_folder = next((label for label, fid in folder_labels.items() if fid == product.get("folder_id")), "Sem pasta")
                edited_folder = st.selectbox("Pasta", list(folder_labels), index=list(folder_labels).index(current_folder))
                edited_visibility = st.selectbox("Visibilidade", ["Interno", "Público", "Restrito"],
                    index=["Interno", "Público", "Restrito"].index(product.get("visibility", "Interno"))
                    if product.get("visibility", "Interno") in ("Interno", "Público", "Restrito") else 0)
                save = st.form_submit_button("Salvar ficha")
            if product["type"] in ("Painel", "Portal"):
                if st.button("Abrir produto no Estúdio Visual", key="open_" + product["id"]):
                    st.session_state["studio_product_id"] = product["id"]
                    st.session_state["studio_open_published"] = True
                    st.query_params["open_studio"] = "1"
                    st.rerun()
            if save:
                try:
                    update_product(product["id"], name=edited_name, description=edited_description,
                                   refresh_policy=edited_refresh, destination=edited_destination,
                                   folder_id=folder_labels[edited_folder], visibility=edited_visibility)
                    st.success("Ficha atualizada.")
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
    st.markdown("### Sala de Gestão publicada")
    if not PUBLISHED.exists():
        st.info("Nenhuma configuração publicada foi encontrada. Publique um gráfico na 8502 para iniciar o inventário.")
        return
    try:
        project = json.loads(PUBLISHED.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        st.error(f"Não foi possível ler a biblioteca: {exc}")
        return
    pages = project.get("pages", [])
    components = [c for page in pages for c in page.get("components", [])]
    st.metric("Componentes publicados", len(components))
    st.markdown("### Produtos de informação")
    with st.container(border=True):
        st.markdown("**Sala de Gestão · 8503**")
        st.write("Nome:", project.get("name", "Sala de Situação — SEPPE"))
        st.write("Localização: Porta 8503 · /")
        st.write("Criado em:", project.get("created_at", "Não informado"))
        st.write("Alterado em:", project.get("updated_at", "Não informado"))
        st.write("Atualização:", project.get("refresh_policy", "Conforme atualização da fonte; periodicidade não informada"))
        st.write("Gráficos e indicadores:", len(components))
        if st.button("Abrir no Estúdio Visual para editar", type="primary", key="library_open_studio"):
            st.session_state["studio_product_id"] = project.get("product_id") or ""
            st.session_state["studio_open_published"] = True
            st.query_params["open_studio"] = "1"
            st.rerun()
    st.markdown("### Outros produtos")
    st.info("PDFs e páginas de transparência serão inventariados quando forem registrados como produtos gerenciados. "
            "Não são presumidos a partir de arquivos sem metadados.")
    st.download_button("Exportar inventário JSON", data=json.dumps(project, ensure_ascii=False, indent=2),
                       file_name="inventario-bi-factory.json", mime="application/json")
