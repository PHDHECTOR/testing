"""Pruebas del informe clínico a través de su ruta autenticada."""
from collections import Counter
from support import BrowserCase, ROOT

PREFIXES = ('rerimss-total', 'rerimss-incidence', 'rerimss-active')


class ReportTests(BrowserCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.page.wait_for_load_state('networkidle')
        self.page.goto(self.url + 'privado/informe', wait_until='networkidle')
        self.page.wait_for_function("document.getElementById('rerimss-active-count').textContent !== 'Calculando…'")
        self.page.wait_for_timeout(500)

    def numeric(self, selector):
        return float(self.page.locator(selector).inner_text().replace(',', '').strip())

    def test_three_maps_and_layers(self):
        self.assertEqual(self.page.locator('.leaflet.html-widget').count(), 3)
        layers = self.page.evaluate('''() => Array.from(document.querySelectorAll('.leaflet.html-widget')).map(el => {
          const map = HTMLWidgets.find('#' + el.id).getMap();
          let polygons = 0, points = 0, carto = 0;
          map.eachLayer(layer => {
            if (layer instanceof L.Polygon) polygons++;
            if (layer instanceof L.CircleMarker) points++;
            if (layer instanceof L.TileLayer && layer._url.startsWith('https://a.basemaps.cartocdn.com/')) carto++;
          });
          return {polygons, points, carto};
        })''')
        for index, layer in enumerate(layers):
            self.assertEqual(layer['polygons'], self.reference['ageb_polygons'])
            self.assertEqual(layer['points'], self.reference['scenarios'][index]['count'])
            self.assertEqual(layer['carto'], 1)
        popup_open = self.page.evaluate('''() => {
          const widget = document.querySelector('.leaflet.html-widget');
          const map = HTMLWidgets.find('#' + widget.id).getMap();
          let polygon;
          map.eachLayer(layer => { if (!polygon && layer instanceof L.Polygon) polygon = layer; });
          polygon.openPopup();
          return !!map._popup && /Pacientes/.test(map._popup.getContent());
        }''')
        self.assertTrue(popup_open, 'El popup del AGEB no mostró su resultado.')

    def test_temporal_counts_rates_and_independence(self):
        for scenario in self.reference['scenarios']:
            with self.subTest(prefix=scenario['prefix'], start=scenario['start'], end=scenario['end']):
                prefix = scenario['prefix']
                others = {other: self.page.locator('#' + other + '-period').inner_text() for other in PREFIXES if other != prefix}
                self.page.evaluate('''data => {
                  const start = document.getElementById(data.prefix + '-start-range');
                  const end = document.getElementById(data.prefix + '-end-range');
                  start.value = data.start; end.value = data.end;
                  start.dispatchEvent(new Event('input', {bubbles: true}));
                  end.dispatchEvent(new Event('change', {bubbles: true}));
                }''', scenario)
                self.page.wait_for_function('''data => document.getElementById(data.prefix + '-period').textContent.endsWith(data.start + '–' + data.end)''', arg=scenario)
                self.assertEqual(self.numeric('#' + prefix + '-count'), scenario['count'])
                self.assertAlmostEqual(self.numeric('#' + prefix + '-max'), scenario['max_rate'], delta=0.051)
                self.assertEqual(self.page.locator('#' + prefix + '-max').inner_text(), self.page.locator('#' + prefix + '-max-summary').inner_text())
                for other, value in others.items():
                    self.assertEqual(self.page.locator('#' + other + '-period').inner_text(), value)

    def test_no_duplicate_ids_or_stuck_summaries(self):
        identifiers = self.page.locator('[id]').evaluate_all('(elements) => elements.map(el => el.id)')
        duplicates = [key for key, count in Counter(identifiers).items() if count > 1]
        self.assertEqual(duplicates, [])
        for prefix in PREFIXES:
            self.assertNotIn('Calculando', self.page.locator('#' + prefix + '-max-summary').inner_text())
        self.assertEqual(self.page.locator('.report-equation').count(), 1)

    def test_embedded_resources_and_carto_only_for_basemap(self):
        self.assertEqual(self.reference['basemap'], 'carto')
        self.assertTrue(self.external, 'El informe no solicitó teselas de CARTO.')
        self.assertEqual(set(self.external), {'a.basemaps.cartocdn.com'})
        # Chromium administrado bloquea file://. Comprobar el mismo HTML por HTTP,
        # con la red externa bloqueada, también verifica sus recursos incorporados.
        resources = self.page.locator('script[src], link[rel="stylesheet"][href], img[src]').evaluate_all('''elements => elements.map(el => el.src || el.href).filter(url => !url.startsWith('data:') && !url.startsWith('blob:') && !url.startsWith('https://a.basemaps.cartocdn.com/'))''')
        self.assertEqual(resources, [])
        self.assertFalse(any(path.suffix.lower() in ('.db', '.xlsx', '.shp', '.dbf') for path in (ROOT / 'dist').rglob('*')))

    def test_mobile_layout_and_keyboard(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.wait_for_timeout(250)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        controls = self.page.locator('.shared-control input[type="range"]')
        self.assertEqual(controls.count(), 6)
        self.assertTrue(all(controls.nth(i).get_attribute('aria-label') for i in range(6)))
        start = self.page.locator('#rerimss-total-start-range')
        start.focus()
        start.press('ArrowRight')
        expected = self.reference['min_year'] + 1
        self.page.wait_for_function("value => document.getElementById('rerimss-total-start-value').textContent === String(value)", arg=expected)
        self.assertEqual(int(start.input_value()), expected)
