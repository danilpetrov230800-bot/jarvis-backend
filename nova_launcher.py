"""Windows GUI entry point packaged by PyInstaller."""

from __future__ import annotations

import sys

from run import main


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Production GUI applications must not expose a console traceback.
        sys.exit(1)
