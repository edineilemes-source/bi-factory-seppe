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

    def save(self):
        self.page.get_by_role('button', name='Salvar produto e abrir editor').click()
        self.page.locator('.visualOverlay').wait_for()

    def close_editor(self):
        # Parent's documented keyboard exit; library downloads are not required.
        self.page.keyboard.press('Escape')
        self.page.locator('.visualOverlay').wait_for(state='hidden')

    def test_consecutive_creation_edit_reopen_and_layout(self):
        self.new('Primeiro sintético')
        self.save()
        first = self.products()[0]
        self.assertIn(first['id'], self.page.locator('.visualOverlay iframe').get_attribute('src'))
        self.close_editor()
        self.new('Segundo sintético')
        self.assertEqual(self.page.locator('#product-details').count(), 0)
        self.assertEqual(self.page.get_by_label('Descrição', exact=True).input_value(), '')
        self.save()
        self.close_editor()
        both = self.products()
        self.assertEqual(len(both), 2)
        self.assertNotEqual(both[0]['id'], both[1]['id'])
        self.assertNotEqual(both[0]['code'], both[1]['code'])
        for product in both:
            self.page.locator('.productHeading').filter(has_text=product['name']).click()
            self.assertEqual(self.page.get_by_label('Nome', exact=True).input_value(), product['name'])
        self.page.get_by_label('Descrição', exact=True).fill('Metadado persistido')
        self.page.get_by_role('button', name='Salvar metadados', exact=True).click()
        self.page.get_by_text('Metadados salvos com sucesso.', exact=True).wait_for()
        self.assertEqual(self.products()[1]['description'], 'Metadado persistido')
        identifier = both[1]['id']
        layout = {'schema':'bi-factory-editor-poc-v1','layout':[], 'objects':{}}
        response = self.page.request.put(f'http://127.0.0.1:8506/api/products/{identifier}/layout', data=layout)
        self.assertEqual(response.status, 200)
        self.assertEqual(self.page.request.get(f'http://127.0.0.1:8506/api/products/{identifier}/layout').json(), layout)
        self.page.reload()
        self.assertEqual(len(self.products()), 2)
        self.assertEqual(self.errors, [])

    def test_api_failure_keeps_draft_and_retry(self):
        self.new('Falha recuperável')
        self.page.route('**/api/create/product', lambda route: route.fulfill(status=503, json={'error':'Falha sintética'}))
        self.page.get_by_role('button', name='Salvar produto e abrir editor').click()
        self.page.get_by_text('Erro: Falha sintética', exact=True).wait_for()
        self.assertEqual(self.products(), [])
        self.assertEqual(self.page.get_by_label('Nome', exact=True).input_value(), 'Falha recuperável')
        self.page.unroute('**/api/create/product')
        self.save()
        self.assertEqual(len(self.products()), 1)

    def test_repeated_clicks_create_once(self):
        self.new('Clique repetido')
        button = self.page.get_by_role('button', name='Salvar produto e abrir editor')
        button.evaluate('(b) => { b.click(); b.click(); b.click(); }')
        self.page.locator('.visualOverlay').wait_for()
        self.assertEqual(len(self.products()), 1)

    def test_catalog_refresh_failure_does_not_offer_duplicate_creation(self):
        self.new('Persistido antes da falha')
        self.page.route('**/api/overview', lambda route: route.fulfill(status=503, json={'error':'Catálogo temporariamente indisponível'}))
        self.page.get_by_role('button', name='Salvar produto e abrir editor').click()
        self.page.locator('.visualOverlay').wait_for(timeout=5000)
        self.assertEqual(len(self.products()), 1)
        self.close_editor()
        self.assertEqual(self.page.get_by_role('button', name='Salvar produto e abrir editor').count(), 0)

    def test_blank_name_is_not_persisted(self):
        self.new('   ')
        self.page.get_by_role('button', name='Salvar produto e abrir editor').click()
        self.page.get_by_text('Informe o nome do produto.', exact=True).wait_for()
        self.assertEqual(self.products(), [])
