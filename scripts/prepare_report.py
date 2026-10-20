"""Adaptaciones de presentación; el .Rmd original permanece intacto."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'report/rerimss/informe.Rmd'
    text = source.read_text(encoding='utf-8')
    # Cambiar el proveedor en la copia web; conservar el Rmd recibido intacto.
    basemap = '''# Mapa base CARTO Positron; las capas del estudio son independientes.
CARTO_TILE_URL <- "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
CARTO_ATTRIBUTION <- paste0(
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
  ' &copy; <a href="https://carto.com/attributions">CARTO</a>'
)

add_rerimss_basemap <- function(map, group = "CARTO Positron") {
  mode <- tolower(trimws(params$basemap_mode))
  if (identical(mode, "none")) return(map)
  if (!identical(mode, "carto")) stop("El mapa base debe ser carto o none.")
  map %>% leaflet::addTiles(
    urlTemplate = CARTO_TILE_URL, group = group, attribution = CARTO_ATTRIBUTION,
    options = leaflet::tileOptions(minZoom = 1, maxZoom = 20, noWrap = TRUE,
                                   referrerPolicy = "no-referrer")
  )
}
'''
    text, count = re.subn(
        r'# Mapa base compatible con publicación web sin API key\..*?\n}\n(?=\n```)',
        lambda _: basemap, text, flags=re.DOTALL)
    if count != 1:
        raise ValueError('Cambió la función del mapa base; revisa el adaptador CARTO.')
    text = text.replace('basemap_mode: "osm"', 'basemap_mode: "carto"')
    text = text.replace('# Mapa base. "osm" usa OpenStreetMap; "none" evita teselas externas.',
                        '# Mapa base. "carto" usa CARTO Positron; "none" evita teselas externas.')
    # Cada mapa traía dos spans con el mismo ID; solo se actualizaba el primero.
    for prefix in ('rerimss-total', 'rerimss-incidence', 'rerimss-active'):
        old = f'<span id="{prefix}-max">'
        if text.count(old) != 1:
            raise ValueError(f'Cambió la estructura del resumen {prefix}; revisa el adaptador.')
        text = text.replace(old, f'<span id="{prefix}-max-summary">')
    old = 'if (maxEl) maxEl.textContent = fmt(maxRate, 1);'
    if text.count(old) != 1:
        raise ValueError('No se encontró la actualización de la tasa máxima.')
    text = text.replace(old, old + "\n    var summaryMaxEl = document.getElementById(prefix + '-max-summary');\n    if (summaryMaxEl) summaryMaxEl.textContent = fmt(maxRate, 1);")
    text = text.replace('```{r rango-anios}', "```{r rango-anios, results='asis'}")
    # Evitar contenedores HTML que cruzan límites de chunks de htmlwidgets.
    # Pandoc los cerraba implícitamente y podía anidar secciones del informe.
    if text.count('<div class="map-box">') != 3 or text.count('```\n</div>') != 3:
        raise ValueError('Cambió la estructura de los contenedores de mapas.')
    text = text.replace('<div class="map-box">', '')
    text = text.replace('```\n</div>', '```')
    # HTML equivalente a la única ecuación; evita cargar MathJax remoto.
    formula = re.compile(r'\\\[\s*\\text\{Indicador por 100,000\}_\{AGEB\}.*?\\\]', re.DOTALL)
    equation = '<div class="report-equation" role="math" aria-label="Indicador por cien mil del AGEB igual a pacientes elegibles divididos entre la población del AGEB del Censo 2020, multiplicado por cien mil."><strong>Indicador por 100,000<sub>AGEB</sub></strong> = <span class="fraction"><span>Pacientes elegibles en el AGEB</span><span>Población del AGEB · Censo 2020</span></span> × 100,000</div>'
    text, count = formula.subn(lambda _: equation, text)
    if count != 1:
        raise ValueError('Cambió la ecuación del informe; revisa el adaptador.')
    # Nombres accesibles para los seis controles temporales.
    text = text.replace("'-start-range\" type=\"range\"", "'-start-range\" aria-label=\"Año inicial del intervalo\" type=\"range\"")
    text = text.replace("'-end-range\" type=\"range\"", "'-end-range\" aria-label=\"Año final del intervalo\" type=\"range\"")
    coverage = """# Cobertura de los archivos

```{r cobertura-web, echo=FALSE}
knitr::kable(
  data.frame(
    Comprobacion = c(
      "Filas del Excel de geolocalización", "Filas con coordenadas válidas",
      "Filas sin coordenadas válidas", "Polígonos AGEB",
      "AGEB con población censal asociada", "AGEB sin población censal asociada",
      "Personas geolocalizadas con información temporal", "Personas fuera de un AGEB"
    ),
    Total = c(nrow(geo), nrow(geo_ok), nrow(geo) - nrow(geo_ok),
              nrow(agebs_censo), sum(!is.na(agebs_censo$POBTOT)),
              sum(is.na(agebs_censo$POBTOT)), nrow(puntos_persona),
              sum(!puntos_persona$asignado_ageb))
  ), col.names = c("Comprobación", "Total"), align = c("l", "r")
)
```

Las tasas requieren población censal válida. Los puntos fuera de un AGEB permanecen visibles cuando cumplen el criterio temporal, pero no contribuyen al numerador de un polígono. Las filas sin coordenadas válidas no pueden mostrarse en los mapas.

"""
    text = text.replace('# Información de sesión', coverage + '# Información de sesión')
    target = ROOT / 'build/informe-web.Rmd'
    target.parent.mkdir(exist_ok=True)
    target.write_text(text, encoding='utf-8')
    print('Copia para la web preparada; fuente original conservada.')


if __name__ == '__main__':
    main()
