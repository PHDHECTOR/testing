from pathlib import Path
import csv
import io
import json

from support import BrowserCase, ROOT


class PublicBrowserTests(BrowserCase):
    def setUp(self):
        super().setUp()
        self.page.goto(self.url, wait_until='networkidle')
        self.page.wait_for_function('!!window.RERIMSS_PUBLIC')

    def test_maps_have_polygons_and_no_individual_markers(self):
        counts = self.page.evaluate('''() => Object.values(RERIMSS_PUBLIC.maps).map(item => {
          let polygons=0, markers=0;
          item.map.eachLayer(layer=>{if(layer instanceof L.Polygon)polygons++;if(layer instanceof L.CircleMarker)markers++;});
          return {polygons,markers};
        })''')
        self.assertEqual(len(counts), 3)
        self.assertTrue(all(count['polygons'] == 479 and count['markers'] == 0 for count in counts))
        self.assertTrue(self.external, 'El navegador no solicitó el fondo CARTO.')
        self.assertEqual(set(self.external), {'a.basemaps.cartocdn.com'})
        self.assertTrue(self.page.evaluate('''() => Object.values(RERIMSS_PUBLIC.maps).every(item =>
          item.basemap.getTileUrl({x:0,y:0,z:0}).startsWith('https://a.basemaps.cartocdn.com/') &&
          Object.values(item.basemap._tiles).some(tile => tile.loaded && tile.el.naturalWidth > 0))'''))
        interaction = self.page.evaluate('''() => {
          const {map,layer} = RERIMSS_PUBLIC.maps.total;
          const zoom = map.getZoom();
          map.setZoom(zoom+1, {animate:false});
          layer.getLayers()[0].openPopup();
          return {zoomed:map.getZoom()===zoom+1,popup:!!map._popup && /AGEB/.test(map._popup.getContent())};
        }''')
        self.assertEqual(interaction, {'zoomed':True,'popup':True})
        self.context.route('https://a.basemaps.cartocdn.com/**', lambda route: route.abort())
        self.page.reload(wait_until='networkidle')
        self.assertEqual(self.page.locator('.basemap-status:visible').count(), 3)
        self.assertTrue(self.page.evaluate('RERIMSS_PUBLIC.maps.total.layer.getLayers().length === 479'))

    def test_public_periods_are_independent(self):
        data = json.loads((ROOT / 'build/public-payload.json').read_text())
        others = {name: self.page.locator('#period-'+name).input_value() for name in ['incidence','active']}
        for period in [data['periods'][0], data['periods'][-2]]:
            self.page.select_option('#period-total', period['id'])
            self.assertEqual(self.page.evaluate('RERIMSS_PUBLIC.selections.total'), period['id'])
            cells = [cell for cell in data['cells']['total'][period['id']] if not cell['suppressed']]
            value = self.page.locator('#count-total').inner_text().replace(',', '').replace('≈', '').strip()
            self.assertEqual(value, str(sum(cell['count'] for cell in cells)) if cells else '—')
            for name, selected in others.items():
                self.assertEqual(self.page.locator('#period-'+name).input_value(), selected)

    def test_public_csv_and_table_filters(self):
        self.assertIn('de 479', self.page.locator('#table-status').inner_text())
        self.page.locator('#next-page').click()
        self.assertEqual(self.page.locator('#page-status').inner_text(), '2 / 40')
        data = json.loads((ROOT / 'build/public-payload.json').read_text())
        code = data['geometry']['features'][0]['properties']['code']
        self.page.fill('#table-search', code)
        self.assertEqual(self.page.locator('#public-table tr').count(), 1)
        with self.page.expect_download() as download:
            self.page.locator('#download-csv').click()
        content = Path(download.value.path()).read_text(encoding='utf-8-sig')
        rows = list(csv.DictReader(io.StringIO(content)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['clave_ageb'], code)
        self.assertNotIn('curp', rows[0])
        if rows[0]['protegido'] == 'no':
            self.assertEqual(int(rows[0]['casos_publicados']) % 5, 0)
        else:
            self.assertEqual(rows[0]['casos_publicados'], 'Protegido (<5)')

    def test_public_mobile_and_login_link(self):
        self.page.set_viewport_size({'width':390,'height':844})
        self.page.wait_for_timeout(250)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        self.page.get_by_role('link', name='Acceso para colegas').click()
        self.assertTrue(self.page.url.endswith('/login'))
        self.assertEqual(self.page.locator('#password').get_attribute('type'), 'password')
