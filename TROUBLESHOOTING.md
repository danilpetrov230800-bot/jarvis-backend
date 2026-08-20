# Troubleshooting

- **NOVA opens in a browser:** the native WebView2 component was unavailable.
  Install current Windows updates or the Microsoft WebView2 Runtime, then restart NOVA.
- **Microphone is unavailable:** enable `MICROPHONE` in Permissions and allow
  microphone access for desktop applications in Windows Privacy settings.
- **No spoken answer:** text mode remains available. Run NOVA Diagnostics to test TTS.
- **AI provider unavailable:** local deterministic tools continue in Offline Mode.
  Check the provider URL/key in Settings.
- **A file operation is denied:** enable only the required permission. NOVA confines
  file access to the current Windows user profile.

Technical details are available in Logs and `%LOCALAPPDATA%\NOVA\nova.log`.
