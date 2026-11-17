"""Browser smoke for the single React BI Factory interface.

Runs only in isolated CI using synthetic CSV. No operational product mutation.
"""
import os
from playwright.sync_api import sync_playwright, expect


def test_react_workspaces_share_a_persisted_analysis():
    base = os.environ.get("BI_BROWSER_TEST_URL", "http://127.0.0.1:8506/")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(base, wait_until="domcontentloaded")
            page.get_by_role("button", name="Entrada de dados").click()
            expect(page.get_by_role("heading", name="Importar e analisar fonte tabular")).to_be_visible()
            page.locator('input[type="file"]').set_input_files({
                "name": "fonte-sintetica.csv",
                "mimeType": "text/csv",
                "buffer": b"Codigo,Valor,Unidade\n001,100,Saude\n002,250,Educacao\n",
            })
            page.get_by_role("button", name="Analisar arquivo").click()
            expect(page.get_by_text("Análise persistida. O arquivo original não foi alterado.")).to_be_visible(timeout=30000)
            expect(page.get_by_role("heading", name="Campos detectados")).to_be_visible()

            page.get_by_role("button", name="Conhecimento").click()
            expect(page.get_by_role("heading", name="Questionário semântico")).to_be_visible()
            expect(page.get_by_role("heading", name="fonte-sintetica.csv")).to_be_visible()

            page.get_by_role("button", name="Modelagem").click()
            expect(page.get_by_role("heading", name="Pipeline de modelagem recuperado")).to_be_visible()
            expect(page.get_by_text("Esquema estrela", exact=True).first).to_be_visible()

            page.reload(wait_until="domcontentloaded")
            expect(page.get_by_role("heading", name="Pipeline de modelagem recuperado")).not_to_be_visible()
            page.get_by_role("button", name="Entrada de dados").click()
            expect(page.get_by_role("heading", name="fonte-sintetica.csv")).to_be_visible(timeout=30000)

            page.get_by_role("button", name="Produtos").click()
            expect(page.get_by_role("button", name="Novo produto")).to_be_visible()
        finally:
            browser.close()
