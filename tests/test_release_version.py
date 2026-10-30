from fastapi.testclient import TestClient
import app
from product import VERSION

def test_installed_version_endpoint_is_local_and_consistent():
    client=TestClient(app.app,base_url='http://127.0.0.1:8766')
    response=client.get('/api/version')
    assert response.status_code==200
    assert response.json()['version']==VERSION=='1.0.2'
    assert client.get('/api/version',headers={'host':'attacker.example'}).status_code==403
