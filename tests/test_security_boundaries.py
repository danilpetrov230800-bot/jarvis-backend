import socket

import pytest

from jarvis import desktop, search
import run
from run import safe_host


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "http://127.0.0.1/admin",
    "http://[::1]/",
    "http://169.254.169.254/latest/meta-data",
    "http://user:password@example.com/",
])
async def test_ssrf_targets_are_rejected(url, monkeypatch):
    monkeypatch.setattr(
        search.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
    )
    with pytest.raises(ValueError):
        await search.validate_public_url(url)


@pytest.mark.asyncio
async def test_public_url_is_allowed(monkeypatch):
    monkeypatch.setattr(
        search.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    await search.validate_public_url("https://example.com/page")


def test_backend_bind_is_loopback_only():
    assert safe_host("127.0.0.1") == "127.0.0.1"
    assert safe_host("localhost") == "localhost"
    assert safe_host("0.0.0.0") == "127.0.0.1"
    assert safe_host("192.168.1.5") == "127.0.0.1"


def test_unknown_executable_is_not_launched(monkeypatch):
    monkeypatch.setattr(desktop, "require", lambda _permission: None)
    monkeypatch.setattr(desktop, "_win", lambda: True)
    monkeypatch.setattr(desktop, "installed_app_index", lambda: {})
    monkeypatch.setattr(desktop.shutil, "which", lambda name: f"C:/{name}")
    assert desktop.open_app("untrusted.exe") is None


def test_openapi_surfaces_are_disabled(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_windowed_launcher_needs_no_console(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "LOG", tmp_path / "nova.log")
    monkeypatch.setattr(run.sys, "stdout", None)
    monkeypatch.setattr(run.sys, "stderr", None)
    run._setup_logging()
    run.console("not visible")
    run.logging.info("windowed mode")
    assert "windowed mode" in run.LOG.read_text("utf-8")
