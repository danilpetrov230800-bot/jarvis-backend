from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from installer.package import relative_names, write_zip


def test_nova_bat_is_ascii_and_calls_bootstrap():
    data = (ROOT / "NOVA.bat").read_bytes()
    assert data.isascii()
    text = data.decode("ascii")
    assert "installer\\bootstrap.ps1" in text
    assert "ExecutionPolicy Bypass" in text
    for line in text.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("echo"):
            assert "(" not in stripped


def test_jarvis_bat_is_ascii_wrapper():
    data = (ROOT / "JARVIS.bat").read_bytes()
    assert data.isascii()
    assert "NOVA.bat" in data.decode("ascii")


def test_bootstrap_downloads_embeddable_python():
    ps1 = (ROOT / "installer" / "bootstrap.ps1").read_bytes()
    assert ps1.isascii()
    text = ps1.decode("ascii")
    assert "3.12.10" in text
    assert "embed-amd64.zip" in text
    assert "get-pip.py" in text
    assert "CreateShortcut" in text
    assert "NOVA.bat" in text
    assert "Unblock-File" in text


def test_package_contains_runtime_files_not_tests(tmp_path):
    names = relative_names()
    assert "NOVA.bat" in names
    assert "JARVIS.bat" in names
    assert "run.py" in names
    assert "installer/bootstrap.ps1" in names
    assert "static/index.html" in names
    assert "jarvis/app.py" in names
    assert not any(name.startswith("tests/") for name in names)

    zpath = tmp_path / "NOVA-windows.zip"
    write_zip(zpath)
    assert zpath.stat().st_size > 1000


def test_home_has_first_run_wizard(client):
    html = client.get("/").text
    assert "NOVA" in html
    assert "setupKey" in html
    assert "console.groq.com/keys" in html
