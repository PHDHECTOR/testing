# RERIMSS · Aplicación pública y privada

Aplicación en español para compartir los resultados del estudio renal por AGEB. Usa el **nuevo Excel censal** y conserva el R Markdown original, los Excel, SQLite y el shapefile sin modificarlos.

- **Pública:** tres mapas con polígonos, periodos fijos, tabla, CSV y resultados agregados.
- **Privada:** el informe clínico completo del R Markdown, con puntos y controles anuales, detrás de cuentas individuales.
- **Mapa base:** CARTO Positron, con zoom, desplazamiento, ventanas por AGEB y controles temporales independientes.
- **Alojamiento público:** carpeta `docs/` y despliegue preparado para GitHub Pages. Consulta [GUIA-GITHUB.md](GUIA-GITHUB.md) para activarlo y comprobar su estado.
- **Alojamiento privado:** Docker + Nginx con HTTPS en el servidor institucional; su instalación sigue pendiente.

Para compartirla o solicitar la instalación, empieza por [GUIA-COMPARTIR.md](GUIA-COMPARTIR.md). Los comandos del administrador están en [GUIA-SERVIDOR.md](GUIA-SERVIDOR.md).

## Preparar el entorno de desarrollo

```bash
cd /workspace/testing
npm ci
npm run setup:r
npm run setup:app
npm run build
npm test
npm run dev
```

El portal local utiliza el puerto 4173 y solo escucha en 127.0.0.1. `npm run dev -- --port 4176` cambia el puerto. Es un servidor de desarrollo; para colegas utiliza Docker + Nginx con HTTPS.

Cada tarea en la nube ya está aislada. Usa el checkout existente; no crees un Git worktree salvo petición explícita.

## Entradas y salidas

Los insumos están en `/workspace/inputs/prueba_codex`. El proyecto utiliza:

- `RERIMSS(4).db`: tablas clínicas `registros` y `terapias_sustitutivas`.
- `renales_31082026.xlsx`: geolocalizaciones.
- **`RESAGEBURB_01CSV20_AGS(2).xlsx`**: nuevo censo, elegido en `config/project.json`.
- `2020_1_01_A (1)/2020_1_01_A.shp` y sus archivos auxiliares.

La copia exacta del documento recibido está en `report/rerimss/informe.Rmd`. Los ajustes de presentación se aplican a una copia en `build/`, no a la fuente original.

`RERIMSS_INPUT_DIR`, `RERIMSS_DB_PATH` y `RERIMSS_CENSO_PATH` permiten cambiar las rutas sin renombrar los originales.

```text
dist/public/index.html     # Único informe que puede compartirse como archivo público
dist/private/index.html    # Informe clínico; solo lo sirve una ruta autenticada
build/validation.json      # Verificación de cálculos privados; no se publica
build/public-payload.json  # Solo resultados agregados autorizados
```

Los datos de entrada y la base clínica no se incluyen en Docker ni en el paquete de instalación. El informe privado incorpora datos clínicos individuales: el paquete completo debe entregarse únicamente al administrador autorizado.

## Qué publica la versión pública

La publicación se genera en `r/publication.R` desde las mismas personas y definiciones clínicas utilizadas por el R Markdown:

1. Se agrupan los resultados por AGEB y periodos fijos de cinco años; el primer y último intervalo se recortan al rango disponible.
2. Los conteos menores de cinco, **incluido cero**, se suprimen; su conteo y tasa se serializan como `null`.
3. Los demás conteos se redondean al múltiplo de cinco más próximo.
4. Las tasas se calculan con el conteo ya redondeado y la población del Censo 2020.
5. Solo se envían polígonos censales con atributos geográficos permitidos y esas celdas publicables.

No se envían puntos de pacientes, CURP, nombres, domicilios, identificadores seudónimos, fechas individuales ni trayectorias. No se utiliza el parámetro `public_mode` del archivo original como garantía de anonimización. Los totales visibles suman únicamente celdas publicadas y no representan los totales clínicos exactos.

Esta reducción de detalle no equivale a una garantía formal frente a toda inferencia estadística. No compares estos valores aproximados con los valores exactos de la versión privada como si fueran iguales.

## Acceso a la versión privada

El portal usa Flask y contraseñas derivadas mediante scrypt, sesiones almacenadas en el servidor, cookies Secure/HttpOnly/SameSite, validación CSRF, limitación de intentos y caducidad por inactividad. Cambiar la contraseña o deshabilitar una cuenta revoca sus sesiones; cerrar sesión invalida incluso una copia de la cookie anterior.

