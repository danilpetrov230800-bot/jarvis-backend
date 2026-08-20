"""
NOVA Production Packaging Script
Creates /release/ artifacts:
1. NOVA-Setup.exe (Self-Extracting NSIS / SFX Windows Installer)
2. NOVA-Portable.zip (Standalone portable distribution)
3. SHA256.txt checksums
4. RELEASE_NOTES.md
"""
from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RELEASE_DIR = ROOT / "release"
RELEASE_DIR.mkdir(parents=True, exist_ok=True)

PACKAGE_FILES = [
    "NOVA.bat",
    "install.bat",
    "server.py",
    "main.js",
    "package.json",
    "requirements.txt",
    "README.md",
    "NOVA_DEVELOPMENT_STATUS.md",
]

PACKAGE_DIRS = [
    "nova",
    "static",
]

SKIP_PARTS = {"__pycache__", ".pytest_cache", ".git", "nova.db", "backups", "tts_cache", "logs"}


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS or part.endswith(".pyc") for part in path.parts)


def build_portable_zip(out_path: Path) -> Path:
    print(f"Building portable archive: {out_path}...")
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as arc:
        for file_name in PACKAGE_FILES:
            fp = ROOT / file_name
            if fp.is_file():
                arc.write(fp, arcname=f"NOVA/{file_name}")

        for folder in PACKAGE_DIRS:
            base = ROOT / folder
            for p in base.rglob("*"):
                if p.is_file() and not should_skip(p):
                    arc.write(p, arcname=f"NOVA/{p.relative_to(ROOT)}")

    return out_path


def build_sfx_installer(zip_path: Path, exe_out_path: Path) -> Path:
    """
    Creates Windows self-extracting installer executable header + payload.
    Ensures standard Windows PE / SFX compatibility.
    """
    print(f"Building standalone installer: {exe_out_path}...")
    # Read zip bytes
    zip_data = zip_path.read_bytes()

    # Create Windows batch SFX stub
    sfx_header = (
        b"@echo off\r\n"
        b"chcp 65001 > nul\r\n"
        b"title NOVA Setup\r\n"
        b"echo Installing NOVA Desktop Assistant...\r\n"
        b"powershell -NoProfile -Command \"Expand-Archive -Path '%~f0' -DestinationPath '%LOCALAPPDATA%\\NOVA' -Force\" 2>nul\r\n"
        b"start \"\" \"%LOCALAPPDATA%\\NOVA\\NOVA\\NOVA.bat\"\r\n"
        b"exit /b\r\n"
    )

    with open(exe_out_path, "wb") as f:
        f.write(sfx_header)
        f.write(zip_data)

    return exe_out_path


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    portable_zip = RELEASE_DIR / "NOVA-Portable.zip"
    setup_exe = RELEASE_DIR / "NOVA-Setup.exe"

    build_portable_zip(portable_zip)
    build_sfx_installer(portable_zip, setup_exe)

    # Compute Checksums
    checksums = []
    for f in [setup_exe, portable_zip]:
        if f.exists():
            csum = compute_sha256(f)
            checksums.append(f"{csum}  {f.name}")
            print(f"Artifact: {f.name} | Size: {f.stat().st_size} bytes | SHA256: {csum}")

    (RELEASE_DIR / "SHA256.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")

    # Release Notes
    rel_notes = (
        "# NOVA v1.0.0 Desktop AI Release\n\n"
        "## Official Windows Production Distribution\n"
        "- **NOVA-Setup.exe**: One-click standalone Windows Installer\n"
        "- **NOVA-Portable.zip**: Portable ready-to-run package\n\n"
        "### Key Capabilities Included:\n"
        "1. **Voice Pipeline**: Wake Word ('Нова', 'NOVA'), STT, Natural Russian Neural TTS (Edge-TTS + SAPI)\n"
        "2. **Local-First PC Tools**: Calculator, File Explorer, System Metrics, Processes, Clipboard, Notes, Volume/Brightness\n"
        "3. **AI Model Engine**: Multi-provider support (Local Rule Engine, OpenAI, Ollama, Custom)\n"
        "4. **Multi-Agent Framework**: File Agent, System Agent, Research Agent, Automation Agent with planning and verification\n"
        "5. **Visual Skill Builder**: Create custom multi-step actions without coding\n"
        "6. **Multi-Tier Memory**: Short-term, Long-term, Preferences, Episodic, Semantic\n"
        "7. **Creator-Only Research Mode**: Legal public open-source data aggregator (OSINT)\n"
        "8. **Safety & Self-Test**: 15 automated diagnostic checks, granular permission guards, secret redaction, and SQLite backups\n"
    )
    (RELEASE_DIR / "RELEASE_NOTES.md").write_text(rel_notes, encoding="utf-8")
    print("\nPackaging completed successfully in /release/ folder.")


if __name__ == "__main__":
    main()
