import argparse
from . import create_app


def main():
    parser = argparse.ArgumentParser(description='Desarrollo local de RERIMSS; para compartir usa HTTPS en el servidor institucional.')
    parser.add_argument('--port', type=int, default=4173)
    args = parser.parse_args()
    app = create_app({'ALLOW_HTTP_LOCAL': True, 'SESSION_COOKIE_SECURE': False})
    app.run(host='127.0.0.1', port=args.port, debug=False)


if __name__ == '__main__':
    main()
