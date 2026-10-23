"""Small, localhost-only OSC receiver for VBridger's VMC blendshape output."""
from __future__ import annotations

import socket
import struct
import threading
import time


def _osc_string(data: bytes, offset: int) -> tuple[str, int]:
    end = data.find(b"\0", offset)
    if end < 0:
        raise ValueError("invalid OSC string")
    value = data[offset:end].decode("utf-8", errors="replace")
    return value, (end + 4) & ~3


def _osc_messages(packet: bytes):
    """Yield OSC address and typed values, including messages in OSC bundles."""
    if packet.startswith(b"#bundle\0"):
        offset = 16  # bundle marker and NTP timetag
        while offset + 4 <= len(packet):
            size = struct.unpack_from(">I", packet, offset)[0]
            offset += 4
            if size <= 0 or offset + size > len(packet):
                return
            yield from _osc_messages(packet[offset:offset + size])
            offset += size
        return
    try:
        address, offset = _osc_string(packet, 0)
        tags, offset = _osc_string(packet, offset)
        if not tags.startswith(","):
            return
        values = []
        for tag in tags[1:]:
            if tag in ("f", "i"):
                if offset + 4 > len(packet):
                    return
                values.append(struct.unpack_from(">f" if tag == "f" else ">i", packet, offset)[0])
                offset += 4
            elif tag == "s":
                value, offset = _osc_string(packet, offset)
                values.append(value)
            elif tag in ("T", "F"):
                values.append(tag == "T")
            else:
                return
        yield address, values
    except (ValueError, UnicodeError, struct.error):
        return


class VBridgerReceiver:
    def __init__(self):
        self._lock = threading.Lock()
        self._socket = None
        self._thread = None
        self._blendshapes = {}
        self._updated_at = 0.0
        self._error = ""

    def start(self, port: int = 39539):
        if self._thread and self._thread.is_alive():
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", int(port)))
            sock.settimeout(0.5)
        except OSError:
            sock.close()
            raise
        self._socket = sock
        self._thread = threading.Thread(target=self._run, name="SakuraVBridgerVMC", daemon=True)
        self._thread.start()

    def _run(self):
        while self._socket:
            try:
                packet, _ = self._socket.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            for address, values in _osc_messages(packet):
                if address == "/VMC/Ext/Blend/Val" and len(values) >= 2 and isinstance(values[0], str):
                    name, value = values[0], values[1]
                    if name and isinstance(value, (int, float)):
                        with self._lock:
                            self._blendshapes[name] = max(0.0, min(1.0, float(value)))
                            self._updated_at = time.time()

    def snapshot(self):
        with self._lock:
            age = time.time() - self._updated_at if self._updated_at else None
            return {"connected": age is not None and age < 2.0,
                    "age_ms": round(age * 1000) if age is not None else None,
                    "blendshapes": dict(self._blendshapes) if age is not None and age < 2.0 else {},
                    "port": 39539}


receiver = VBridgerReceiver()
