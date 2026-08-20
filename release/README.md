# Release files

These files are the production Windows build from GitHub Actions `windows-release`.

- `NOVA-Setup.exe` — installer (Start Menu, desktop shortcut, uninstall)
- `NOVA-Portable.zip` — portable `NOVA.exe`
- `SHA256.txt` — checksums
- `RELEASE_NOTES.md`

SHA256:

```
NOVA-Setup.exe  297A67F47131002C069A1975FC3409389C2659DD46ADF3E08A79EA5A22BCFC4F
NOVA-Portable.zip 67A1E6658D18A6892C28DBFCBE717F1252B86D1712A149DB07AFA02110B48889
```

Verified on GitHub Actions `windows-latest`: package, launch, silent install, uninstall.
