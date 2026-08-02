# Instagram Mock BFa Tool

Web UI for credential testing using **instaloader**, with all Instagram HTTP traffic routed through a mock demo API — never hitting real `instagram.com`.

## Mock proxy

All `www.instagram.com` and `i.instagram.com` requests are rewritten to:

```
https://instagram.mockapis.com/v1/api/mock/com.instgram.com/
```

Example:

| Original | Routed to |
|----------|-----------|
| `https://www.instagram.com/api/v1/web/accounts/login/ajax/` | `https://instagram.mockapis.com/v1/api/mock/com.instgram.com/api/v1/web/accounts/login/ajax/` |

Configure via `MOCK_API_BASE_URL` in `.env`.

## Quick start

```bash
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
py -3 app.py
```

Open `http://localhost:8080`.

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCK_API_BASE_URL` | `https://instagram.mockapis.com/v1/api/mock/com.instgram.com` | Mock Instagram API base |
| `INSTAGRAM_RATE_LIMIT` | 60 | Requests per minute |
| `INSTAGRAM_TIMEOUT` | 30 | Request timeout (seconds) |
| `MAX_CONCURRENT_CHECKS` | 10 | Parallel password checks |

## Stack

- Flask web UI
- instaloader for Instagram-style login/profile flow
- `mock_proxy.py` patches `requests.Session` to rewrite URLs

## Tests

```bash
py -3 test_app.py
```

## Security

For authorized testing against mock/demo endpoints only. Do not point at production Instagram.
