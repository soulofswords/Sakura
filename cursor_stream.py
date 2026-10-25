"""Low-latency cursor samples for the local renderer, without per-frame RPC."""
import asyncio
from urllib.parse import urlsplit

from fastapi import WebSocket, WebSocketDisconnect
from screen_cursor import position


def install_cursor_stream(app):
    @app.websocket('/api/cursor/stream')
    async def cursor_stream(socket: WebSocket):
        # HTTP middleware does not protect WebSocket handshakes. Do not expose
        # desktop cursor activity to unrelated websites, including other ports.
        origin = socket.headers.get('origin', '')
        try:
            parsed = urlsplit(origin)
            local = parsed.hostname in ('127.0.0.1', 'localhost', '::1')
            same_origin = parsed.netloc.lower() == socket.headers.get('host', '').lower()
        except ValueError:
            local = same_origin = False
        if not local or not same_origin or parsed.scheme not in ('http', 'https'):
            await socket.close(code=1008)
            return
        await socket.accept()
        loop = asyncio.get_running_loop()
        due = loop.time()
        disconnected = asyncio.create_task(socket.receive())
        try:
            while not disconnected.done():
                await socket.send_json(position() or {})
                # Deadline-based scheduling avoids adding sampling/send time to
                # every frame. A slow renderer never creates a catch-up burst.
                due = max(due + 1 / 60, loop.time())
                await asyncio.wait({disconnected}, timeout=max(0, due - loop.time()))
        except (WebSocketDisconnect, OSError, RuntimeError):
            pass
        finally:
            disconnected.cancel()
            await asyncio.gather(disconnected, return_exceptions=True)
