import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    PORT = int(os.getenv("PORT", 8080))
    HOST = os.getenv("HOST", "0.0.0.0")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    MOCK_API_BASE_URL = os.getenv(
        "MOCK_API_BASE_URL",
        "https://instagram.mockapis.com/v1/api/mock/com.instgram.com",
    )

    INSTAGRAM_RATE_LIMIT = int(os.getenv("INSTAGRAM_RATE_LIMIT", 60))
    INSTAGRAM_TIMEOUT = int(os.getenv("INSTAGRAM_TIMEOUT", 30))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", 5))

    MAX_CONCURRENT_CHECKS = int(os.getenv("MAX_CONCURRENT_CHECKS", 5))
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))
    MAX_PASSWORDS = int(os.getenv("MAX_PASSWORDS", 5000))

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    ALLOWED_EXTENSIONS = {"txt", "csv", "json"}

    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-in-production")
    SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", 3600))

    REPLICA_ID = os.getenv("REPLICA_ID", "0")
    TOTAL_REPLICAS = int(os.getenv("TOTAL_REPLICAS", 1))
    WORKER_COUNT = int(os.getenv("WORKER_COUNT", 4))

    APP_NAME = "MOCKA"
    APP_TAGLINE = "Mock Instagram auth lab"


config = Config()
