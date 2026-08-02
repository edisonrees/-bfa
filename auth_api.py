"""
Local Auth API Handler with Error Resistance and Rate Limiting
Tests credentials against a configurable HTTP login endpoint (default: localhost:8080)
"""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from config import config

logger = logging.getLogger(__name__)


@dataclass
class LoginResult:
    success: bool
    username: str
    password: str
    message: str = ""
    profile: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None


class LocalAuthAPIHandler:
    def __init__(self):
        self.rate_limiter = RateLimiter(config.RATE_LIMIT)
        self.executor = ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_CHECKS)
        self.login_url = config.TARGET_LOGIN_URL

    def check_credentials(self, username: str, password: str) -> LoginResult:
        """Check credentials against the configured local login endpoint."""
        try:
            self.rate_limiter.wait()

            for attempt in range(config.MAX_RETRIES):
                try:
                    response = requests.post(
                        self.login_url,
                        json={"username": username, "password": password},
                        timeout=config.REQUEST_TIMEOUT,
                        headers={"Content-Type": "application/json"},
                    )

                    if response.status_code == 200:
                        data = response.json() if response.content else {}
                        if data.get("success", True):
                            return LoginResult(
                                success=True,
                                username=username,
                                password=password,
                                message=data.get("message", "Login successful"),
                                profile=data.get("user"),
                            )

                    if response.status_code == 404:
                        return LoginResult(
                            success=False,
                            username=username,
                            password=password,
                            message="Invalid username",
                            error_type="invalid_username",
                        )

                    if response.status_code == 401:
                        return LoginResult(
                            success=False,
                            username=username,
                            password=password,
                            message="Invalid password",
                            error_type="invalid_password",
                        )

                    try:
                        data = response.json()
                        message = data.get("message", f"Login failed: HTTP {response.status_code}")
                    except ValueError:
                        message = f"Login failed: HTTP {response.status_code}"

                    return LoginResult(
                        success=False,
                        username=username,
                        password=password,
                        message=message,
                        error_type="login_error",
                    )

                except requests.ConnectionError as exc:
                    if attempt < config.MAX_RETRIES - 1:
                        time.sleep(config.RETRY_DELAY)
                        continue
                    return LoginResult(
                        success=False,
                        username=username,
                        password=password,
                        message=f"Connection error: {exc}",
                        error_type="connection_error",
                    )
                except requests.Timeout:
                    if attempt < config.MAX_RETRIES - 1:
                        time.sleep(config.RETRY_DELAY)
                        continue
                    return LoginResult(
                        success=False,
                        username=username,
                        password=password,
                        message="Request timed out",
                        error_type="connection_error",
                    )

            return LoginResult(
                success=False,
                username=username,
                password=password,
                message="Max retries exceeded",
                error_type="connection_error",
            )

        except Exception as exc:
            logger.error(f"Critical error in check_credentials: {exc}")
            return LoginResult(
                success=False,
                username=username,
                password=password,
                message=f"Critical error: {exc}",
                error_type="critical_error",
            )

    def check_credentials_batch(self, username: str, passwords: List[str]) -> List[LoginResult]:
        """Check multiple passwords for a single username."""
        results = []
        futures = []

        with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_CHECKS) as executor:
            for password in passwords:
                futures.append(executor.submit(self.check_credentials, username, password))

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    if result.success:
                        for pending in futures:
                            pending.cancel()
                        break
                except Exception as exc:
                    logger.error(f"Error in batch check: {exc}")
                    results.append(
                        LoginResult(
                            success=False,
                            username=username,
                            password="unknown",
                            message=f"Batch processing error: {exc}",
                            error_type="batch_error",
                        )
                    )

        return results


class RateLimiter:
    """Simple rate limiter to avoid overwhelming the target server."""

    def __init__(self, rate_limit: int):
        self.rate_limit = rate_limit
        self.min_interval = 60.0 / rate_limit if rate_limit > 0 else 0
        self.last_request_time = 0
        self.lock = Lock()

    def wait(self):
        if self.min_interval <= 0:
            return

        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time

            if time_since_last < self.min_interval:
                time.sleep(self.min_interval - time_since_last)

            self.last_request_time = time.time()


auth_handler = LocalAuthAPIHandler()
