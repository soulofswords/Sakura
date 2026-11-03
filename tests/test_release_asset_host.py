import unittest
import httpx
import app


class AssetHostTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_loopback_host_cannot_read_assets(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url=f'http://attacker.example:{app.gui_server.port}') as client:
            for path in ('/', '/static/index.html', '/models/private.pmx', '/audio/private.wav'):
                response = await client.get(path)
                self.assertEqual(response.status_code, 403)

    async def test_legitimate_local_page_still_loads(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url=f'http://127.0.0.1:{app.gui_server.port}') as client:
            response = await client.get('/static/index.html')
            self.assertEqual(response.status_code, 200)
