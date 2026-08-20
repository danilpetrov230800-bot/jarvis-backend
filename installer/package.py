from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INCLUDE_FILES = (
    "NOVA.bat",
    "JARVIS.bat",
    "run.py",
    "nova_launcher.py",
    "requirements.txt",
    ".env.example",
    "README.md",
    "INSTALL.md",
    "ARCHITECTURE.md",
    "TESTING.md",
    "TROUBLESHOOTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "КАК ЗАПУСТИТЬ.txt",
    "start.bat",
    "start.sh",
)

INCLUDE_DIRS = (
    "jarvis",
    "nova_core",
    "static",
    "installer",
    "api",
    "data",
)

SKIP_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "runtime",
    "dist",
    ".git",
    "tts_cache",
}


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS or part.endswith(".pyc") for part in path.parts)


def iter_package_files() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_FILES:
        path = ROOT / name
        if path.is_file():
            files.append(path)
    for folder in INCLUDE_DIRS:
        base = ROOT / folder
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and not should_skip(path):
                files.append(path)
    return files


def relative_names() -> list[str]:
    return sorted(path.relative_to(ROOT).as_posix() for path in iter_package_files())


def write_zip(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in iter_package_files():
            archive.write(path, arcname=Path("NOVA") / path.relative_to(ROOT))
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack NOVA ZIP for PC")
    parser.add_argument(
        "-o",
        "--output",
        default=str(ROOT / "dist" / "NOVA-windows.zip"),
        help="Path to zip",
    )
    args = parser.parse_args()
    out = write_zip(Path(args.output))
    print(f"Ready: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