La aplicación no tiene credenciales predeterminadas. En desarrollo puedes crear una cuenta, sin escribir contraseñas en argumentos:

```bash
.app-runtime/bin/python -m app.accounts add colega1
```

Los comandos `password`, `disable`, `enable` y `list` administran las cuentas. El estado local está en `.state/`, fuera de Git; en Docker se conserva en un volumen. Las contraseñas se introducen sin eco en la terminal.

Las rutas privadas no admiten caché y no son archivos de una carpeta pública. El servidor no expone el árbol del proyecto ni los archivos de entrada.

## Compilar y distribuir

```bash
npm run build
npm test
npm run vendor
npm run package
```

`npm run vendor` descarga las dependencias Python de producción y comprueba sus SHA-256 contra PyPI. Genera un archivo con versiones y hashes para que Docker instale los paquetes sin acceder a PyPI durante la construcción. Las dependencias incluidas corresponden a Linux x86_64 y Python 3.12; para otra arquitectura hay que preparar ruedas compatibles.

La salida consta de `build/RERIMSS-publico.zip` y `build/RERIMSS-aplicacion-PRIVADA.zip`. El segundo incluye ambas versiones, el servidor, Docker y Nginx; **no debe subirse como una carpeta de archivos estáticos**.

## Verificación

`npm test` ejecuta 21 pruebas que cubren acceso anónimo, CSRF, errores genéricos de login, cookies, revocación, caducidad, limitación de intentos, ausencia de identificadores en el HTML público, las 15,807 celdas públicas, filtros, CSV, mapas, teclado y móvil.

```bash
docker build --network=none -t rerimss-web:local .
.app-runtime/bin/python scripts/check_deployment.py
```

La prueba de despliegue levanta un proyecto temporal de Docker + Nginx, con HTTPS y un certificado de prueba confiado explícitamente. Mantiene activa la verificación TLS; comprueba la versión pública, el bloqueo anónimo de la privada, el inicio y cierre de sesión y las cookies seguras. Solo abre puertos locales y elimina su propio proyecto y volumen al terminar. Ese certificado de prueba no forma parte de la entrega ni debe utilizarse en la institución.

El navegador administrado bloquea `file://`, por lo que los informes se verifican mediante HTTP/HTTPS. Las pruebas simulan las imágenes de CARTO y bloquean otros servicios externos; comprueban el zoom, las ventanas y que las áreas sigan disponibles cuando CARTO falla. Esto verifica la integración, no el acceso real al proveedor desde una red institucional.

## Publicar en GitHub

El repositorio puede contener el código de ambas versiones. **Solo `docs/` se despliega en Pages**; no se suben el informe clínico compilado, las bases, los Excel, cuentas, certificados ni el ZIP confidencial. GitHub Pages sirve archivos estáticos y no ejecuta Flask, Docker ni el inicio de sesión privado.

Después de regenerar los informes y verificar las pruebas, actualiza la carpeta pública:

```bash
python3 scripts/publish_public.py
python3 scripts/publish_public.py --check
```

El workflow `.github/workflows/pages.yml` valida y sube exclusivamente `docs/` al actualizar `master`. No compila R ni necesita los archivos clínicos en GitHub. Pages debe estar activado con **Settings → Pages → Source: GitHub Actions**. La URL real aparece cuando el despliegue termina; tener el código en GitHub no confirma que el sitio esté publicado.

## Cobertura de los insumos

El nuevo censo cubre los **479 AGEB**; **478** tienen población positiva y uno tiene población cero. Se conservan 707 filas sin coordenadas válidas y 488 personas fuera de AGEB, conforme a las reglas de lectura y asignación del informe original. Las tasas de AGEB sin denominador positivo no se calculan. Los puntos fuera de AGEB solo aparecen en la versión clínica y no se añaden a los numeradores de los polígonos.

Ambas versiones utilizan CARTO Positron desde `https://a.basemaps.cartocdn.com`. La política CSP de Flask permite ese origen para imágenes; no solicita teselas a `tile.openstreetmap.org`. Se conserva la atribución a OpenStreetMap porque CARTO usa sus datos cartográficos. La red de los visitantes debe permitir el dominio de CARTO. Si no está disponible, los polígonos y los controles siguen funcionando; la pública muestra un aviso. Para generar la privada sin fondo externo, utiliza `RERIMSS_BASEMAP=none npm run build`.
