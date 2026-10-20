"""Credenciales y sesiones del portal; no almacena la base clínica."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import os
import secrets
import sqlite3
import tempfile


def initialize(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    secret = directory / 'secret.key'
    if not secret.exists():
        descriptor, name = tempfile.mkstemp(dir=directory, prefix='.secret-')
        try:
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(secrets.token_bytes(32))
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(name, secret)
            except FileExistsError:
                pass
        finally:
            os.unlink(name)
    key = secret.read_bytes()
    if len(key) < 32:
        raise RuntimeError('La clave del portal es inválida; revisa el directorio de estado.')
    with database(directory) as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                created REAL NOT NULL,
                last_seen REAL NOT NULL,
                expires REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attempts (
                fingerprint TEXT NOT NULL,
                created REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS attempts_lookup ON attempts(fingerprint, created);
        ''')
    os.chmod(directory / 'access.sqlite', 0o600)
    os.chmod(secret, 0o600)
    return key


@contextmanager
def database(directory):
    connection = sqlite3.connect(Path(directory) / 'access.sqlite', timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()
