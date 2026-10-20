from collections import Counter
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import json
import math
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WidgetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.content = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'script' and attributes.get('type') == 'application/json' and attributes.get('data-for'):
            self.capture = not self.content

    def handle_data(self, data):
        if self.capture:
            self.content.append(data)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.capture = False


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = json.loads((ROOT / 'build/public-payload.json').read_text())
        parser = WidgetParser()
        parser.feed((ROOT / 'dist/private/index.html').read_text())
        cls.clinical = json.loads(parser.content[0])['jsHooks']['render'][0]['data']

    def test_public_cells_against_independent_private_reference(self):
        points = self.clinical['points']
        population = {item['id']: item['poblacion'] for item in self.clinical['agebs']}
        checked = 0
        for metric, periods in self.public['cells'].items():
            for period, cells in periods.items():
                start, end = map(int, period.split('-'))
                def eligible(point):
                    began, death = point['startYear'], point['deathYear']
                    if metric == 'incidence':
                        return start <= began <= end
                    if metric == 'active':
                        return began <= end and (death is None or death > end)
                    return began <= end and (death is None or death >= start)
                counts = Counter(point['ageb'] for point in points if point['ageb'] and eligible(point))
                self.assertEqual(len(cells), 479)
                for cell in cells:
                    raw = counts[cell['code']]
                    if raw < 5:
                        self.assertTrue(cell['suppressed'])
                        self.assertIsNone(cell['count'])
                        self.assertIsNone(cell['rate'])
                    else:
                        rounded = 5 * math.floor(raw / 5 + .5)
                        self.assertFalse(cell['suppressed'])
                        self.assertEqual(cell['count'], rounded)
                        pop = population[cell['code']]
                        if pop is None or pop <= 0:
                            self.assertIsNone(cell['rate'])
                        else:
                            self.assertAlmostEqual(cell['rate'], 100000 * rounded / pop, delta=1e-6)
                    checked += 1
        self.assertEqual(checked, 15807)

    def test_no_individuals_in_public_schema(self):
        forbidden = {'points', 'person', 'curp', 'nombre', 'domicilio', 'startYear', 'deathYear', 'lat', 'long', 'popup_base', 'trayectoria_html'}
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for item in value.values(): check(item)
            elif isinstance(value, list):
                for item in value: check(item)
        check(self.public)
        for feature in self.public['geometry']['features']:
            self.assertIn(feature['geometry']['type'], ['Polygon', 'MultiPolygon'])
            self.assertLessEqual(set(feature['properties']), {'code', 'ageb', 'municipality', 'locality', 'population'})
        for cells in self.public['cells'].values():
            for rows in cells.values():
                for row in rows:
                    self.assertEqual(set(row), {'code', 'count', 'rate', 'suppressed'})

    def test_public_html_contains_no_patient_identifiers(self):
        db_path = Path('/workspace/inputs/prueba_codex/RERIMSS(4).db')
        with sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True) as db:
            records = db.execute('SELECT curp,nombre,apellido_paterno,apellido_materno FROM registros').fetchall()
        html = unescape((ROOT / 'dist/public/index.html').read_text()).casefold()
        identifiers = {str(row[0]).strip().casefold() for row in records if row[0] and len(str(row[0]).strip()) >= 15}
        names = {' '.join(str(value).strip() for value in row[1:] if value).casefold() for row in records}
        names = {value for value in names if len(value) >= 18}
        self.assertEqual(sum(value in html for value in identifiers), 0, 'Se encontró un identificador de paciente en el HTML público.')
        self.assertEqual(sum(value in html for value in names), 0, 'Se encontró un nombre de paciente en el HTML público.')

    def test_updated_census_and_positive_denominators(self):
        summary = json.loads((ROOT / 'build/validation.json').read_text())
        self.assertEqual(summary['census_file'], 'RESAGEBURB_01CSV20_AGS(2).xlsx')
        self.assertEqual(summary['agebs_with_population'], 479)
        self.assertEqual(summary['agebs_without_population'], 0)
        self.assertEqual(self.public['positive_population_agebs'], 478)
        self.assertTrue(all(period['end'] - period['start'] <= 4 for period in self.public['periods']))
