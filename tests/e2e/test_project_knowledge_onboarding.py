"""Chromium test: project-first onboarding and Knowledge workflow, synthetic only."""
import os
from playwright.sync_api import sync_playwright,expect

def test_new_project_starts_with_knowledge_instead_of_analysis_id():
    url=os.environ.get("BI_BROWSER_TEST_URL","http://127.0.0.1:8506/")
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            page.goto(url,wait_until="domcontentloaded")
            expect(page.get_by_role("heading",name="Meus projetos")).to_be_visible()
            page.get_by_role("button",name="+ Novo projeto").click()
            page.get_by_label("Nome do projeto *").fill("Condomínio de teste")
            page.get_by_label("Tema do projeto *").fill("Prestação de contas condominial")
            page.get_by_label("Abrangência").fill("Mato Grosso do Sul")
            page.get_by_role("button",name="Criar projeto e iniciar conhecimento").click()
            expect(page.get_by_role("heading",name="1. O que você deseja conhecer?")).to_be_visible(timeout=20000)
            expect(page.get_by_text("Análise persistida")).to_have_count(0)
            page.get_by_role("button",name="Registrar solicitação de pesquisa").click()
            expect(page.get_by_text("Solicitação registrada. A pesquisa automática por IA ainda será conectada; nenhuma busca foi executada.")).to_be_visible()
            page.get_by_role("heading",name="3. Acervo de conhecimento").scroll_into_view_if_needed()
            expect(page.get_by_text("Pesquisa solicitada")).to_be_visible()
            page.get_by_role("button",name="Projetos").click()
            expect(page.get_by_text("Condomínio de teste")).to_be_visible()
        finally:
            browser.close()
