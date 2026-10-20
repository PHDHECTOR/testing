from pathlib import Path
from unittest.mock import patch
import re
import secrets
import tempfile
import time
import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from app import accounts
from app.store import database


class AccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(24)
        cls.password_hash = generate_password_hash(cls.password)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name)
        self.app = create_app({'TESTING': True, 'STATE_DIR': self.state})
        self.client = self.app.test_client()
        with database(self.state) as db:
            db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)', ('colega', self.password_hash))

    def tearDown(self):
        self.temp.cleanup()

    def get(self, path, **kwargs):
        return self.client.get(path, base_url='https://localhost', **kwargs)

    def csrf(self):
        response = self.get('/login')
        return re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)

    def login(self):
        token = self.csrf()
        return self.client.post('/login', base_url='https://localhost', data={'csrf_token': token, 'username': 'colega', 'password': self.password})

    def test_anonymous_cannot_read_private_files(self):
        for path in ['/privado/', '/privado/informe']:
            response = self.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith('/login'))
            self.assertNotIn(b'popup_temporal', response.data)
        for path in ['/dist/private/index.html', '/private/index.html', '/static/private/index.html', '/public/../private/index.html', '/reports/private/index.html']:
            self.assertEqual(self.get(path).status_code, 404)
        self.assertEqual(self.get('/').status_code, 200)
        with self.get('/publico.html') as response:
            self.assertEqual(response.status_code, 200)

    def test_csrf_and_generic_login_errors(self):
        response = self.client.post('/login', base_url='https://localhost', data={'username': 'colega', 'password': self.password})
        self.assertEqual(response.status_code, 400)
        token = self.csrf()
        bodies = []
        for username in ['colega', 'inexistente']:
            response = self.client.post('/login', base_url='https://localhost', data={'csrf_token': token, 'username': username, 'password': 'incorrecta-123456'})
            self.assertEqual(response.status_code, 401)
            bodies.append(response.data)
        self.assertEqual(*bodies)

    def test_login_cookie_and_private_cache_headers(self):
        anonymous = self.client.get_cookie('rerimss_session')
        self.assertEqual(self.login().status_code, 302)
        cookie = self.client.get_cookie('rerimss_session')
        self.assertTrue(cookie.secure)
        self.assertTrue(cookie.http_only)
        self.assertEqual(cookie.same_site, 'Lax')
        self.assertNotEqual(anonymous, cookie)
        for path in ['/privado/', '/privado/informe']:
            response = self.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertIn('noindex', response.headers['X-Robots-Tag'])
        self.assertNotIn('ETag', response.headers)
        self.assertNotIn('Last-Modified', response.headers)
        response.close()

    def test_logout_revokes_copied_cookie(self):
        self.login()
        stolen = self.client.get_cookie('rerimss_session').value
        html = self.get('/privado/').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        self.assertEqual(self.client.post('/logout', base_url='https://localhost').status_code, 400)
        response = self.client.post('/logout', base_url='https://localhost', data={'csrf_token': token})
        self.assertEqual(response.status_code, 302)
        self.client.set_cookie('rerimss_session', stolen)
        self.assertEqual(self.get('/privado/informe').status_code, 302)

    def test_disabled_user_and_password_change_revoke_access(self):
        self.login()
        with patch.dict('os.environ', {'RERIMSS_STATE_DIR': str(self.state)}), patch('sys.argv', ['accounts', 'disable', 'colega']):
            accounts.main()
        self.assertEqual(self.get('/privado/informe').status_code, 302)
        with patch.dict('os.environ', {'RERIMSS_STATE_DIR': str(self.state)}), patch('sys.argv', ['accounts', 'enable', 'colega']):
            accounts.main()
        self.login()
        new_password = secrets.token_urlsafe(24)
        with patch.dict('os.environ', {'RERIMSS_STATE_DIR': str(self.state)}), patch('sys.argv', ['accounts', 'password', 'colega']), patch('app.accounts.getpass', side_effect=[new_password, new_password]):
            accounts.main()
        self.assertEqual(self.get('/privado/informe').status_code, 302)

    def test_expiration_and_idle_timeout(self):
        self.login()
        with database(self.state) as db:
            db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.get('/privado/informe').status_code, 302)
        self.login()
        with database(self.state) as db:
            db.execute('UPDATE sessions SET last_seen=?', (time.time() - 1900,))
        self.assertEqual(self.get('/privado/informe').status_code, 302)

    def test_rate_limit(self):
        token = self.csrf()
        for _ in range(5):
            response = self.client.post('/login', base_url='https://localhost', data={'csrf_token': token, 'username': 'colega', 'password': 'incorrecta-123456'})
            self.assertEqual(response.status_code, 401)
        response = self.client.post('/login', base_url='https://localhost', data={'csrf_token': token, 'username': 'colega', 'password': self.password})
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response.headers)

    def test_https_and_forwarded_header_trust(self):
        response = self.client.get('/login', base_url='http://localhost', headers={'X-Forwarded-Proto': 'https'})
        self.assertEqual(response.status_code, 308)
        self.assertTrue(response.location.startswith('https://'))
        self.assertEqual(self.client.get('/login', base_url='https://outside.invalid').status_code, 400)
        self.assertEqual(self.client.get('/healthz', base_url='http://localhost').status_code, 200)
