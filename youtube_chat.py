"""Read-only, bounded live-chat inbox. No login or posting capabilities."""
from collections import deque
import re
import threading
import time
from urllib.parse import urlparse, parse_qs


def video_id(link):
    value = link.strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', value):
        return value
    parsed = urlparse(value)
    if parsed.hostname in {'youtu.be', 'www.youtu.be'}:
        value = parsed.path.strip('/')
    elif parsed.hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com'}:
        value = parse_qs(parsed.query).get('v', [''])[0]
        if not value and parsed.path.startswith(('/live/', '/shorts/')):
            value = parsed.path.split('/')[2]
    else:
        raise ValueError('Enter a YouTube livestream or pop-out chat URL.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', value):
        raise ValueError('This URL does not contain a YouTube video ID.')
    return value


class YouTubeChat:
    def __init__(self):
        self.lock = threading.Lock()
        self.generation = 0
        self.client = None
        self.messages = deque(maxlen=30)
        self.seen = deque(maxlen=1000)
        self.status = 'Disconnected'
        self.connected = False

    def stop(self):
        with self.lock:
            self.generation += 1
            client, self.client = self.client, None
            self.connected = False
            self.messages.clear()
            self.status = 'Disconnected'
        if client:
            client.terminate()

    def connect(self, link):
        identity = video_id(link)
        self.stop()
        with self.lock:
            generation = self.generation
            self.seen.clear()
            self.status = 'Connecting to YouTube…'
        threading.Thread(target=self._read, args=(identity, generation), daemon=True).start()
        return identity

    def _read(self, identity, generation):
        client = None
        started = time.time() * 1000
        try:
            import pytchat
            client = pytchat.create(video_id=identity, interruptable=False)
            with self.lock:
                if generation != self.generation:
                    return
                self.client = client
                self.connected = True
                self.status = 'Connected · waiting for new chat messages'
            while client.is_alive():
                with self.lock:
                    if generation != self.generation:
                        return
                for item in client.get().sync_items():
                    with self.lock:
                        if generation != self.generation:
                            return
                        if item.id in self.seen:
                            continue
                        self.seen.append(item.id)
                        if item.timestamp < started or item.type not in {'textMessage', 'superChat'}:
                            continue
                        self.messages.append({'id': item.id, 'author': item.author.name[:80],
                            'text': item.message[:500], 'timestamp': item.timestamp})
                time.sleep(1)
            raise ValueError('Live chat ended or is unavailable. Check that the stream is live and chat is enabled.')
        except Exception as exc:
            with self.lock:
                if generation == self.generation:
                    self.status = str(exc)[:240]
                    self.connected = False
        finally:
            if client:
                client.terminate()

    def poll(self):
        with self.lock:
            messages = list(self.messages)
            self.messages.clear()
            return {'connected': self.connected, 'status': self.status, 'messages': messages}


chat = YouTubeChat()
