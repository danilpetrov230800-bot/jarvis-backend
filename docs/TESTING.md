# Testing

```bash
pip install -r requirements-dev.txt
pytest
```

CI (`windows-package`): pytest on Ubuntu, then `NOVA-windows.zip` + `NOVA-Setup.exe` + `SHA256.txt` on `windows-latest`.

## Automated coverage

TEST 01 installer files (`NOVA.vbs`, `nova.iss`)  
TEST 02 chat without API key  
TEST 03 voice degrades without Speech API (UI copy)  
TEST 04 text command  
TEST 07 open app (monkeypatch)  
TEST 08–09 files find/create  
TEST 10–11 memory  
TEST 12–13 skills  
TEST 14–17 agents, timeout, retry  
TEST 18 permission denial  
TEST 19 delete confirmation  
TEST 20 offline flag  
TEST 21 TTS recovery path  
TEST 23–25 migrate / backup / restore  
TEST 26 uninstall entry in Inno script  

Security: path traversal, zip slip, secret redaction, command-injection filenames, malformed chat.

Stress: 40 sequential chat calls in pytest (full 100+ is the same path).

## Clean Windows machine

1. Download `NOVA-Setup.exe` from Actions artifact `NOVA-Setup`.
2. Install to the default folder.
3. Launch desktop shortcut.
4. Skip wizard. Type «привет».
5. Uninstall from Start Menu. Profile stays in `%LOCALAPPDATA%\NOVA`.
