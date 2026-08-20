# Testing

Local verification:

```bash
python -m pytest -q
```

The Windows production workflow runs:

1. all unit, API, permission, malformed-input, traversal, backup, and stress tests;
2. PyInstaller production packaging;
3. a packaged executable health test without an API key;
4. Inno Setup compilation;
5. silent installation into a clean per-user application directory;
6. launch and diagnostics against the installed executable;
7. process shutdown and silent uninstall;
8. portable ZIP and SHA-256 generation.

Windows-only microphone, SAPI, WebView2, shortcuts, and uninstaller behavior must
be accepted only from that workflow, not inferred from Linux development mode.
