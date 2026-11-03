"""Create simple .xlsx files using only Python stdlib (zipfile + XML).

Excel rejects a workbook for three reasons that are easy to get wrong by hand: XML that
is not well formed (no escaping), text stored as a bare <v> number, and a formula that
keeps its leading "=". Each cell is therefore written with the type Excel expects.
"""
import math
import zipfile
from xml.sax.saxutils import escape, quoteattr

_CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                  '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                  '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                  '<Default Extension="xml" ContentType="application/xml"/>'
                  '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                  '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                  '</Types>')

_RELATIONSHIPS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                  '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                  '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                  'Target="worksheets/sheet1.xml"/>'
                  '</Relationships>')

# OPC packages start at this relationship part.  Some forgiving readers infer the
# workbook when it is absent, but Excel and other strict consumers are entitled to
# reject the archive without it.
_ROOT_RELATIONSHIPS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" '
                       'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                       'Target="xl/workbook.xml"/>'
                       '</Relationships>')

_BAD_SHEET_CHARACTERS = set('[]:*?/\\')
_ILLEGAL_CONTROL = {code for code in range(32)} - {9, 10, 13}


def _col_letter(j):
    """Convert 1-based column index to Excel column letter (A, B, ..., Z, AA, ...)."""
    result = ""
    while j > 0:
        j, r = divmod(j - 1, 26)
        result = chr(65 + r) + result
    return result


def _text(value):
    text = str(value)
    if any(ord(character) in _ILLEGAL_CONTROL for character in text):
        raise ValueError('Cell text contains a control character that Excel cannot store.')
    return escape(text)


def _number(value):
    """A real number, whether it arrived as a number or as digits in a string."""
    if isinstance(value, str):
        try:
            value = int(value.strip())
        except ValueError:
            try:
                value = float(value.strip())
            except ValueError:
                raise ValueError('A number cell needs a real number, not ' + repr(value) + '.') from None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('A number cell needs a real number, not ' + repr(value) + '.')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Excel cannot store an infinite or NaN number.')
    return value


def _boolean(value):
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in ('true', 'yes', '1'):
            return True
        if lowered in ('false', 'no', '0'):
            return False
        raise ValueError('A boolean cell needs true or false, not ' + repr(value) + '.')
    return bool(value)


def _cell_xml(col_idx, row_idx, value):
    """One <c> element with the type Excel needs for this value."""
    reference = _col_letter(col_idx) + str(row_idx)
    kind = None
    if isinstance(value, (tuple, list)) and len(value) == 2 and isinstance(value[0], str):
        kind, value = value[0].strip().casefold(), value[1]
    if kind not in (None, 'formula', 'string', 'text', 'number', 'boolean'):
        raise ValueError('Unknown cell type ' + str(kind) + '. Use formula, string, number or boolean.')
    if kind == 'formula':
        formula = str(value or '').strip()
        if formula.startswith('='):
            formula = formula[1:]
        if not formula:
            raise ValueError('A formula cell needs a formula, for example ("formula", "=SUM(A1:A2)").')
        return '<c r="' + reference + '"><f>' + _text(formula) + '</f></c>'
    if value is None:
        return ''
    if kind in ('number', 'boolean'):
        if kind == 'boolean':
            return '<c r="' + reference + '" t="b"><v>' + ('1' if _boolean(value) else '0') + '</v></c>'
        return '<c r="' + reference + '"><v>' + repr(_number(value)) + '</v></c>'
    if kind in ('string', 'text') or isinstance(value, str):
        text = str(value)
        if not text:
            return ''
        return '<c r="' + reference + '" t="inlineStr"><is><t xml:space="preserve">' + _text(text) + '</t></is></c>'
    if isinstance(value, bool):
        return '<c r="' + reference + '" t="b"><v>' + ('1' if value else '0') + '</v></c>'
    if isinstance(value, (int, float)):
        return '<c r="' + reference + '"><v>' + repr(_number(value)) + '</v></c>'
    raise ValueError('Cell values must be text, a number, a boolean, or (type, value).')


def _row_xml(cells, row_idx):
    """Build a <row> element from a list of cell values."""
    parts = [_cell_xml(cidx, row_idx, val) for cidx, val in enumerate(cells, 1)]
    return '<row r="' + str(row_idx) + '">' + ''.join(parts) + '</row>'


def _sheet_name(value):
    name = str('Sheet1' if value is None else value).strip()
    if not name or len(name) > 31 or _BAD_SHEET_CHARACTERS & set(name):
        raise ValueError('Sheet names need 1 to 31 characters and none of [ ] : * ? / \\.')
    return name


def write_xlsx(path, rows, sheet_name="Sheet1"):
    """Write a minimal XLSX file using only Python stdlib (zipfile).

    Args:
        path: filesystem path to write (.xlsx)
        rows: list of lists (or list of tuples), each inner list is a row.
              Cell values can be str, int, float, bool, or (type, value) tuple.
                - ('formula', '=SUM(A1:A1)')  -> formula cell
                - ('string', '007')           -> text, not the number 7
                - ('number', '12')            -> numeric cell
            A plain str is written as text, a plain number as a number.
        sheet_name: name of the worksheet (default "Sheet1")
    """
    name = _sheet_name(sheet_name)
    body = ''.join(_row_xml(row, ridx) for ridx, row in enumerate(rows, 1))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _ROOT_RELATIONSHIPS)
        z.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name=' + quoteattr(name) + ' sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        z.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>" + body + "</sheetData>"
            "</worksheet>",
        )
        z.writestr("xl/_rels/workbook.xml.rels", _RELATIONSHIPS)


def _display(value):
    """How a cell is shown in the approval preview, before anything is written."""
    if isinstance(value, (tuple, list)) and len(value) == 2 and isinstance(value[0], str):
        if value[0].strip().casefold() == 'formula':
            return '=' + str(value[1] or '').strip().lstrip('=')
        return '' if value[1] is None else str(value[1])
    return '' if value is None else str(value)


def preview(rows, limit=20):
    """A plain-text view of the rows for the approval panel. Every cell is validated here,
    so a bad type or formula is refused before the reviewer clicks approve."""
    lines = []
    for ridx, row in enumerate(rows, 1):
        for cidx, value in enumerate(row, 1):
            _cell_xml(cidx, ridx, value)
        if ridx <= limit:
            lines.append(' | '.join(_display(value) for value in row))
    if len(rows) > limit:
        lines.append('+ ' + str(len(rows) - limit) + ' more rows')
    return '\n'.join(lines)


if __name__ == "__main__":
    import pathlib
    import sys

    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("demo.xlsx")
    write_xlsx(out, [
        ("Header 1", "Header 2", "Header 3"),
        ("Alice", 30, 1_200_000),
        ("Bob", 25, 850_000),
        ("Total", ("formula", "=SUM(B2:B3)"), ("formula", "=SUM(C2:C3)")),
    ], sheet_name="Friends")
    print("Wrote " + str(out))
