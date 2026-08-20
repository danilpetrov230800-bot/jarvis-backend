import sys

from nova.boot import prepare, write_crash

prepare()

from nova.__main__ import main

if __name__ == "__main__":
    try:
        raise SystemExit(main() or 0)
    except Exception as exc:
        write_crash(exc)
        sys.exit(1)
