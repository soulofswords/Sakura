"""Loopback-only read-only model renderer assets; no app/account API."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import mimetypes
import shutil
import os
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        path=unquote(urlsplit(self.path).path)
        parts=path.strip('/').split('/')
        if not parts or parts[0] not in ('static','models'):
            self.send_error(404);return
        if parts[:2]==['models','pmx'] and os.environ.get('SAKURA_LIBRARY_PREVIEW_PMX_ROOT'):
            root=Path(os.environ['SAKURA_LIBRARY_PREVIEW_PMX_ROOT']).resolve()
            target=root.joinpath(*parts[2:]).resolve()
        else:
            root=ROOT/parts[0]
            target=root.joinpath(*parts[1:]).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file() or target.suffix.lower() in ('.py','.bin','.env','.exe'):
            self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
        self.send_header('Content-Length',str(target.stat().st_size));self.end_headers()
        with target.open('rb') as source:shutil.copyfileobj(source,self.wfile)


if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8796),Handler).serve_forever()
