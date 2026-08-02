#!/usr/bin/env python3
"""Test suite for Instagram Mock BFa application."""

import unittest
import tempfile
import os
import time
from unittest.mock import patch, MagicMock
from app import app
from instagram_api import instagram_handler, LoginResult, RateLimiter
from mock_proxy import rewrite_instagram_url, install_mock_proxy
from file_processor import password_processor
from models import BFaTask, task_manager
from config import config


class TestInstagramMockBFa(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        if os.path.exists(config.UPLOAD_FOLDER):
            for filename in os.listdir(config.UPLOAD_FOLDER):
                filepath = os.path.join(config.UPLOAD_FOLDER, filename)
                try:
                    if os.path.isfile(filepath):
                        os.unlink(filepath)
                except OSError:
                    pass

        for task in task_manager.get_all_tasks():
            try:
                task_manager.delete_task(task.task_id)
            except Exception:
                pass

    def test_mock_url_rewrite(self):
        original = "https://www.instagram.com/api/v1/web/accounts/login/ajax/"
        expected = (
            "https://instagram.mockapis.com/v1/api/mock/com.instgram.com/"
            "api/v1/web/accounts/login/ajax/"
        )
        self.assertEqual(rewrite_instagram_url(original), expected)

    def test_mock_url_rewrite_iphone_host(self):
        original = "https://i.instagram.com/api/v1/users/test/info/"
        expected = (
            "https://instagram.mockapis.com/v1/api/mock/com.instgram.com/"
            "api/v1/users/test/info/"
        )
        self.assertEqual(rewrite_instagram_url(original), expected)

    def test_mock_proxy_installs_once(self):
        install_mock_proxy()
        install_mock_proxy()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data["status"], "healthy")
        self.assertIn("target_url", data)
        self.assertEqual(data["target_url"], config.MOCK_API_BASE_URL)

    def test_main_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Instagram Mock BFa Tool", response.data)

    def test_tasks_endpoint_empty(self):
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 0)

    def test_file_preview_txt(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("password1\npassword2\npassword3")
            temp_file = f.name

        try:
            with open(temp_file, "rb") as f:
                response = self.client.post("/api/preview", data={"passwordFile": (f, "test.txt")})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["password_count"], 3)
        finally:
            os.unlink(temp_file)

    def test_rate_limiter(self):
        limiter = RateLimiter(300)
        start = time.time()
        for _ in range(5):
            limiter.wait()
        self.assertGreaterEqual(time.time() - start, 0.8)

    def test_instagram_handler_mock_base(self):
        self.assertEqual(instagram_handler.mock_base_url, config.MOCK_API_BASE_URL)

    def test_session_creation(self):
        session = instagram_handler.create_session()
        self.assertIsNotNone(session)
        self.assertEqual(type(session).__name__, "Instaloader")

    def test_check_credentials_mocked(self):
        mock_profile = MagicMock()
        mock_profile.username = "demo"
        mock_profile.full_name = "Demo User"
        mock_profile.followers = 100
        mock_profile.followees = 50
        mock_profile.mediacount = 10
        mock_profile.biography = "bio"
        mock_profile.is_verified = False
        mock_profile.profile_pic_url = "http://example.com/pic.jpg"

        mock_loader = MagicMock()
        with patch.object(instagram_handler, "create_session", return_value=mock_loader), patch(
            "instagram_api.Profile.from_username", return_value=mock_profile
        ):
            mock_loader.login.return_value = None
            result = instagram_handler.check_credentials("demo", "pass123")

        self.assertTrue(result.success)
        mock_loader.login.assert_called_once_with("demo", "pass123")

    def test_task_manager(self):
        task = task_manager.create_task(username="testuser", passwords=["pass1", "pass2"])
        self.assertIsNotNone(task.task_id)
        self.assertTrue(task_manager.delete_task(task.task_id))

    def test_multiple_usernames(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("pass1\npass2\npass3")
            temp_file = f.name

        try:
            with patch.object(instagram_handler, "check_credentials") as mock_check:
                mock_check.return_value = LoginResult(
                    success=False,
                    username="user1",
                    password="pass1",
                    message="Invalid password",
                    error_type="invalid_password",
                )

                with open(temp_file, "rb") as f:
                    response = self.client.post(
                        "/api/tasks",
                        data={
                            "passwordFile": (f, "passwords.txt"),
                            "usernames": "user1,user2,user3",
                        },
                    )

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json["success"])
                time.sleep(0.5)
                self.assertEqual(self.client.get("/api/tasks").json["count"], 1)
        finally:
            os.unlink(temp_file)


if __name__ == "__main__":
    unittest.main()
