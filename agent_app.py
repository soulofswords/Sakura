"""Standalone agent workspace; shares Sakura's saved model configuration."""
import threading
import webbrowser
from fastapi import FastAPI
import uvicorn

from agent_api import agent_router

_model=None
_lock=threading.Lock()


def selected_model():
    global _model
    with _lock:
        if _model is None:
            from app import get_settings,configure_saved_ai
            from llm import LLM
            settings=get_settings();model=LLM(persist_memory=False)
            configure_saved_ai(model,settings)
            if settings.get('llm_provider')=='ollama':
                model.model=settings.get('ollama_model',model.model)
                model.context_length=settings.get('ollama_context_length',4096)
                from ollama_runtime import server_for_folder
                model.base_url=server_for_folder(settings.get('ollama_models_folder',''))
            _model=model
    return _model


app=FastAPI(title='Sakura Agent')
def agent_available():
    from product import EDITION
    return EDITION!='vtuber'
app.include_router(agent_router(selected_model,agent_available))


def main():
    import socket
    import requests
    from config import BASE_DIR
    from agent_runtime import digest
    port=None
    for candidate in range(8790,8800):
        try:
            identity=requests.get(f'http://127.0.0.1:{candidate}/api/agent/identity',timeout=.4).json()
            if identity.get('application')=='sakura-agent' and identity.get('installation')==digest(str(BASE_DIR)):
                webbrowser.open(f'http://127.0.0.1:{candidate}/agent');raise SystemExit(0)
        except (requests.RequestException,ValueError):pass
        with socket.socket() as sock:
            try:sock.bind(('127.0.0.1',candidate));port=candidate;break
            except OSError:pass
    if port is None:raise RuntimeError('No free Sakura Agent port from 8790 to 8799.')
    threading.Timer(1,lambda:webbrowser.open(f'http://127.0.0.1:{port}/agent')).start()
    uvicorn.run(app,host='127.0.0.1',port=port,log_level='warning')


if __name__=='__main__':main()
