from datetime import timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import hmac
import os
import secrets
import time

from flask import Flask, Response, abort, g, redirect, render_template, request, send_file, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from .store import database, initialize, token_hash

ROOT = Path(__file__).resolve().parents[1]


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        REPORTS_DIR=Path(os.environ.get('RERIMSS_REPORTS_DIR', ROOT / 'dist')),
        STATE_DIR=Path(os.environ.get('RERIMSS_STATE_DIR', ROOT / '.state')),
        ALLOW_HTTP_LOCAL=False,
        SESSION_COOKIE_NAME='rerimss_session',
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=16 * 1024,
        TRUSTED_HOSTS=['localhost', '127.0.0.1', '[::1]'] + [x.strip() for x in os.environ.get('RERIMSS_HOSTS', '').split(',') if x.strip()],
        PROXY_HOPS=int(os.environ.get('RERIMSS_PROXY_HOPS', '0')),
        IDLE_SECONDS=30 * 60,
        SESSION_SECONDS=8 * 60 * 60,
        RATE_WINDOW=15 * 60,
        RATE_LIMIT=5,
        IP_RATE_LIMIT=30,
    )
    if config:
        app.config.update(config)
    app.config['REPORTS_DIR'] = Path(app.config['REPORTS_DIR'])
    app.config['STATE_DIR'] = Path(app.config['STATE_DIR'])
    os.umask(0o077)
    app.secret_key = initialize(app.config['STATE_DIR'])
    for variant in ('public', 'private'):
        if not (app.config['REPORTS_DIR'] / variant / 'index.html').is_file():
            raise RuntimeError('Faltan informes compilados; ejecuta npm run build.')
    hops = app.config['PROXY_HOPS']
    if hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops)
    dummy_hash = generate_password_hash(secrets.token_urlsafe(24), method='scrypt')

    def csrf_token():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        return session['csrf']

    def validate_csrf():
        supplied = request.form.get('csrf_token', '')
        expected = session.get('csrf', '')
        if not expected or not supplied or not hmac.compare_digest(supplied, expected):
            abort(400, description='La sesión del formulario cambió. Recarga la página e inténtalo de nuevo.')

    def current_user():
        if hasattr(g, 'user'):
            return g.user
        g.user = None
        token = session.get('sid')
        if not isinstance(token, str):
            return None
        now = time.time()
        with database(app.config['STATE_DIR']) as db:
            row = db.execute('''SELECT users.id, users.username, users.enabled,
                sessions.last_seen, sessions.expires
                FROM sessions JOIN users ON users.id=sessions.user_id
                WHERE sessions.token_hash=?''', (token_hash(token),)).fetchone()
            if not row or not row['enabled'] or row['expires'] <= now or row['last_seen'] + app.config['IDLE_SECONDS'] <= now:
                db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(token),))
                session.clear()
                return None
            db.execute('UPDATE sessions SET last_seen=? WHERE token_hash=?', (now, token_hash(token)))
            g.user = {'id': row['id'], 'username': row['username']}
        return g.user

    def protected(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user():
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    @app.before_request
    def require_https():
        if request.path == '/healthz':
            return None
        local = app.config['ALLOW_HTTP_LOCAL'] and request.remote_addr in ('127.0.0.1', '::1')
        if not request.is_secure and not local:
            # Host validado por TRUSTED_HOSTS; no se confía en cabeceras de proxy
            # salvo que el administrador configure explícitamente PROXY_HOPS.
            return redirect(request.url.replace('http://', 'https://', 1), code=308)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), microphone=()'
        scripts = "'self' 'unsafe-inline'"
        if request.endpoint == 'private_report':
            scripts += " 'unsafe-eval'"  # htmlwidgets de R ejecuta sus funciones serializadas.
        response.headers['Content-Security-Policy'] = f"default-src 'self' data: blob:; script-src {scripts} data:; style-src 'self' 'unsafe-inline' data:; img-src 'self' data: blob: https://a.basemaps.cartocdn.com; font-src 'self' data:; connect-src 'none'; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'; object-src 'none'"
        if request.path.startswith(('/login', '/logout', '/privado')):
            response.headers['Cache-Control'] = 'no-store, private, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.context_processor
    def template_helpers():
        return {'csrf_token': csrf_token}

    @app.get('/')
    def public_report():
        html = (app.config['REPORTS_DIR'] / 'public/index.html').read_text(encoding='utf-8')
        link = '<a class="private-access" href="/privado/">Acceso para colegas <span aria-hidden="true">↗</span></a>'
        response = Response(html.replace('<!--PRIVATE_ACCESS-->', link), mimetype='text/html')
        response.headers['Cache-Control'] = 'public, max-age=60'
        return response

    @app.get('/publico.html')
    def download_public():
        return send_file(app.config['REPORTS_DIR'] / 'public/index.html', as_attachment=True, download_name='RERIMSS-publico.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user():
            return redirect(url_for('private_home'))
        error = None
        status = 200
        if request.method == 'POST':
            validate_csrf()
            username = request.form.get('username', '').strip().casefold()
            password = request.form.get('password', '')
            now = time.time()
            ip = request.remote_addr or 'unknown'
            fingerprint = hmac.new(app.secret_key, (ip + '\0' + username).encode(), hashlib.sha256).hexdigest()
            ip_key = hmac.new(app.secret_key, ('ip\0' + ip).encode(), hashlib.sha256).hexdigest()
            with database(app.config['STATE_DIR']) as db:
                db.execute('DELETE FROM attempts WHERE created < ?', (now - app.config['RATE_WINDOW'],))
                count = db.execute('SELECT COUNT(*) FROM attempts WHERE fingerprint=?', (fingerprint,)).fetchone()[0]
                ip_count = db.execute('SELECT COUNT(*) FROM attempts WHERE fingerprint=?', (ip_key,)).fetchone()[0]
                if count >= app.config['RATE_LIMIT'] or ip_count >= app.config['IP_RATE_LIMIT']:
                    response = app.make_response((render_template('login.html', error='Demasiados intentos. Espera 15 minutos y vuelve a intentarlo.'), 429))
                    response.headers['Retry-After'] = str(app.config['RATE_WINDOW'])
                    return response
                row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
                valid = check_password_hash(row['password_hash'] if row else dummy_hash, password[:128])
                if row and row['enabled'] and valid and 12 <= len(password) <= 128:
                    previous = session.get('sid')
                    if isinstance(previous, str):
                        db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(previous),))
                    token = secrets.token_urlsafe(32)
                    db.execute('DELETE FROM sessions WHERE expires <= ?', (now,))
                    db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)', (token_hash(token), row['id'], now, now, now + app.config['SESSION_SECONDS']))
                    db.execute('DELETE FROM attempts WHERE fingerprint=?', (fingerprint,))
                    session.clear()
                    session.permanent = True
                    session['sid'] = token
                    session['csrf'] = secrets.token_urlsafe(32)
                    return redirect(url_for('private_home'))
                db.executemany('INSERT INTO attempts VALUES (?,?)', [(fingerprint, now), (ip_key, now)])
                error, status = 'Usuario o contraseña incorrectos.', 401
        return render_template('login.html', error=error), status

    @app.post('/logout')
    @protected
    def logout():
        validate_csrf()
        with database(app.config['STATE_DIR']) as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(session['sid']),))
        session.clear()
        return redirect(url_for('public_report'))

    @app.get('/privado/')
    @protected
    def private_home():
        return render_template('private.html', user=g.user)

    @app.get('/privado/informe')
    @protected
    def private_report():
        response = send_file(app.config['REPORTS_DIR'] / 'private/index.html', conditional=False, etag=False)
        response.headers.pop('Last-Modified', None)
        return response

    @app.get('/healthz')
    def health():
        return {'status': 'ok'}

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        return render_template('error.html', status=error.code), error.code

    return app
