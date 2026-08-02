import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask Configuration
    PORT = int(os.getenv("PORT", 8080))
    HOST = os.getenv("HOST", "0.0.0.0")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Mock Instagram API proxy (all instaloader traffic routes here)
    MOCK_API_BASE_URL = os.getenv(
        "MOCK_API_BASE_URL",
        "https://instagram.mockapis.com/v1/api/mock/com.instgram.com",
    )

    # Instagram / instaloader Configuration
    INSTAGRAM_RATE_LIMIT = int(os.getenv("INSTAGRAM_RATE_LIMIT", 60))
    INSTAGRAM_TIMEOUT = int(os.getenv("INSTAGRAM_TIMEOUT", 30))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", 5))

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
