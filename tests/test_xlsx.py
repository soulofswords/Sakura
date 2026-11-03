"""The XLSX writer must produce a package Excel will actually open: well-formed XML,
text stored as text, numbers as numbers and formulas without their leading "="."""
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from sakura_xlsx import write_xlsx

MAIN = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def _parts(path):
    with zipfile.ZipFile(path) as package:
        return {name: package.read(name) for name in package.namelist()}


def _sheet(path):
    root = ET.fromstring(_parts(path)['xl/worksheets/sheet1.xml'])
    return {cell.get('r'): cell for cell in root.iter(MAIN + 'c')}


class XlsxWriterTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'report.xlsx'

    def write(self, rows, **kwargs):
        write_xlsx(self.path, rows, **kwargs)
        return _sheet(self.path)

    def test_every_part_is_well_formed_and_the_required_parts_exist(self):
        write_xlsx(self.path, [('Header', 1)])
        parts = _parts(self.path)
        for required in ('[Content_Types].xml', '_rels/.rels', 'xl/workbook.xml',
                         'xl/worksheets/sheet1.xml', 'xl/_rels/workbook.xml.rels'):
            self.assertIn(required, parts)
        for name, data in parts.items():
            ET.fromstring(data)  # raises on malformed XML

    def test_workbook_has_the_required_root_and_sheet_relationships(self):
        write_xlsx(self.path, [('Header', 1)])
        parts = _parts(self.path)
        root_rels = ET.fromstring(parts['_rels/.rels'])
        office_document = root_rels.find('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')
        self.assertEqual(office_document.get('Target'), 'xl/workbook.xml')
        workbook = ET.fromstring(parts['xl/workbook.xml'])
        sheet = workbook.find(MAIN + 'sheets/' + MAIN + 'sheet')
        self.assertEqual(sheet.get(REL + 'id'), 'rId1')
        self.assertIsNone(sheet.get('id'))

    def test_text_is_stored_as_text_not_a_bare_number(self):
        cells = self.write([('Header 1', 'Alice', '007')])
        self.assertEqual(cells['A1'].get('t'), 'inlineStr')
        self.assertEqual(cells['B1'].get('t'), 'inlineStr')
        self.assertEqual(cells['C1'].get('t'), 'inlineStr')
        self.assertEqual(cells['C1'].find(MAIN + 'is/' + MAIN + 't').text, '007')

    def test_special_characters_are_escaped_and_survive_a_round_trip(self):
        cells = self.write([('A & B', '<tag>', 'a > b')])
        self.assertEqual(cells['A1'].find(MAIN + 'is/' + MAIN + 't').text, 'A & B')
        self.assertEqual(cells['B1'].find(MAIN + 'is/' + MAIN + 't').text, '<tag>')
        self.assertEqual(cells['C1'].find(MAIN + 'is/' + MAIN + 't').text, 'a > b')

    def test_numbers_and_booleans_use_their_native_cell_types(self):
        cells = self.write([(30, 1.5, True, False)])
        self.assertIsNone(cells['A1'].get('t'))
        self.assertEqual(cells['A1'].find(MAIN + 'v').text, '30')
        self.assertEqual(cells['B1'].find(MAIN + 'v').text, '1.5')
        self.assertEqual(cells['C1'].get('t'), 'b')
        self.assertEqual(cells['C1'].find(MAIN + 'v').text, '1')
        self.assertEqual(cells['D1'].find(MAIN + 'v').text, '0')

    def test_formula_tuples_lose_the_leading_equals_sign(self):
        cells = self.write([(2, ('formula', '=SUM(A1:A3)')), (1,), (3,)])
        formula = cells['B1'].find(MAIN + 'f')
        self.assertEqual(formula.text, 'SUM(A1:A3)')
        self.assertIsNone(cells['A1'].find(MAIN + 'f'))

    def test_typed_strings_keep_leading_zeros(self):
        cells = self.write([(('string', '007'), ('number', '007'))])
        self.assertEqual(cells['A1'].get('t'), 'inlineStr')
        self.assertEqual(cells['B1'].find(MAIN + 'v').text, '7')

    def test_empty_cells_are_omitted_but_later_columns_keep_their_reference(self):
        cells = self.write([('', 'kept')])
        self.assertNotIn('A1', cells)
        self.assertIn('B1', cells)

    def test_sheet_name_is_escaped_and_validated(self):
        write_xlsx(self.path, [('x',)], sheet_name='R&D "2026"')
        workbook = ET.fromstring(_parts(self.path)['xl/workbook.xml'])
        self.assertEqual(workbook.find(MAIN + 'sheets/' + MAIN + 'sheet').get('name'), 'R&D "2026"')
        for bad in ('', 'x' * 32, 'a/b', 'a:b', 'a[b]'):
            with self.assertRaises(ValueError):
                write_xlsx(self.path, [('x',)], sheet_name=bad)

    def test_values_excel_cannot_store_are_refused(self):
        for bad in (float('nan'), float('inf'), ('formula', '='), ('formula', None),
                    ('date', '2026-01-01'), {'a': 1}, 'control\x0bcharacter'):
            with self.assertRaises(ValueError, msg=repr(bad)):
                write_xlsx(self.path, [(bad,)])

    @unittest.skipUnless(importlib.util.find_spec('openpyxl'), 'openpyxl is not installed')
    def test_openpyxl_reads_the_types_back(self):
        import openpyxl
        write_xlsx(self.path, [('Name', 'Score'), ('Alice', 30), ('Bob', ('formula', '=SUM(B2:B2)'))])
        sheet = openpyxl.load_workbook(self.path).active
        self.assertEqual(sheet['A1'].value, 'Name')
        self.assertEqual(sheet['B2'].value, 30)
        self.assertEqual(sheet['B3'].value, '=SUM(B2:B2)')


if __name__ == '__main__':
    unittest.main()
