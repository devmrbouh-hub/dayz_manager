"""RCON say messages should appear in chat buffer."""

from unittest.mock import MagicMock, patch

from src.core.rcon_client import RconClient
from tests.conftest import FakeConfig, make_server


def test_bilingual_say_injects_chat(tmp_path):
    server = make_server(tmp_path)
    cfg = FakeConfig({"settings": {}, "servers": [server]})
    rcon = RconClient(cfg)
    injected = []

    def capture(server_arg, text, player="Server", channel="Broadcast"):
        injected.append({"text": text, "player": player, "channel": channel})

    rcon.set_chat_inject(capture)
    rcon_cfg = {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 2305,
        "password": "test",
        "timeout": 5,
    }

    with patch.object(rcon, "_get_server_rcon_config", return_value=rcon_cfg), \
         patch.object(rcon, "_execute", side_effect=[(True, "ok", None), (True, "ok", None)]), \
         patch("src.core.rcon_client.time.sleep"):
        ok = rcon.send_bilingual_say(server, "Привет RU", "Hello EN")

    assert ok is True
    assert len(injected) == 2
    assert injected[0]["text"] == "Привет RU"
    assert injected[0]["channel"] == "Global"
    assert injected[0]["player"] == "Server"
    assert injected[1]["text"] == "Hello EN"
    assert injected[1]["channel"] == "Global"
