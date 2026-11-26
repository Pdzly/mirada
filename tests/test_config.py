import json

from mirada import config
from mirada.config import DEFAULTS, parse_sections, reading_minutes, sanitize


def test_sanitize_defaults_for_garbage():
    for raw in (None, [], "x", 3):
        conf = sanitize(raw)
        assert {k: v for k, v in conf.items() if k != "remote_token"} == \
               {k: v for k, v in DEFAULTS.items() if k != "remote_token"}


def test_sanitize_drops_wrong_types_and_unknown_keys():
    conf = sanitize({"font_size": "grande", "voice": 1, "mode": "raro", "zzz": 1,
                     "float_geometry": [1, 2, 3]})
    assert conf["font_size"] == DEFAULTS["font_size"]
    assert conf["voice"] is DEFAULTS["voice"]
    assert conf["mode"] == "notch"
    assert conf["float_geometry"] == DEFAULTS["float_geometry"]
    assert "zzz" not in conf


def test_sanitize_clamps_ranges():
    conf = sanitize({"speed": 10_000, "font_size": 1, "remote_port": 80, "sensitivity": 55.7})
    assert conf["speed"] == 300
    assert conf["font_size"] == 10
    assert conf["remote_port"] == 1024
    assert conf["sensitivity"] == 55


def test_short_token_is_replaced():
    assert len(sanitize({"remote_token": "abc"})["remote_token"]) >= 16
    tok = "x" * 22
    assert sanitize({"remote_token": tok})["remote_token"] == tok


def test_defaults_not_shared_between_calls():
    a = sanitize({})
    a["float_geometry"][0] = 999
    assert sanitize({})["float_geometry"][0] == DEFAULTS["float_geometry"][0]


def test_load_and_save_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.load_conf()["mode"] == "notch"          # sin archivo
    conf = config.load_conf()
    conf["speed"] = 77
    config.save_conf(conf)
    assert json.loads((tmp_path / "mirada" / "config.json").read_text())["speed"] == 77
    assert config.load_conf()["speed"] == 77


def test_load_corrupt_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "mirada").mkdir()
    (tmp_path / "mirada" / "config.json").write_text("{no es json")
    assert config.load_conf()["speed"] == DEFAULTS["speed"]


def test_parse_sections():
    text = "# Uno\nhola\n\n## Dos\n#\nfin"
    assert parse_sections(text) == [("Uno", 0), ("Dos", 3), ("Sección 3", 4)]
    assert parse_sections("") == []


def test_reading_minutes():
    assert reading_minutes("palabra " * 140) == 1.0
