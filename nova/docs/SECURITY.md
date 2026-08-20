# NOVA Security

## Secret Storage

- API keys encrypted with Fernet (machine-bound key)
- Never stored in source code
- Never logged (redaction patterns in logger)
- User can delete/replace keys in Settings

## Permissions

Each tool requires explicit permission:

| Permission | Risk |
|-----------|------|
| READ_FILES | Low |
| WRITE_FILES | Medium |
| DELETE_FILES | High |
| RUN_APPLICATIONS | Medium |
| SYSTEM_SETTINGS | High |
| NETWORK | Low |
| SCREEN_CONTROL | High |
| MICROPHONE | Low |
| CAMERA | High |
| RESEARCH_MODE | High |

Dangerous permissions marked in UI.

## Dangerous Actions

File deletion, mass operations require confirmation dialog.

## Audit Log

All security events logged to `audit.log` (no secrets).

## Research Mode

- Separate permission required
- Only public/open sources
- No bypass of auth, paywall, CAPTCHA
- All searches logged

## What NOVA Does NOT Do

- Execute arbitrary remote code
- Bypass Windows security
- Hide malicious actions
- Store passwords in plaintext
- Auto-execute dangerous operations
