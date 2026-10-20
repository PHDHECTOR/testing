from pathlib import Path
from threading import Thread
import json
import secrets
import shutil
import tempfile
import unittest
import base64

from playwright.sync_api import sync_playwright
from werkzeug.security import generate_password_hash
from werkzeug.serving import WSGIRequestHandler, make_server

from app import create_app
from app.store import database

ROOT = Path(__file__).resolve().parents[1]


class QuietRequestHandler(WSGIRequestHandler):
    def log(self, *_args, **_kwargs):
        pass


class BrowserCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.state = Path(cls.temp.name)
        cls.username = 'colega_prueba'
        cls.password = secrets.token_urlsafe(24)
        cls.app = create_app({'STATE_DIR': cls.state, 'ALLOW_HTTP_LOCAL': True, 'SESSION_COOKIE_SECURE': False})
        with database(cls.state) as db:
            db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)', (cls.username, generate_password_hash(cls.password)))
        cls.server = make_server('127.0.0.1', 0, cls.app, threaded=True, request_handler=QuietRequestHandler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'
        cls.reference = json.loads((ROOT / 'build/validation.json').read_text())
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1000})
        self.external = []
        def external_resource(route):
            self.external.append(route.request.url.split('/')[2])
            if route.request.url.startswith('https://a.basemaps.cartocdn.com/light_all/'):
                # Tesela simulada: valida la integración sin depender del proveedor.
                tile = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
                route.fulfill(status=200, content_type='image/png', body=tile)
            else:
                route.abort()
        self.context.route('https://**/*', external_resource)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

    def login(self):
        self.page.goto(self.url + 'login', wait_until='networkidle')
        self.page.locator('#username').fill(self.username)
        self.page.locator('#password').fill(self.password)
        self.page.get_by_role('button', name='Entrar al informe privado').click()
        self.page.wait_for_url('**/privado/')

    def tearDown(self):
        try:
            self.assertEqual(self.errors, [], 'Se produjo un error JavaScript.')
        finally:
            self.context.close()
