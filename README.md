# MOCKA — Mock Instagram Auth Lab

Premium web UI for auth-testing workflows using **instaloader**, with every Instagram HTTP request rewritten to a mock demo API.

## What it does

- Upload / paste / sample wordlists
- Run credential checks through `MOCK_API_BASE_URL`
- Live progress, ETA, cancel, export, clear finished
- Never talks to production Instagram while the mock proxy is enabled

## Default mock route

```
https://instagram.mockapis.com/v1/api/mock/com.instgram.com
```

## Quick start

```bash
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
py -3 app.py
```

Open `http://localhost:8080`.

## QoL features

- Drag-and-drop wordlists
- Paste passwords without a file
- Built-in sample list
- Stop on first hit
- Cancel / delete / export JSON
- Keyboard shortcut: `Ctrl/⌘ + Enter`
- Live stats + status filters
- Mock-target badge always visible

## Env

| Variable | Default |
|----------|---------|
| `MOCK_API_BASE_URL` | `https://instagram.mockapis.com/v1/api/mock/com.instgram.com` |
| `INSTAGRAM_RATE_LIMIT` | `60` |
| `MAX_CONCURRENT_CHECKS` | `5` |
| `MAX_PASSWORDS` | `5000` |

## Tests

```bash
py -3 test_app.py
```

## Security

Authorized mock/demo testing only. Do not point `MOCK_API_BASE_URL` at production Instagram.
