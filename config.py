import os
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class Config:
    PORT = _int("PORT", 8080)
    HOST = os.getenv("HOST", "0.0.0.0")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    MOCK_API_BASE_URL = os.getenv(
        "MOCK_API_BASE_URL",
        "https://instagram.mockapis.com/v1/api/mock/com.instgram.com",
    )

    INSTAGRAM_RATE_LIMIT = _int("INSTAGRAM_RATE_LIMIT", 60)
    INSTAGRAM_TIMEOUT = _int("INSTAGRAM_TIMEOUT", 10)
    MAX_RETRIES = _int("MAX_RETRIES", 2)
    RETRY_DELAY = _int("RETRY_DELAY", 1)

    MAX_CONCURRENT_CHECKS = _int("MAX_CONCURRENT_CHECKS", 5)
    BATCH_SIZE = _int("BATCH_SIZE", 100)
    # 100 million passwords hard cap
    MAX_PASSWORDS = _int("MAX_PASSWORDS", 100_000_000)
    # Large wordlists need big uploads (default 2 GiB)
    MAX_FILE_SIZE = _int("MAX_FILE_SIZE", 2 * 1024 * 1024 * 1024)
    # Below this, keep passwords in memory; above, stream from disk
    STREAM_THRESHOLD = _int("STREAM_THRESHOLD", 50_000)

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    ALLOWED_EXTENSIONS = {"txt", "csv", "json"}

    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-in-production")
    SESSION_TIMEOUT = _int("SESSION_TIMEOUT", 3600)

    REPLICA_ID = os.getenv("REPLICA_ID", os.getenv("RAILWAY_REPLICA_ID", "0"))
    TOTAL_REPLICAS = _int("TOTAL_REPLICAS", _int("RAILWAY_REPLICA_TOTAL", 1))
    WORKER_COUNT = _int("WORKER_COUNT", 4)

    APP_NAME = "MOCKA"
    APP_TAGLINE = "Mock Instagram auth lab"


config = Config()
