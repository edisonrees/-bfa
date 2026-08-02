# Local Auth BFa Tool for Railway

A local authentication security testing tool with a web interface, designed for Railway deployment with replica support. Targets **localhost:8080** (or any configurable HTTP login endpoint) — not external services.

## Features

- **Web Interface**: Clean, responsive UI on port 8080
- **Password File Upload**: Supports `.txt`, `.csv`, and `.json` formats
- **Multiple Username Support**: Test against single or multiple usernames
- **Local Target**: Built-in `/api/login` endpoint on `http://localhost:8080`
- **Configurable Target**: Point at any local auth API via env vars
- **Railway Optimized**: Works with Railway replicas and scaling
- **Real-time Progress**: Live updates on task status and results

## Built-in Demo Login

The app includes a local login endpoint for testing:

- **URL**: `POST http://localhost:8080/api/login`
- **Body**: `{"username": "admin", "password": "secret123"}`
- Override via `DEMO_USERNAME` and `DEMO_PASSWORD` env vars

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open `http://localhost:8080` in your browser.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Web interface port |
| `TARGET_BASE_URL` | `http://localhost:8080` | Auth server base URL |
| `TARGET_LOGIN_PATH` | `/api/login` | Login endpoint path |
| `DEMO_USERNAME` | `admin` | Built-in demo username |
| `DEMO_PASSWORD` | `secret123` | Built-in demo password |
| `RATE_LIMIT` | 300 | Requests per minute to target |
| `MAX_CONCURRENT_CHECKS` | 10 | Concurrent password checks |

## API Endpoints

- `GET /` — Web interface
- `GET /health` — Health check
- `POST /api/login` — Built-in local login target
- `GET /api/tasks` — List tasks
- `POST /api/tasks` — Start a new auth test
- `POST /api/preview` — Preview password file

## Security Notice

Use only against systems you own or have explicit permission to test. Unauthorized access to computer systems may be illegal in your jurisdiction.

## License

Educational and authorized security testing purposes only.
