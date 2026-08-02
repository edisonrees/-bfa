import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask Configuration
    PORT = int(os.getenv("PORT", 8080))
    HOST = os.getenv("HOST", "0.0.0.0")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Target Auth Server Configuration
    TARGET_BASE_URL = os.getenv("TARGET_BASE_URL", "http://localhost:8080")
    TARGET_LOGIN_PATH = os.getenv("TARGET_LOGIN_PATH", "/api/login")
    TARGET_LOGIN_URL = f"{TARGET_BASE_URL.rstrip('/')}{TARGET_LOGIN_PATH}"

    # Demo credentials for the built-in local login endpoint
    DEMO_USERNAME = os.getenv("DEMO_USERNAME", "admin")
    DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "secret123")

    # Request Configuration
    RATE_LIMIT = int(os.getenv("RATE_LIMIT", 300))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 10))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", 1))

    # BFa Configuration
    MAX_CONCURRENT_CHECKS = int(os.getenv("MAX_CONCURRENT_CHECKS", 10))
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))

    # File Upload Configuration
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    ALLOWED_EXTENSIONS = {"txt", "csv", "json"}

    # Security Configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-in-production")
    SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", 3600))

    # Railway Configuration
    REPLICA_ID = os.getenv("REPLICA_ID", "0")
    TOTAL_REPLICAS = int(os.getenv("TOTAL_REPLICAS", 1))

    # Performance Configuration
    WORKER_COUNT = int(os.getenv("WORKER_COUNT", 4))


config = Config()
