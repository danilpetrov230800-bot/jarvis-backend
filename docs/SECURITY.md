# Security

- API keys live only in the local profile (`settings.json`), never in source.
- Keys are masked in `/api/settings` and stripped from logs (`gsk_`, `sk-`, `sk-or-`).
- File tools stay inside Desktop/Documents/Downloads/Pictures/Videos and the NOVA profile.
- `DELETE_FILES`, `RESEARCH`, and `CAMERA` are off by default.
- Deletes need an explicit confirm flag or UI confirmation.
- Restore accepts zip files only from the NOVA data folder; zip-slip (`..`) is rejected.
- Research mode uses public web search only. No login bypass, CAPTCHA bypass, paywall bypass, or hidden monitoring.
- Dangerous permissions are marked in the UI.
- Arbitrary remote code execution is not exposed as a tool.
