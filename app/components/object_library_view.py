"""Catalog of BI information products and their published components."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st
from app.components.information_product_registry import TYPES, create_product, load_registry, update_product, load_folders, create_folder, folder_choices

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = ROOT / "storage" / "dashboard_projects" / "published.json"


def render_object_library() -> None:
    st.subheader("Biblioteca de Objetos de Informação")
    st.caption("Inventário dos produtos, componentes, destinos e configurações disponíveis. "
               "Metadados não registrados aparecem como 'Não informado', sem datas inventadas.")
    folders = load_folders()
    folder_labels = folder_choices()
    try:
        registered = load_registry()
    except (ValueError, OSError) as exc:
        st.error("Não foi possível carregar os produtos: " + str(exc))
        registered = []

    if PUBLISHED.exists():
        try:
            legacy = json.loads(PUBLISHED.read_text(encoding="utf-8"))
            count = sum(len(page.get("components", [])) for page in legacy.get("pages", []))
            registered.append({
                "id": "__legacy__", "code": "SEPPE-LEGADO",
                "name": legacy.get("name") or "Sala Executiva — Execução Orçamentária",
                "type": "Painel", "folder_id": None, "version": legacy.get("version", 1),
                "status": "Publicado na 8503",
                "description": legacy.get("description") or "Sala de Gestão original",
                "created_at": legacy.get("created_at") or "Não informado",
                "updated_at": legacy.get("updated_at") or "Não informado",
                "components": [None] * count,
                "refresh_policy": legacy.get("refresh_policy") or "Conforme fonte",
                "destination": "8503 /", "visibility": "Interno",
            })
        except (ValueError, OSError) as exc:
            st.warning("Erro ao carregar publicação original: " + str(exc))

    st.markdown("**Organização:** Pastas → Subpastas → Produtos de informação → Gráficos e indicadores")
    st.caption("Pastas organizam os produtos; os gráficos pertencem aos produtos. A Sala de Gestão na porta 8503 exibe somente o que foi publicado.")
    with st.expander("＋ Criar pasta, subpasta ou produto", expanded=False):
        tab_folder, tab_product = st.tabs(["Nova pasta ou subpasta", "Novo produto"])
        with tab_folder:
            with st.form("create_folder"):
                folder_name = st.text_input("Nome da nova pasta")
                parent_label = st.selectbox("Pasta superior", list(folder_labels), help="Escolha Sem pasta para criar uma pasta principal.")
                add_folder = st.form_submit_button("Criar pasta")
            if add_folder:
                try:
                    created = create_folder(folder_name, folder_labels[parent_label])
                    st.success("Pasta criada: " + created["name"])
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
        with tab_product:
            with st.form("create_information_product"):
                name = st.text_input("Nome do produto")
                kind = st.selectbox("Tipo de produto", TYPES)
                description = st.text_area("Descrição")
                refresh = st.selectbox("Atualização dos dados", ["Manual", "Conforme fonte", "Diária", "Semanal", "Mensal"])
                destination = st.text_input("Destino de publicação")
                folder_label = st.selectbox("Localização na biblioteca", list(folder_labels))
                visibility = st.selectbox("Visibilidade (cadastro, não controle de acesso)", ["Interno", "Público", "Restrito"])
                submit = st.form_submit_button("Criar produto", type="primary")
            if submit:
                try:
                    product = create_product(name, kind, description, refresh, destination, folder_labels[folder_label], visibility)
                    st.success("Produto criado: " + product["code"])
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))

    st.markdown("### Explorador de objetos")
    left, right = st.columns([1, 2.5], gap="large")
    selected = st.session_state.get("library_folder_id", "__all__")
    valid_ids = {"__all__", None} | {f["id"] for f in folders}
    if selected not in valid_ids:
        selected = "__all__"
    by_parent = {}
    for folder in folders:
        by_parent.setdefault(folder.get("parent_id"), []).append(folder)
    with left:
        st.markdown("**Pastas e subpastas**")
        st.caption("Selecione uma pasta para ver os produtos à direita.")
        if st.button("▦ Todos os produtos", use_container_width=True, type="primary" if selected == "__all__" else "secondary"):
            st.session_state["library_folder_id"] = "__all__"
            st.rerun()
        if st.button("▤ Sem pasta", use_container_width=True, type="primary" if selected is None else "secondary"):
            st.session_state["library_folder_id"] = None
            st.rerun()
        def draw_folder(folder, depth=0, ancestors=frozenset()):
            identifier = folder["id"]
            if identifier in ancestors:
                st.error("Ciclo na hierarquia de pastas.")
                return
            path = next((label for label, fid in folder_labels.items() if fid == identifier), folder["name"])
            count = sum(p.get("folder_id") == identifier for p in registered)
            prefix = "　" * min(depth, 6) + ("📂 " if selected == identifier else "📁 ")
            if st.button(prefix + folder["name"] + (f" ({count})" if count else ""),
                         key="library_folder_" + identifier, help=path,
                         use_container_width=True, type="primary" if selected == identifier else "secondary"):
                st.session_state["library_folder_id"] = identifier
                st.rerun()
            for child in sorted(by_parent.get(identifier, []), key=lambda f: f["name"].casefold()):
                draw_folder(child, depth + 1, ancestors | {identifier})
        for folder in sorted((f for f in folders if not f.get("parent_id") or f["parent_id"] not in {x["id"] for x in folders}), key=lambda f: f["name"].casefold()):
            draw_folder(folder)
    with right:
        current_path = ("Todos os produtos" if selected == "__all__" else
                        "Sem pasta" if selected is None else
                        next((label for label, fid in folder_labels.items() if fid == selected), "Pasta"))
        st.markdown("**Localização: " + current_path + "**")
        search = st.text_input("Buscar nesta localização", placeholder="Nome, código ou tipo do produto", key="library_search")
        visible = [p for p in registered if (selected == "__all__" or p.get("folder_id") == selected)
                   and search.casefold() in (p["name"] + " " + p["code"] + " " + p["type"]).casefold()]
        st.caption(f"{len(visible)} produto(s) nesta visualização. Abra um produto para consultar ou editar sua ficha.")
        if not visible:
            st.info("Nenhum produto nesta localização. Selecione outra pasta ou crie um produto.")
        for product in visible:
            with st.expander(("📊 " if product["type"] in ("Painel", "Portal") else "📄 ") +
                             product["name"] + " · " + product["code"]):
                st.caption("Tipo: " + product["type"] + " · Versão: " + str(product.get("version", 1)) +
                           " · Situação: " + product.get("status", "Não informado"))
                st.write(product.get("description") or "Sem descrição.")
                st.caption("Criado: " + product.get("created_at", "Não informado") +
                           " · Alterado: " + product.get("updated_at", "Não informado"))
                st.write("Componentes associados:", len(product.get("components", [])))
                if product["type"] in ("Painel", "Portal"):
                    if st.button("Abrir no Estúdio Visual", key="open_" + product["id"], type="primary"):
                        st.session_state["studio_product_id"] = product["id"]
                        st.session_state["studio_open_published"] = True
                        st.query_params["open_studio"] = "1"
                        st.rerun()
                if product["id"] == "__legacy__":
                    st.caption("Produto original: edite o conteúdo pelo Estúdio Visual.")
                    continue
                with st.form("edit_" + product["id"]):
                    st.markdown("**Editar identificação e localização**")
                    edited_name = st.text_input("Nome", value=product["name"])
                    edited_description = st.text_area("Descrição", value=product.get("description", ""))
                    edited_refresh = st.text_input("Regra de atualização", value=product.get("refresh_policy", "Manual"))
                    edited_destination = st.text_input("Destino", value=product.get("destination", ""))
                    current_folder = next((label for label, fid in folder_labels.items() if fid == product.get("folder_id")), "Sem pasta")
                    edited_folder = st.selectbox("Mover para pasta", list(folder_labels), index=list(folder_labels).index(current_folder))
                    edited_visibility = st.selectbox("Visibilidade", ["Interno", "Público", "Restrito"],
                        index=["Interno", "Público", "Restrito"].index(product.get("visibility", "Interno"))
                        if product.get("visibility", "Interno") in ("Interno", "Público", "Restrito") else 0)
                    save = st.form_submit_button("Salvar alterações")
                if save:
                    try:
                        update_product(product["id"], name=edited_name, description=edited_description,
                                       refresh_policy=edited_refresh, destination=edited_destination,
                                       folder_id=folder_labels[edited_folder], visibility=edited_visibility)
                        st.success("Ficha atualizada.")
                        st.rerun()
                    except (ValueError, OSError) as exc:
                        st.error(str(exc))
