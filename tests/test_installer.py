from pathlib import Path


def test_installer_script_exists():
    root = Path(__file__).resolve().parents[1]
    assert (root / "packaging" / "nova.iss").exists()
    assert (root / ".github" / "workflows" / "windows-release.yml").exists()
    iss = (root / "packaging" / "nova.iss").read_text(encoding="utf-8")
    assert "NOVA-Setup" in iss
    assert "{uninstallexe}" in iss or "Uninstall" in iss
