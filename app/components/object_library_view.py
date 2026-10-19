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
    st.markdown("""
    <style>
    /* Identidade visual da biblioteca: navegação discreta, conteúdo em primeiro plano. */
    div[data-testid="stMainBlockContainer"] {
        max-width: none;
        padding-left: 2cm;
        padding-right: 1.25rem;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stExpander"] {
        border: 1px solid #e4eaf2; border-radius: 12px; background: #fff;
        box-shadow: 0 2px 12px rgba(19, 41, 72, .025);
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stExpander"] summary:hover {
        background: #f5f8fc; border-radius: 12px;
    }
    div[data-testid="stVerticalBlock"] button[kind="secondary"] {
        border-color: #e3eaf3; border-radius: 9px; background: #fff;
        color: #273d58; font-weight: 500;
    }
    div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover {
        border-color: #8bb1d7; background: #f2f7fc; color: #174f84;
    }
    div[data-testid="stVerticalBlock"] button[kind="primary"] {
        border-radius: 9px; background: #1766a3; border-color: #1766a3;
    }
    /* Streamlit centraliza o conteúdo por padrão: direcionar apenas aos botões de pastas. */
    [class*="st-key-library_folder_"] button {
        justify-content: flex-start !important;
        text-align: left !important;
        padding-left: 12px !important;
    }
    [class*="st-key-library_folder_"] button > div,
    [class*="st-key-library_folder_"] button p {
        text-align: left !important;
        justify-content: flex-start !important;
        width: auto !important;
    }
    /* Alinhar o conteúdo dos botões de pasta à esquerda, sem deslocar as setas. */
    div[data-testid="stVerticalBlock"] button[kind="secondary"] p,
    div[data-testid="stVerticalBlock"] button[kind="primary"] p {
        text-align: left;
        width: 100%;
    }
        div[data-testid="stVerticalBlock"] button[kind="primary"]:hover {
        background: #105184; border-color: #105184;
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("## Biblioteca de objetos")
    st.caption("Encontre, organize e gerencie os produtos de informação da SEPPE.")
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

    st.markdown("### Explorar biblioteca")
    left, right = st.columns([1.05, 2.9], gap="large")
    selected = st.session_state.get("library_folder_id", "__all__")
    valid_ids = {"__all__", None} | {f["id"] for f in folders}
    if selected not in valid_ids:
        selected = "__all__"
    by_parent = {}
    for folder in folders:
        by_parent.setdefault(folder.get("parent_id"), []).append(folder)
    with left:
        st.markdown("**PASTAS**")
        st.caption("Clique na pasta para abrir suas subpastas e visualizar os produtos.")
        folder_ids = {folder["id"] for folder in folders}
        parent_of = {folder["id"]: folder.get("parent_id") for folder in folders}
        def is_descendant(folder_id, ancestor_id):
            visited = set()
            current = folder_id
            while current and current not in visited:
                if current == ancestor_id:
                    return True
                visited.add(current)
                current = parent_of.get(current)
            return False

        def draw_folder(folder, depth=0, ancestors=frozenset()):
            identifier = folder["id"]
            if identifier in ancestors:
                st.error("Hierarquia de pastas inválida: referência circular.")
                return
            children = sorted(by_parent.get(identifier, []), key=lambda f: f["name"].casefold())
            path = next((label for label, fid in folder_labels.items() if fid == identifier), folder["name"])
            count = sum(p.get("folder_id") == identifier for p in registered)
            # O nome da pasta é o único controle: sem setas separadas.
            if depth:
                indent_col, folder_col = st.columns([min(depth, 6) * 0.12, max(0.28, 1 - min(depth, 6) * 0.12)], gap="small")
                with indent_col:
                    st.empty()
            else:
                folder_col = st.container()
            with folder_col:
                label = ("📂 " if selected == identifier else "📁 ") + folder["name"]
                if count:
                    label += f" · {count}"
                if st.button(label, key="library_folder_" + identifier, help=path,
                             use_container_width=True,
                             type="primary" if selected == identifier else "secondary"):
                    st.session_state["library_folder_id"] = identifier
                    st.rerun()
            # A ramificação selecionada abre automaticamente até a pasta ativa.
            if selected != "__all__" and selected is not None and is_descendant(selected, identifier):
                for child in children:
                    draw_folder(child, depth + 1, ancestors | {identifier})
        roots = sorted(
            (f for f in folders if not f.get("parent_id") or f["parent_id"] not in folder_ids),
            key=lambda f: f["name"].casefold(),
        )
        for folder in roots:
            draw_folder(folder)
    with right:
        st.markdown("**PRODUTOS**")
        if st.button("▦ Ver todos os produtos", use_container_width=False,
                     type="primary" if selected == "__all__" else "secondary"):
            st.session_state["library_folder_id"] = "__all__"
            st.rerun()
        current_path = ("Todos os produtos" if selected == "__all__" else
                        "Sem pasta" if selected is None else
                        next((label for label, fid in folder_labels.items() if fid == selected), "Pasta"))
        st.caption("Visualizando: " + current_path)
        search = st.text_input("Buscar produtos", placeholder="Nome, código ou tipo", key="library_search")
        def matches_search(product):
            return search.casefold() in (
                product["name"] + " " + product["code"] + " " + product["type"]
            ).casefold()
        if selected == "__all__":
            visible = [p for p in registered if matches_search(p)]
            groups = [
                ("Sem pasta", [p for p in visible if not p.get("folder_id")]),
                ("Nas pastas", [p for p in visible if p.get("folder_id")]),
            ]
        elif selected is None:
            visible = [p for p in registered if not p.get("folder_id") and matches_search(p)]
            groups = [("Sem pasta", visible)]
        else:
            visible = [
                p for p in registered
                if p.get("folder_id") and is_descendant(p["folder_id"], selected)
                and matches_search(p)
            ]
            groups = [
                ("Diretamente nesta pasta", [p for p in visible if p.get("folder_id") == selected]),
                ("Nas subpastas", [p for p in visible if p.get("folder_id") != selected]),
            ]
        st.caption(f"{len(visible)} produto(s) · Selecione um item para consultar ou editar.")
        if not visible:
            st.info("Nenhum produto nesta localização.")
        for group_title, group_products in groups:
            st.markdown("##### " + group_title + f"  ·  {len(group_products)}")
            if not group_products:
                st.caption("Nenhum produto neste grupo.")
            for product in group_products:
                location = next((label for label, fid in folder_labels.items() if fid == product.get("folder_id")), "Sem pasta")
                with st.expander(("📊 " if product["type"] in ("Painel", "Portal") else "📄 ") +
                                 product["name"] + " · " + product["code"] + "  |  📁 " + location):
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
