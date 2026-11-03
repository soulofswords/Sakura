"""Reviewed, new-file-only PDF creation using ReportLab."""
import os
import textwrap
import tempfile
from pathlib import Path


def write_pdf(path, content, title='Document'):
    path = Path(path)
    title = str(title or 'Document').strip()
    content = str(content or '')
    if path.suffix.casefold() != '.pdf':
        raise ValueError('PDF output must use a .pdf filename.')
    if not path.parent.is_dir():
        raise ValueError('The PDF output folder must already exist.')
    if not title or len(title) > 200 or not content.strip() or len(content) > 50000:
        raise ValueError('Use a title up to 200 characters and PDF content from 1 to 50,000 characters.')
    if any(ord(character) < 32 and character not in '\n\r\t' for character in title + content):
        raise ValueError('PDF text contains unsupported control characters.')
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        raise RuntimeError('PDF creation needs ReportLab. Install requirements-agent.txt in Sakura’s Python environment.') from None
    if path.exists():
        raise ValueError('That PDF already exists. Choose a new filename; existing files are never overwritten.') from None
    temporary = None
    pages = 1
    try:
        descriptor, temporary = tempfile.mkstemp(prefix='.' + path.stem + '.', suffix='.sakura-pdf.tmp', dir=path.parent)
        os.close(descriptor)
        document = canvas.Canvas(temporary, pagesize=A4, pageCompression=1)
        width, height = A4
        margin = 48

        def header():
            document.setFont('Helvetica-Bold', 16)
            document.drawString(margin, height - margin, title)
            document.setFont('Helvetica', 10)
            return height - margin - 28

        y = header()
        for source in content.expandtabs(4).splitlines() or ['']:
            lines = textwrap.wrap(source, width=100, replace_whitespace=False,
                                  drop_whitespace=False) or ['']
            for line in lines:
                if y < margin + 18:
                    document.showPage(); pages += 1; y = header()
                document.drawString(margin, y, line[:500])
                y -= 13
            y -= 3
        document.save()
        # Hard-link publication is create-only: unlike os.replace(), it cannot
        # overwrite an existing user document if another process creates it
        # while ReportLab is rendering the temporary file.
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise ValueError('That PDF was created while Sakura was preparing it. Existing files are never overwritten.') from None
        except OSError as error:
            raise RuntimeError('Could not publish the PDF atomically; no file was written.') from error
    except Exception:
        raise
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
    return {'path': str(path), 'bytes': path.stat().st_size, 'pages': pages,
            'characters': len(content)}
