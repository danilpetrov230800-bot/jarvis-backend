# jarvis-backend → NOVA

This repository now contains **NOVA** — Neural Operational & Virtual Assistant.

See [nova/README.md](nova/README.md) for user documentation.

## Quick Start (Development)

```bash
cd nova/backend
pip install -r requirements.txt
PYTHONPATH=. python3 -m nova.main

# In another terminal:
cd nova/frontend
npm install
npm run dev:vite
```

## Release

Build artifacts are in `nova/release/`:
- `NOVA-Portable.zip` — portable bundle
- `NOVA-Setup.exe` — Windows installer (build on Windows)

See [nova/NOVA_DEVELOPMENT_STATUS.md](nova/NOVA_DEVELOPMENT_STATUS.md) for full status.
