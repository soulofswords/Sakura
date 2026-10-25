"""Find Sakura's backend without mistaking another local app for it."""
import json
import os
import socket
import threading
import webbrowser
from urllib.request import build_opener, ProxyHandler

HOST = "127.0.0.1"
port = 8766

def url():
    suffix = "?upload=1" if os.environ.get("SAKURA_UPLOAD_UI") == "1" else ""
    return f"http://{HOST}:{port}{suffix}"

def select_port():
    global port
    opener = build_opener(ProxyHandler({}))
    from product import EDITION
    from vtuber_instances import instance_index
    separate=(EDITION=='vtuber' or os.environ.get('SAKURA_VTUBER_INSTANCE')=='1') and 'SAKURA_INSTANCE_INDEX' in os.environ
    first=(8780 if EDITION=='vtuber' else 8830)+(instance_index()-1)*10 if separate else 8766
    for candidate in range(first,first+8 if separate else 8777):
        address = f"http://{HOST}:{candidate}"
        try:
            if separate:raise ValueError("Separate instance requires its own backend")
            with opener.open(address + "/api/identity", timeout=0.5) as response:
                from product import EDITION, INSTALLATION_ID
                identity=json.load(response)
                if identity.get("application") == "sakura-anime-assistant" and identity.get('edition')==EDITION and identity.get('installation')==INSTALLATION_ID:
                    port = candidate
                    return True
        except Exception:
            pass
        with socket.socket() as sock:
            try:
                sock.bind((HOST, candidate))
            except OSError:
                continue
        port = candidate
        return False
    raise RuntimeError("No available Sakura port between 8766 and 8776")

def launch():
    import uvicorn
    if select_port():
        print(f"Opening existing Sakura backend at {url()}")
        webbrowser.open(url())
        return
    print(f"Starting Sakura at {url()}")
    # Uvicorn owns the foreground process.  Open the upload/library page only
    # after it has had a moment to begin accepting localhost connections.
    threading.Timer(0.9, lambda: webbrowser.open(url())).start()
    uvicorn.run("app:app", host=HOST, port=port, log_level="warning")
