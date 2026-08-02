"""
Instagram API Handler routed through mockapis demo proxy.
Uses instaloader; all HTTP traffic is rewritten to instagram.mockapis.com.
"""

import random
import time
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from config import config
from mock_proxy import install_mock_proxy

install_mock_proxy()

from instaloader import (  # noqa: E402
    Instaloader,
    BadCredentialsException,
    ConnectionException,
    InstaloaderException,
    LoginException,
    LoginRequiredException,
    ProfileNotExistsException,
)
from instaloader.structures import Profile  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass
class LoginResult:
    success: bool
    username: str
    password: str
    message: str = ""
    profile: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None


class InstagramAPIHandler:
    def __init__(self):
        self.rate_limiter = RateLimiter(config.INSTAGRAM_RATE_LIMIT)
        self.executor = ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_CHECKS)
        self.mock_base_url = config.MOCK_API_BASE_URL

    def create_session(self) -> Instaloader:
        """Create an instaloader session; requests go through the mock proxy."""
        loader = Instaloader(
            request_timeout=config.INSTAGRAM_TIMEOUT,
            max_connection_attempts=config.MAX_RETRIES,
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            save_metadata=False,
            post_metadata_txt_pattern="",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            quiet=True,
            sleep=False,
        )

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        ]
        loader.context.user_agent = random.choice(user_agents)
        return loader

    def check_credentials(self, username: str, password: str) -> LoginResult:
        """Check credentials via instaloader against the mock Instagram API."""
        try:
            self.rate_limiter.wait()
            loader = self.create_session()

            try:
                loader.login(username, password)

                try:
                    profile = Profile.from_username(loader.context, username)
                    if profile:
                        return LoginResult(
                            success=True,
                            username=username,
                            password=password,
                            message="Login successful (mock API)",
                            profile={
                                "username": profile.username,
                                "full_name": profile.full_name,
                                "followers": profile.followers,
                                "following": profile.followees,
                                "posts": profile.mediacount,
                                "bio": profile.biography,
                                "is_verified": profile.is_verified,
                                "profile_pic_url": profile.profile_pic_url,
                            },
                        )
                except Exception as exc:
                    logger.warning(f"Profile fetch failed for {username}: {exc}")
                    return LoginResult(
                        success=True,
                        username=username,
                        password=password,
                        message="Login successful (profile fetch failed)",
                        error_type="profile_fetch_error",
                    )

            except (BadCredentialsException, LoginRequiredException) as exc:
                error_msg = str(exc)
                if "invalid user" in error_msg.lower() or "does not exist" in error_msg.lower():
                    return LoginResult(
                        success=False,
                        username=username,
                        password=password,
                        message="Invalid username",
                        error_type="invalid_username",
                    )
                if "password" in error_msg.lower() or "credentials" in error_msg.lower():
                    return LoginResult(
                        success=False,
                        username=username,
                        password=password,
                        message="Invalid password",
                        error_type="invalid_password",
                    )
                return LoginResult(
                    success=False,
                    username=username,
                    password=password,
                    message=f"Login error: {error_msg}",
                    error_type="login_error",
                )
            except LoginException as exc:
                error_msg = str(exc)
                if "does not exist" in error_msg.lower():
                    return LoginResult(
                        success=False,
                        username=username,
                        password=password,
                        message="Invalid username",
                        error_type="invalid_username",
                    )
                return LoginResult(
                    success=False,
                    username=username,
                    password=password,
                    message=f"Login error: {error_msg}",
                    error_type="login_error",
                )
            except ProfileNotExistsException:
                return LoginResult(
                    success=False,
                    username=username,
                    password=password,
                    message="Invalid username",
                    error_type="invalid_username",
                )
            except ConnectionException as exc:
                return LoginResult(
                    success=False,
                    username=username,
                    password=password,
                    message=f"Connection error: {exc}",
                    error_type="connection_error",
                )
            except InstaloaderException as exc:
                return LoginResult(
                    success=False,
                    username=username,
                    password=password,
                    message=f"Mock Instagram API error: {exc}",
                    error_type="instagram_error",
                )
            except Exception as exc:
                logger.error(f"Unexpected error for {username}: {exc}")
                return LoginResult(
                    success=False,
                    username=username,
                    password=password,
                    message=f"Unexpected error: {exc}",
                    error_type="unknown_error",
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

    async def check_credentials_async(self, username: str, password: str) -> LoginResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.check_credentials, username, password)


class RateLimiter:
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


instagram_handler = InstagramAPIHandler()
