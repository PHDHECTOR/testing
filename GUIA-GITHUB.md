# Publicar la versión pública en GitHub

GitHub guarda el código del proyecto. GitHub Pages puede mostrar la versión pública mediante un enlace HTTPS. La versión clínica necesita el servidor institucional con Docker, Nginx y cuentas; Pages no ejecuta esa aplicación.

## Primera publicación

Una vez subidos los cambios al repositorio `PHDHECTOR/testing`:

1. Abre [Settings → Pages](https://github.com/PHDHECTOR/testing/settings/pages).
2. En **Build and deployment → Source**, elige **GitHub Actions**.
3. Abre [Actions](https://github.com/PHDHECTOR/testing/actions), selecciona **Publicar RERIMSS público** y pulsa **Run workflow** sobre `master`. Si el primer intento ocurrió antes de activar Pages, vuelve a ejecutarlo.
4. Espera a que termine correctamente. Abre el enlace que aparece en el despliegue `github-pages`; ese es el que puedes compartir con colegas.

Comprueba que se muestran los tres mapas con CARTO, que puedes acercarlos y abrir los resultados de un AGEB, y que cambiar un periodo no altera los otros mapas. El sitio público no ofrece el informe clínico ni cuentas de acceso.

La activación inicial necesita permisos de administración/Pages del repositorio. El workflow utiliza el token temporal de GitHub Actions para las siguientes publicaciones y no requiere guardar un token personal en el código.

## Actualizar resultados

En el entorno autorizado que contiene los archivos originales:

```bash
npm run build
npm test
python3 scripts/publish_public.py
python3 scripts/publish_public.py --check
git add docs
git commit -m "Actualizar resultados públicos RERIMSS"
git push origin HEAD:master
```

El workflow despliega exclusivamente la carpeta `docs/`, con HTML público agregado, licencia de Leaflet y manifiesto SHA-256. No necesita recibir la base clínica para publicar. La versión pública suprime conteos menores de cinco y redondea el resto; sus resultados no son los valores clínicos exactos.

## Datos privados

El repositorio contiene la lógica de autenticación y el Rmd fuente, pero no contiene el HTML clínico compilado, la base SQLite, los Excel ni los certificados. Tampoco se publica la imagen Docker con el informe clínico en un registro público. El paquete confidencial se entrega al administrador por el canal institucional y se instala siguiendo [GUIA-SERVIDOR.md](GUIA-SERVIDOR.md).

## Si CARTO aparece bloqueado

La red del navegador debe permitir `https://a.basemaps.cartocdn.com`. El portal ya permite ese dominio en su política de imágenes. Los polígonos y sus resultados funcionan aunque falle el fondo. La atribución legal a OpenStreetMap aparece porque CARTO utiliza sus datos; las teselas se solicitan a CARTO.

Para administrar y verificar Pages desde este entorno de desarrollo también se necesita acceso a `api.github.com` y al dominio público que GitHub asigne. Una configuración de red guardada no se aplica hasta que se guarde/active mediante los ajustes del entorno.
