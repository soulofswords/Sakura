"""Test client representing Sakura's same-origin window, not an arbitrary website."""
from fastapi.testclient import TestClient as BaseClient
class TestClient(BaseClient):
    __test__=False
    def __init__(self,*args,**kwargs):
        import gui_server
        kwargs.setdefault('base_url',f'http://127.0.0.1:{gui_server.port}')
        headers=dict(kwargs.pop('headers',{}) or {})
        headers.setdefault('origin',kwargs['base_url'].rstrip('/'))
        kwargs['headers']=headers
        super().__init__(*args,**kwargs)

def local_request():
    import gui_server
    from starlette.requests import Request
    host=f'127.0.0.1:{gui_server.port}'
    return Request({'type':'http','scheme':'http','path':'/','query_string':b'','server':('127.0.0.1',gui_server.port),'client':('127.0.0.1',1234),'headers':[(b'host',host.encode()),(b'origin',('http://'+host).encode())]})
