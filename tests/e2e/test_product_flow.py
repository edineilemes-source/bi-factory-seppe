"""Real API + React tests. Every storage path is redirected to a disposable fixture.
Run: python -m unittest discover -s tests/e2e -v
Requires playwright (Apache-2.0), Chromium and npm ci in web/bi_factory.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import serve_bi_factory_api as api
import bi_factory_catalog as catalog
from playwright.sync_api import sync_playwright


class ProductFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='seppe-e2e-')
        fixture = Path(cls.fixture.name)
        cls.originals = []
        editor = api.visual_editor_server
        for module in (api, catalog, editor, editor.registry):
            for key, value in list(vars(module).items()):
                if isinstance(value, Path) and value.is_relative_to(ROOT / 'storage'):
                    cls.originals.append((module, key, value))
                    setattr(module, key, fixture / value.relative_to(ROOT))
        cls.server = ThreadingHTTPServer(('127.0.0.1', 8505), api.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.vite = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '8506', '--strictPort'], cwd=ROOT / 'web/bi_factory', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urlopen('http://127.0.0.1:8506/api/overview', timeout=1).close()
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError('Frontend did not start')
        cls.pw = sync_playwright().start()
        executable = os.environ.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium')
        cls.browser = cls.pw.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.vite.terminate()
        cls.vite.wait(timeout=10)
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        for module, key, value in cls.originals:
            setattr(module, key, value)
        cls.fixture.cleanup()

    def setUp(self):
        # Empty only the fixture, never the operational registry.
        catalog.write(catalog.REGISTRY, [])
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto('http://127.0.0.1:8506')
        self.page.get_by_role('button', name='Produtos', exact=True).click()

    def tearDown(self):
        self.context.close()

    def products(self):
        return self.page.request.get('http://127.0.0.1:8506/api/products').json()

    def new(self, name):
        self.page.get_by_role('button', name='Novo produto', exact=True).click()
        self.page.get_by_label('Nome', exact=True).fill(name)

    def open_editor(self):
        self.page.get_by_role('button', name='Abrir Editor Visual').click()
        self.page.locator('.visualOverlay iframe').wait_for()
        self.page.frame_locator('.visualOverlay iframe').locator('#save').wait_for()

    def save(self):
        self.open_editor()
        self.page.frame_locator('.visualOverlay iframe').locator('#save').click()
        self.page.locator('.visualOverlay').wait_for(state='hidden')
        self.page.get_by_text('Produto e metadados salvos com sucesso.', exact=True).wait_for()

    def close_editor(self):
        if self.page.locator('.visualOverlay').count():
            self.page.keyboard.press('Escape')
            self.page.locator('.visualOverlay').wait_for(state='hidden')

    def test_deferred_creation_and_consecutive_saves(self):
        self.new('Primeiro sintético')
        self.open_editor()
        self.assertEqual(self.products(), [])
        self.page.frame_locator('.visualOverlay iframe').locator('#save').click()
        self.page.locator('.visualOverlay').wait_for(state='hidden')
        self.assertEqual(len(self.products()), 1)
        self.assertEqual(self.page.get_by_role('button', name='Editar metadados').count(), 1)
        self.assertEqual(self.page.get_by_role('button', name='Editar visual').count(), 1)
        self.assertEqual(self.page.get_by_role('button', name='Visualizar produto', exact=True).count() >= 1, True)
        self.new('Segundo sintético')
        self.assertEqual(self.page.locator('#product-details').count(), 0)
        self.save()
        both = self.products()
        self.assertEqual(len(both), 2)
        self.assertNotEqual(both[0]['id'], both[1]['id'])
        self.assertNotEqual(both[0]['code'], both[1]['code'])
        self.page.get_by_role('button', name='Editar metadados').click()
        self.page.get_by_label('Descrição', exact=True).fill('Metadado persistido')
        self.page.get_by_role('button', name='Salvar alterações').click()
        self.page.get_by_text('Metadados salvos com sucesso.', exact=True).wait_for()
        self.assertEqual(self.products()[1]['description'], 'Metadado persistido')
        self.assertEqual(self.errors, [])

    def test_cancel_before_save_does_not_create_product(self):
        self.new('Não persistido')
        self.open_editor()
        self.close_editor()
        self.assertEqual(self.products(), [])
        self.assertEqual(self.page.get_by_label('Nome', exact=True).input_value(), 'Não persistido')

    def test_failed_create_keeps_draft_for_retry(self):
        self.new('Falha recuperável')
        self.open_editor()
        self.page.route('**/api/create/product', lambda route: route.fulfill(status=503, json={'error':'Falha sintética'}))
        self.page.frame_locator('.visualOverlay iframe').locator('#save').click()
        self.page.get_by_text('Erro ao salvar produto: Falha sintética', exact=True).wait_for()
        self.assertEqual(self.products(), [])
        self.page.unroute('**/api/create/product')
        self.page.frame_locator('.visualOverlay iframe').locator('#save').click()
        self.page.locator('.visualOverlay').wait_for(state='hidden')
        self.assertEqual(len(self.products()), 1)

    def test_blank_name_is_not_persisted(self):
        self.new('   ')
        self.page.get_by_role('button', name='Abrir Editor Visual').click()
        self.page.get_by_text('Informe o nome do produto.', exact=True).wait_for()
        self.assertEqual(self.products(), [])

    def test_delete_product_updates_list_and_clears_open_record(self):
        self.new('Excluir sintético')
        self.save()
        self.close_editor()
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('.productPanel').filter(has_text='Excluir sintético').get_by_role('button', name='Apagar', exact=True).click()
        self.page.get_by_text('Produto "Excluir sintético" apagado.', exact=True).wait_for()
        self.assertEqual(self.products(), [])
        self.assertEqual(self.page.locator('.productPanel').count(), 0)
        self.assertEqual(self.page.locator('#product-details').count(), 0)
        self.assertEqual(self.errors, [])

    def test_delete_committed_then_refresh_failure_does_not_leave_stale_row(self):
        self.new('Excluir com falha de atualização')
        self.save()
        self.close_editor()
        self.page.route('**/api/overview', lambda route: route.fulfill(status=503, json={'error':'Falha sintética'}))
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('.productPanel').filter(has_text='Excluir com falha de atualização').get_by_role('button', name='Apagar', exact=True).click()
        self.page.get_by_text('O catálogo não pôde ser atualizado; a exclusão já foi concluída.', exact=False).wait_for()
        self.assertEqual(self.products(), [])
        self.assertEqual(self.page.locator('.productPanel').count(), 0)
        self.assertEqual(self.page.locator('#product-details').count(), 0)

    def test_failed_delete_preserves_product_and_reports_api_error(self):
        self.new('Preservar em falha')
        self.save()
        self.close_editor()
        self.page.route('**/api/create/delete-product', lambda route: route.fulfill(status=503, json={'error':'Exclusão recusada sintética'}))
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('.productPanel').filter(has_text='Preservar em falha').get_by_role('button', name='Apagar', exact=True).click()
        self.page.get_by_text('Erro ao apagar produto: Exclusão recusada sintética', exact=True).wait_for()
        self.assertEqual(len(self.products()), 1)
        self.assertEqual(self.page.locator('.productPanel').count(), 1)
