# NOVA Testing

## Self-Test

```bash
cd nova
python tests/self_test.py
```

## Unit Tests

```bash
cd nova/backend
pip install -r requirements.txt pytest pytest-asyncio
pytest ../tests/unit/ -v
```

## Test Scenarios

| # | Test | Status |
|---|------|--------|
| 01 | Launch after install | Manual (Windows) |
| 02 | Launch without API key | Automated |
| 03 | Launch without microphone | Automated |
| 04 | Text command | Automated |
| 05 | Voice command | Manual (Windows + mic) |
| 06 | Wake word | Manual (Windows + mic) |
| 07 | Launch application | Manual (Windows) |
| 08 | File search | Automated |
| 09 | Create file | Automated (with permission) |
| 10 | Memory save | Automated |
| 11 | Memory recall | Automated |
| 12 | Create Skill | Automated |
| 13 | Execute Skill | Automated |
| 14 | Create Agent | Automated |
| 15 | Agent task | Automated |
| 16 | Agent timeout | Automated |
| 17 | Agent retry | Automated |
| 18 | Permission denial | Automated |
| 19 | Dangerous action confirmation | Automated |
| 20 | Offline mode | Automated |
| 21 | Crash recovery | Manual |
| 22 | Restart NOVA | Manual |
| 23 | Upgrade | Manual |
| 24 | Backup | Automated |
| 25 | Restore | Automated |
| 26 | Uninstall | Manual (Windows) |

## Security Tests

- Permission bypass: tools check permissions before execution
- Path traversal: file tools validate paths
- Secret leakage: logs redact API keys and tokens
- Command injection: calculator uses restricted eval

## Stress Test

Run 100+ messages via chat API:

```bash
for i in $(seq 1 100); do
  curl -s -X POST http://127.0.0.1:47821/api/chat \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"test $i\"}" > /dev/null
done
```
