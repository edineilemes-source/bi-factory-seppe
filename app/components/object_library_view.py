"""Catalog of BI information products and their published components."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = ROOT / "storage" / "dashboard_projects" / "published.json"


def render_object_library() -> None:
    st.subheader("Biblioteca de Objetos de Informação")
    st.caption("Inventário dos produtos, componentes, destinos e configurações disponíveis. "
               "Metadados não registrados aparecem como 'Não informado', sem datas inventadas.")
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
        for c in components:
            with st.expander(c.get("title", "Objeto sem título")):
                st.write("Tipo:", c.get("visual_subtype", c.get("component_type", "Não informado")))
                st.write("Métricas:", ", ".join(m.get("label", m.get("field", "")) for m in c.get("metrics", [])))
                st.write("Dimensões:", ", ".join(d.get("label", d.get("field", "")) for d in c.get("dimensions", [])) or "Nenhuma")
                st.write("Identificador:", c.get("id", "Legado: não informado"))
                st.write("Criado em:", c.get("created_at", "Não informado"))
                st.write("Alterado em:", c.get("updated_at", "Não informado"))
                st.json({"cores": c.get("series_colors", []), "posição": c.get("position", {})})
    st.markdown("### Outros produtos")
    st.info("PDFs e páginas de transparência serão inventariados quando forem registrados como produtos gerenciados. "
            "Não são presumidos a partir de arquivos sem metadados.")
    st.download_button("Exportar inventário JSON", data=json.dumps(project, ensure_ascii=False, indent=2),
                       file_name="inventario-bi-factory.json", mime="application/json")
