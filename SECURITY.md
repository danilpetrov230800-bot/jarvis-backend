# Security

- API keys are protected with Windows DPAPI and never returned by the API.
- Installed files are immutable; profile data is stored per user.
- Dangerous permissions are disabled by default and changes are audited.
- Deletes require both `DELETE_FILES` and explicit confirmation.
- File tools reject paths outside the current user's profile.
- Restore rejects absolute paths, traversal, and unknown archive entries.
- Agent execution has hard timeout and retry ceilings.
- The local service binds to loopback and the UI uses same-origin requests.
- Logs contain action metadata, not API keys, passwords, or tokens.

Creator Research is limited to public sources and does not bypass authentication,
CAPTCHA, paywalls, privacy controls, or access restrictions.
