"""Administración local de colegas. Las contraseñas se solicitan sin eco."""
from getpass import getpass
from pathlib import Path
import argparse
import os
import re
import sqlite3

from werkzeug.security import generate_password_hash
from .store import database, initialize


def main():
    parser = argparse.ArgumentParser(description='Administrar cuentas de la versión privada de RERIMSS.')
    parser.add_argument('action', choices=['add', 'password', 'disable', 'enable', 'list'])
    parser.add_argument('username', nargs='?')
    args = parser.parse_args()
    if args.action != 'list' and (not args.username or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]{2,79}', args.username)):
        parser.error('Indica un usuario de 3 a 80 caracteres: letras, números, punto, @, guion o guion bajo.')
    directory = Path(os.environ.get('RERIMSS_STATE_DIR', Path(__file__).resolve().parents[1] / '.state'))
    os.umask(0o077)
    initialize(directory)
    username = args.username.casefold() if args.username else None
    password_hash = None
    if args.action in ('add', 'password'):
        first = getpass('Contraseña nueva (12–128 caracteres): ')
        second = getpass('Repite la contraseña: ')
        if first != second or not 12 <= len(first) <= 128:
            parser.error('Las contraseñas deben coincidir y tener entre 12 y 128 caracteres.')
        password_hash = generate_password_hash(first, method='scrypt')
    with database(directory) as db:
        if args.action == 'list':
            for row in db.execute('SELECT username,enabled FROM users ORDER BY username'):
                print(row['username'], 'habilitado' if row['enabled'] else 'deshabilitado')
            return
        if args.action == 'add':
            try:
                db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)', (username, password_hash))
            except sqlite3.IntegrityError:
                parser.error('El usuario ya existe.')
        else:
            row = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
            if not row:
                parser.error('El usuario no existe.')
            if args.action == 'password':
                db.execute('UPDATE users SET password_hash=? WHERE id=?', (password_hash, row['id']))
            else:
                db.execute('UPDATE users SET enabled=? WHERE id=?', (int(args.action == 'enable'), row['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?', (row['id'],))
    print('Cuenta actualizada. Las credenciales no se han enviado ni publicado.')


if __name__ == '__main__':
    main()
