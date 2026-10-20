"""Prueba Docker + Nginx + HTTPS en un proyecto temporal, sin publicar puertos externos."""
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, HTTPSHandler, Request, build_opener
import hashlib
import json
import os
import re
import secrets
import ssl
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def main():
    environment = os.environ.copy()
    environment['DOCKER_CONFIG'] = str(ROOT / '.tools/docker')
    project = 'rerimss-check-' + secrets.token_hex(4)
    command = ['docker', 'compose', '--project-name', project]
    (ROOT / 'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='tls-check-', dir=ROOT/'build') as temporary:
        tls = Path(temporary)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2', '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost', '-keyout', str(tls/'privkey.pem'), '-out', str(tls/'fullchain.pem')], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        environment.update(RERIMSS_DOMAIN='localhost', RERIMSS_BIND_IP='127.0.0.1', RERIMSS_HTTP_PORT='0', RERIMSS_HTTPS_PORT='0', RERIMSS_TLS_DIR=str(tls))
        def compose(arguments, **kwargs):
            return subprocess.run(command+arguments, env=environment, cwd=ROOT, check=True, capture_output=True, **kwargs)
        try:
            compose(['up', '-d', '--no-build', '--wait', '--wait-timeout', '90'])
            port = int(compose(['port', 'nginx', '443']).stdout.decode().strip().rsplit(':', 1)[1])
            http_port = int(compose(['port', 'nginx', '80']).stdout.decode().strip().rsplit(':', 1)[1])
            base = f'https://localhost:{port}'
            context = ssl.create_default_context(cafile=str(tls/'fullchain.pem'))
            jar = CookieJar()
            opener = build_opener(HTTPSHandler(context=context), HTTPCookieProcessor(jar), NoRedirect())
            def request(path, form=None, url=None):
                data = urlencode(form).encode() if form is not None else None
                req = Request(url or base+path, data=data)
                try:
                    response = opener.open(req, timeout=30)
                except HTTPError as error:
                    response = error
                with response:
                    return response.status, response.read(), response.headers
            # A Nginx le puede faltar una fracción de segundo tras crear el contenedor.
            for attempt in range(10):
                try:
                    status, public, _ = request('/')
                    break
                except OSError:
                    if attempt == 9: raise
                    time.sleep(.3)
            assert status == 200, 'No se abrió la versión pública con HTTPS.'
            assert request('/privado/informe')[0] == 302, 'La versión privada fue accesible sin cuenta.'
            assert request('/dist/private/index.html')[0] == 404, 'Se encontró una ruta alternativa al archivo privado.'
            assert request('/', url=f'http://localhost:{http_port}/')[0] == 308, 'No se redirigió HTTP a HTTPS.'
            _, public_download, _ = request('/publico.html')
            assert hashlib.sha256(public_download).digest() == hashlib.sha256((ROOT/'dist/public/index.html').read_bytes()).digest()
            password = secrets.token_urlsafe(24)
            setup = "import json,sys; from pathlib import Path; from app.store import database; from werkzeug.security import generate_password_hash; value=json.load(sys.stdin); dbctx=database(Path('/data')); db=dbctx.__enter__(); db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)',('colega_validacion',generate_password_hash(value['password']))); dbctx.__exit__(None,None,None)"
            compose(['exec', '-T', 'app', 'python', '-c', setup], input=json.dumps({'password':password}).encode())
            status, login, _ = request('/login')
            assert status == 200
            csrf = re.search(r'name="csrf_token" value="([^"]+)"', login.decode()).group(1)
            status, _, headers = request('/login', {'csrf_token':csrf, 'username':'colega_validacion', 'password':password})
            assert status == 302, 'El inicio de sesión no funcionó tras Nginx.'
            cookies = headers.get('Set-Cookie', '')
            assert 'Secure' in cookies and 'HttpOnly' in cookies and 'SameSite=Lax' in cookies
            status, wrapper, _ = request('/privado/')
            assert status == 200
            status, report, headers = request('/privado/informe')
            assert status == 200 and 'no-store' in headers['Cache-Control']
            assert hashlib.sha256(report).digest() == hashlib.sha256((ROOT/'dist/private/index.html').read_bytes()).digest()
            csrf = re.search(r'name="csrf_token" value="([^"]+)"', wrapper.decode()).group(1)
            assert request('/logout', {'csrf_token':csrf})[0] == 302
            assert request('/privado/informe')[0] == 302
            results = dict(docker_nginx_https=True, certificate_verification=True, public_access=True, authenticated_private_access=True, private_unauthorized_blocked=True, private_alternate_path_blocked=True, secure_cookie=True, logout_revokes_access=True, http_to_https=True)
            (ROOT/'build/deployment-validation.json').write_text(json.dumps(results, indent=2))
            print('Docker + Nginx + HTTPS verificados: pública, login, cookies seguras, informe privado y cierre de sesión.')
            print('La verificación TLS se mantuvo activa usando una CA de prueba confiada explícitamente.')
        finally:
            compose(['down', '--volumes', '--remove-orphans'])


if __name__ == '__main__':
    main()
