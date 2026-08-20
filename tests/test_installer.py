from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from installer.package import relative_names, write_zip


def test_launcher_calls_bootstrap():
    bat = (ROOT / "JARVIS.bat").read_text(encoding="utf-8", errors="replace")
    assert "installer\\bootstrap.ps1" in bat
    assert "ExecutionPolicy Bypass" in bat


def test_bootstrap_downloads_embeddable_python():
    ps1 = (ROOT / "installer" / "bootstrap.ps1").read_text(encoding="utf-8-sig")
    assert "3.12.10" in ps1
    assert "embed-amd64.zip" in ps1
    assert "safesearch" not in ps1
    assert "get-pip.py" in ps1
    assert "CreateShortcut" in ps1
    assert "Unblock-File" in ps1


def test_package_contains_runtime_files_not_tests(tmp_path):
    names = relative_names()
    assert "JARVIS.bat" in names
    assert "run.py" in names
    assert "installer/bootstrap.ps1" in names
    assert "installer/__init__.py" in names
    assert "installer/package.py" in names
    assert "static/index.html" in names
    assert "jarvis/app.py" in names
    assert "КАК ЗАПУСТИТЬ.txt" in names
    assert not any(name.startswith("tests/") for name in names)
    assert not any(".git/" in name for name in names)

    zpath = tmp_path / "JARVIS-windows.zip"
    write_zip(zpath)
    assert zpath.stat().st_size > 1000


def test_home_has_first_run_wizard(client):
    html = client.get("/").text
    assert "Первый запуск" in html
    assert "setupKey" in html
    assert "console.groq.com/keys" in html
