"""Run from the isolated installed app, never from the working project's root."""
import os
os.environ['SAKURA_START_MODE']='vtuber'
os.environ['SAKURA_DESKTOP']='1'
import asyncio
import app
import httpx

async def check():
    async with app.lifespan(app.app):
        assert app.app.state.ai_unloaded
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://test') as client:
            for path in ('/','/api/models','/api/voices','/api/settings'):
                response=await client.get(path)
                assert response.status_code==200,(path,response.status_code)
                if path=='/api/models':assert response.json()=={'models':[],'live2d_models':[]},response.json()
                print(path,'PASS')
    print('Isolated installed backend, empty model library, VTuber with no AI: PASS')

asyncio.run(check())
