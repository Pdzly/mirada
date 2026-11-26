import json
import urllib.error
import urllib.request

import pytest
from PySide6.QtCore import QCoreApplication

from mirada.remote import RemoteBridge

TOKEN = "t" * 22


@pytest.fixture
def bridge():
    b = RemoteBridge()
    url = b.start(0, TOKEN, host="127.0.0.1")
    assert url.startswith("http://"), url
    b.base = f"http://127.0.0.1:{b.port}"
    yield b
    b.stop()


def _req(url, method="GET"):
    return urllib.request.urlopen(urllib.request.Request(url, method=method), timeout=5)


def test_rejects_without_token(bridge):
    for path in ("/", "/?t=malo", "/api/state?t="):
        with pytest.raises(urllib.error.HTTPError) as e:
            _req(bridge.base + path)
        assert e.value.code == 403


def test_page_and_state(bridge):
    assert b"Mirada" in _req(f"{bridge.base}/?t={TOKEN}").read()
    bridge.state["speed"] = 42
    assert json.loads(_req(f"{bridge.base}/api/state?t={TOKEN}").read())["speed"] == 42


def test_command_emits_signal(bridge):
    got = []
    bridge.command.connect(lambda c, i: got.append((c, i)))
    app = QCoreApplication.instance() or QCoreApplication([])
    _req(f"{bridge.base}/api/cmd?t={TOKEN}&c=section&i=2", "POST")
    # La señal viene del hilo del servidor: llega al procesar eventos de Qt.
    app.processEvents()
    assert got == [("section", 2)]


def test_unknown_command_rejected(bridge):
    with pytest.raises(urllib.error.HTTPError) as e:
        _req(f"{bridge.base}/api/cmd?t={TOKEN}&c=rm", "POST")
    assert e.value.code == 400
