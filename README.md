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

## Scale / caps

| Variable | Default | Notes |
|----------|---------|-------|
| `MAX_PASSWORDS` | `100000000` | Hard cap (100 million) |
| `MAX_FILE_SIZE` | `2147483648` | 2 GiB uploads |
| `STREAM_THRESHOLD` | `50000` | Above this, stream from disk |
| `TOTAL_REPLICAS` / `RAILWAY_REPLICA_TOTAL` | `1` | Shard wordlist by index |
| `REPLICA_ID` / `RAILWAY_REPLICA_ID` | `0` | This replica's shard |

Replicas process `index % TOTAL_REPLICAS == REPLICA_ID`. For multi-replica deploys, mount a shared `UPLOAD_FOLDER` volume so every replica can read the same wordlist.

## CSV-style TXT

These all work:

```
pass1,pass2,pass3
```

```
pass1
pass2,pass3,pass4
user:secret,backup
```

## ETA

Live board shows rolling rate (attempts/s) and human ETA (`12m 4s`). With multiple replicas, shard label + cluster ETA are shown.

## Tests

```bash
py -3 test_app.py
```

## Security

Authorized mock/demo testing only. Do not point `MOCK_API_BASE_URL` at production Instagram.
