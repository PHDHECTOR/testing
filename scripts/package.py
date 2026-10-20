"""Entregas separadas: archivo público y aplicación confidencial para el administrador."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    public = ROOT / 'dist/public/index.html'
    private = ROOT / 'dist/private/index.html'
    if not public.exists() or not private.exists():
        raise SystemExit('Primero ejecuta npm run build.')
    tests = (ROOT / 'build/dual-tests-final.log').read_text()
    if not re.search(r'Ran 21 tests', tests) or '\nOK\n' not in tests:
        raise SystemExit('No se encontró la verificación de las 21 pruebas.')
    tested_inputs = [public, private, *list((ROOT/'app').rglob('*.py')), *list((ROOT/'app/templates').glob('*.html'))]
    if (ROOT/'build/dual-tests-final.log').stat().st_mtime < max(path.stat().st_mtime for path in tested_inputs):
        raise SystemExit('Las pruebas son anteriores a los informes o al servidor. Ejecuta npm test.')
    deployment = json.loads((ROOT/'build/deployment-validation.json').read_text())
    if not deployment or not all(deployment.values()):
        raise SystemExit('Falta verificar Docker + Nginx + HTTPS.')
    deployed_inputs = [*tested_inputs, ROOT/'Dockerfile', ROOT/'compose.yaml', ROOT/'deploy/nginx.conf.template']
    if (ROOT/'build/deployment-validation.json').stat().st_mtime < max(path.stat().st_mtime for path in deployed_inputs):
        raise SystemExit('La verificación de Docker es anterior a la entrega. Ejecuta scripts/check_deployment.py.')
    lock = ROOT/'vendor/wheels/requirements.lock'
    expected = set(re.findall(r'--hash=sha256:([0-9a-f]{64})', lock.read_text()))
    wheels = [path for path in lock.parent.glob('*.whl') if digest(path) in expected]
    if {digest(path) for path in wheels} != expected:
        raise SystemExit('Faltan paquetes verificados para construir Docker.')
    metadata = {
        'generated_at':datetime.now(ZoneInfo('America/Mexico_City')).isoformat(),
        'census_file':'RESAGEBURB_01CSV20_AGS(2).xlsx',
        'public_sha256':digest(public), 'private_sha256':digest(private),
        'tests_passed':21, 'public_cells_checked':15807,
        'docker_nginx_https_verified':True,
        'institutional_deployment':'pending_domain_certificate_and_administrator',
    }
    (ROOT/'build/RELEASE.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False))
    public_note = '''RERIMSS · Versión pública

index.html contiene tres mapas y resultados agregados por AGEB.
Puede compartirse como archivo o publicarse en un alojamiento estático.
Se suprimen los conteos menores de cinco (incluido cero) y se redondean
los demás a múltiplos de cinco. Las tasas usan esos conteos publicados.
Los periodos son bloques fijos, con extremos recortados al rango disponible.

No contiene puntos, CURP, nombres, domicilios ni trayectorias individuales.
No incluye el informe privado ni el servidor de autenticación.
Los polígonos y los recursos necesarios están incorporados en el HTML.
El fondo utiliza CARTO Positron y requiere acceso a a.basemaps.cartocdn.com.
Los polígonos y resultados siguen disponibles si ese fondo no carga.

El nuevo Excel censal cubre los 479 AGEB del shapefile; 478 tienen población
positiva y permiten usar su denominador. Los resultados son descriptivos.
La supresión y el redondeo reducen detalle, sin garantizar formalmente
la imposibilidad de toda inferencia estadística.
'''
    validation = '''# Validación de RERIMSS

- Nuevo Excel censal: 479 AGEB asociados; 478 con población positiva.
- 21 pruebas aprobadas: acceso, sesiones, cálculos, privacidad y navegador.
- Las 15,807 celdas públicas fueron cotejadas con una referencia independiente de los datos clínicos: supresión, redondeo y tasas aproximadas.
- HTML público revisado: sin identificadores ni nombres de pacientes, sin puntos ni trayectorias individuales.
- Mapas CARTO con zoom, ventanas y controles temporales verificados mediante teselas simuladas; el acceso real a CARTO depende de la red del visitante.
- Docker + Nginx + HTTPS probados con validación de certificado activa, acceso público, bloqueo anónimo del informe privado, inicio y cierre de sesión.
- La instalación institucional queda pendiente del dominio, certificado y administrador del servidor.

La verificación técnica no sustituye la evaluación epidemiológica de los métodos ni una evaluación formal de riesgo de inferencia estadística.
'''
    (ROOT/'build/VALIDACION-DOS-VERSIONES.md').write_text(validation)
    license_file = ROOT/'node_modules/leaflet/LICENSE'
    public_zip = ROOT/'build/RERIMSS-publico.zip'
    with zipfile.ZipFile(public_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        bundle.write(public,'index.html')
        bundle.write(license_file,'LEAFLET-LICENSE.txt')
        bundle.writestr('LEEME.txt',public_note)
        bundle.writestr('VALIDACION.md',validation)
    deploy_zip = ROOT/'build/RERIMSS-aplicacion-PRIVADA.zip'
    files = [ROOT/name for name in ['Dockerfile','compose.yaml','.dockerignore','.env.example','requirements.txt','GUIA-SERVIDOR.md','GUIA-COMPARTIR.md','deploy/nginx.conf.template']]
    files += [path for path in (ROOT/'app').rglob('*') if path.is_file() and path.suffix in ('.py','.html') and '__pycache__' not in path.parts]
    files += [public,private,lock,*wheels]
    with zipfile.ZipFile(deploy_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        for path in files:
            bundle.write(path,'RERIMSS/'+path.relative_to(ROOT).as_posix())
        bundle.write(license_file,'RERIMSS/LEAFLET-LICENSE.txt')
        bundle.write(ROOT/'build/RELEASE.json','RERIMSS/RELEASE.json')
        bundle.writestr('RERIMSS/VALIDACION.md',validation)
    with zipfile.ZipFile(public_zip) as bundle:
        assert set(bundle.namelist()) == {'index.html','LEAFLET-LICENSE.txt','LEEME.txt','VALIDACION.md'}
        assert hashlib.sha256(bundle.read('index.html')).hexdigest() == metadata['public_sha256']
        assert bundle.testzip() is None
    with zipfile.ZipFile(deploy_zip) as bundle:
        assert not any(name.endswith(('.db','.sqlite','.xlsx','.pem','.key')) for name in bundle.namelist())
        assert not any('/.state/' in name for name in bundle.namelist())
        assert hashlib.sha256(bundle.read('RERIMSS/dist/private/index.html')).hexdigest() == metadata['private_sha256']
        assert bundle.testzip() is None
    for path in [public_zip,deploy_zip]:
        print(path.name, path.stat().st_size,'bytes; SHA-256',digest(path))


if __name__ == '__main__':
    main()
