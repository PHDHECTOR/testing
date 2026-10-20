# Instalación institucional: Docker + Nginx

Esta guía es para el administrador del servidor. El paquete completo contiene un informe clínico identificable; no debe alojarse como archivos estáticos ni compartirse públicamente.

La instalación prepara un dominio con página pública en `/`, formulario en `/login` e informe privado en `/privado/`. No necesita R, Node.js, los Excel ni la base clínica en producción. Los visitantes solo necesitan su navegador.

## 1. Requisitos

- Servidor Linux x86_64 con Docker Engine y Docker Compose v2.
- Un subdominio cuyo DNS apunte al servidor.
- Puertos 80 y 443 disponibles para Nginx.
- Certificado institucional válido para ese subdominio: `fullchain.pem` y `privkey.pem`.
- Acceso para descargar las imágenes oficiales de Python y Nginx. Las dependencias Python ya están incluidas y verificadas; la construcción de la aplicación no descarga paquetes.
- Los navegadores de los visitantes deben poder cargar imágenes desde `https://a.basemaps.cartocdn.com` para ver el fondo CARTO Positron. Las áreas, puntos y controles permanecen disponibles si el fondo falla.

Si el servidor ya tiene Nginx atendiendo esos puertos, el administrador debe integrar el proxy en su configuración existente; no debe iniciar un segundo servicio que compita por ellos.

## 2. Preparar la carpeta

Extrae el ZIP confidencial y entra en la carpeta `RERIMSS`:

```bash
cd RERIMSS
cp .env.example .env
mkdir -p tls
```

Edita `.env` y cambia `RERIMSS_DOMAIN` por el subdominio real, sin `https://` ni rutas. `RERIMSS_BIND_IP=0.0.0.0`, puerto HTTP 80 y HTTPS 443 son los valores para el servicio institucional.

Copia el certificado y su clave a:

```text
tls/fullchain.pem
tls/privkey.pem
```

La clave permanece en el servidor y se monta en Nginx en modo de solo lectura. No se incluye en la imagen de la aplicación.

## 3. Construir e iniciar

```bash
docker build --network=none -t rerimss-web:local .
docker compose up -d
docker compose ps
```

Nginx espera a que la aplicación esté saludable. Si el certificado falta o no corresponde a las rutas configuradas, el servicio HTTPS no arrancará; no se sustituye por una publicación clínica sin HTTPS.

## 4. Crear cuentas para colegas

No existe un usuario o contraseña predeterminados. Crea una cuenta por persona:

```bash
docker compose exec app python -m app.accounts add colega1
```

La terminal solicita la contraseña sin mostrarla: debe tener entre 12 y 128 caracteres. No la escribas como parte del comando ni en `.env`. Entrega a cada colega únicamente su usuario, contraseña y el enlace privado por el canal institucional apropiado.

Otros comandos:

```bash
docker compose exec app python -m app.accounts list
docker compose exec app python -m app.accounts password colega1
docker compose exec app python -m app.accounts disable colega1
docker compose exec app python -m app.accounts enable colega1
```

Cambiar la contraseña o deshabilitar una cuenta invalida sus sesiones. La aplicación caduca la sesión tras 30 minutos de inactividad y después de ocho horas como máximo. Las cuentas, hashes de contraseña, sesiones y clave del portal se conservan en el volumen Docker `accounts`.

## 5. Verificar antes de compartir

- El enlace principal muestra la versión pública con tres mapas y periodos fijos.
- La dirección `/privado/` solicita una cuenta.
- La dirección `/privado/informe`, abierta sin sesión, redirige a `/login` y no descarga datos clínicos.
- Tras entrar con una cuenta autorizada se ven los tres mapas clínicos y sus controles anuales.
- Cerrar sesión impide volver a abrir el informe mediante su URL.
- El navegador acepta el certificado de la institución sin excepciones.

La pública y la privada se generan desde el mismo estudio, pero sus números pueden diferir: la pública suprime conteos menores de cinco y redondea el resto a múltiplos de cinco; sus tasas se calculan a partir de esos valores publicados.

## 6. Operación

```bash
docker compose logs --tail=100 app nginx
docker compose restart app
docker compose down
```

`down` detiene el servicio y conserva las cuentas. **No añadas `--volumes`** en producción si necesitas mantenerlas. Las actualizaciones deben conservar el volumen y la carpeta de certificados.

Para renovar el certificado, reemplaza los archivos en `tls/` siguiendo el procedimiento institucional y recarga Nginx:

```bash
docker compose exec nginx nginx -s reload
```

Para actualizar los informes, regenera ambas versiones desde el repositorio de desarrollo, reemplaza `dist/public/index.html` y `dist/private/index.html`, y ejecuta:

```bash
docker compose build app
docker compose up -d
```

## Contenido de la entrega

- `dist/public/index.html`: archivo público autocontenido.
- `dist/private/index.html`: resultado clínico que la aplicación sirve únicamente tras autenticar.
- `app/`: inicio de sesión, gestión de sesiones y rutas.
- `compose.yaml`, `Dockerfile`, `deploy/nginx.conf.template`: instalación probada.
- `vendor/wheels/`: dependencias de producción con versiones y hashes SHA-256 verificados contra PyPI.
- `.env.example`: configuración sin credenciales.

No se incluyen cuentas reales, contraseñas, claves TLS, SQLite clínica ni los Excel. Los datos clínicos necesarios para la versión privada sí están incorporados en su HTML.
