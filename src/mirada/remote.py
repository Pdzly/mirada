"""Control remoto desde el teléfono: pequeño servidor web en la red local."""
from __future__ import annotations

import json
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QObject, Signal

COMMANDS = {"toggle", "next", "prev", "faster", "slower", "fwd", "back", "restart", "section"}

REMOTE_PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mirada remoto</title><style>
body{margin:0;font:17px system-ui,sans-serif;background:#111;color:#eee;padding:18px}
h1{font-size:20px;margin:0 0 14px}.row{display:flex;gap:10px;margin-bottom:10px}
button{flex:1;min-height:64px;font-size:20px;border:0;border-radius:14px;background:#2a2a2a;color:#eee}
button.main{background:#ff7a59;color:#111;font-weight:700}
#secs button{display:block;width:100%;min-height:52px;margin-bottom:8px;text-align:left;padding:0 16px;font-size:17px}
#st{color:#999;margin:8px 0 16px;font-size:15px}</style></head><body>
<h1>Mirada · control remoto</h1>
<div class="row"><button class="main" onclick="c('toggle')">⏯ Pausa / seguir</button></div>
<div class="row"><button onclick="c('prev')">⏮ Sección</button><button onclick="c('next')">Sección ⏭</button></div>
<div class="row"><button onclick="c('slower')">− Lento</button><button onclick="c('faster')">+ Rápido</button></div>
<div class="row"><button onclick="c('back')">↑ Retroceder</button><button onclick="c('fwd')">↓ Avanzar</button></div>
<div class="row"><button onclick="c('restart')">↺ Desde el inicio</button></div>
<div id="st"></div><div id="secs"></div>
<script>
const T=encodeURIComponent(new URLSearchParams(location.search).get('t')||'');
async function c(cmd,i){await fetch('/api/cmd?t='+T+'&c='+cmd+(i!=null?'&i='+i:''),{method:'POST'});load()}
async function load(){try{const r=await fetch('/api/state?t='+T);const s=await r.json();
document.getElementById('st').textContent=(s.open?(s.paused?'En pausa':'Corriendo'):'Prompter cerrado')+' · velocidad '+s.speed;
const d=document.getElementById('secs');d.innerHTML='';
s.sections.forEach((n,i)=>{const b=document.createElement('button');b.textContent=(i+1)+'. '+n;b.onclick=()=>c('section',i);d.appendChild(b)})}catch(e){}}
load();setInterval(load,2000);
</script></body></html>"""


def local_ip() -> str:
    """IP de la interfaz con ruta por defecto (no envía paquetes)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return "127.0.0.1"


class RemoteBridge(QObject):
    """Servidor HTTP en un hilo; los comandos llegan a Qt mediante una señal."""

    command = Signal(str, int)

    def __init__(self):
        super().__init__()
        self.state = {"open": False, "paused": True, "speed": 0, "sections": []}
        self.token = ""
        self.server: ThreadingHTTPServer | None = None
        self.port = 0

    def start(self, port: int, token: str, host: str = "0.0.0.0") -> str:
        """Inicia el servidor. Devuelve la URL para el teléfono, o un mensaje
        de error que empieza con «No se pudo»."""
        self.stop()
        self.token = token
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code: int, body: bytes = b"", ctype: str = "text/plain"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def _auth(self, q) -> bool:
                given = q.get("t", [""])[0]
                if not bridge.token or not secrets.compare_digest(given.encode(), bridge.token.encode()):
                    self._send(403, b"forbidden")
                    return False
                return True

            def do_GET(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if not self._auth(q):
                    return
                if u.path == "/":
                    self._send(200, REMOTE_PAGE.encode(), "text/html; charset=utf-8")
                elif u.path == "/api/state":
                    self._send(200, json.dumps(bridge.state).encode(), "application/json")
                else:
                    self._send(404, b"not found")

            def do_POST(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if not self._auth(q):
                    return
                if u.path != "/api/cmd":
                    self._send(404, b"not found")
                    return
                cmd = q.get("c", [""])[0]
                if cmd not in COMMANDS:
                    self._send(400, b"bad command")
                    return
                try:
                    idx = int(q.get("i", ["-1"])[0])
                except ValueError:
                    idx = -1
                bridge.command.emit(cmd, idx)
                self._send(200, b"{}", "application/json")

        try:
            self.server = ThreadingHTTPServer((host, port), Handler)
        except OSError as e:
            self.server = None
            return f"No se pudo abrir el puerto {port}: {e}"
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return f"http://{local_ip()}:{self.port}/?t={token}"

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
