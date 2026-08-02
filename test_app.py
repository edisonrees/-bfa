#!/usr/bin/env python3
"""
Test suite for Local Auth BFa application
"""

import unittest
import tempfile
import os
import time
from unittest.mock import patch, MagicMock
from app import app
from auth_api import auth_handler, LoginResult, RateLimiter
from file_processor import password_processor
from models import BFaTask, task_manager
from config import config


class TestLocalAuthBFa(unittest.TestCase):

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

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data["status"], "healthy")
        self.assertIn("replica_id", data)
        self.assertIn("target_url", data)
        self.assertIn("timestamp", data)

    def test_main_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Local Auth BFa Tool", response.data)

    def test_login_endpoint_success(self):
        response = self.client.post(
            "/api/login",
            json={"username": config.DEMO_USERNAME, "password": config.DEMO_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(data["success"])

    def test_login_endpoint_invalid_password(self):
        response = self.client.post(
            "/api/login",
            json={"username": config.DEMO_USERNAME, "password": "wrong"},
        )
        self.assertEqual(response.status_code, 401)

    def test_login_endpoint_invalid_username(self):
        response = self.client.post(
            "/api/login",
            json={"username": "nobody", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 404)

    def test_tasks_endpoint_empty(self):
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 0)
        self.assertEqual(len(data["tasks"]), 0)

    def test_file_preview_txt(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("password1\npassword2\npassword3")
            temp_file = f.name

        try:
            with open(temp_file, "rb") as f:
                response = self.client.post("/api/preview", data={"passwordFile": (f, "test.txt")})

            self.assertEqual(response.status_code, 200)
            data = response.json
            self.assertTrue(data["success"])
            self.assertEqual(data["password_count"], 3)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_file_preview_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("password\npass1\npass2\npass3")
            temp_file = f.name

        try:
            with open(temp_file, "rb") as f:
                response = self.client.post("/api/preview", data={"passwordFile": (f, "test.csv")})

            self.assertEqual(response.status_code, 200)
            data = response.json
            self.assertTrue(data["success"])
            self.assertEqual(data["password_count"], 3)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_file_preview_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"passwords": ["pass1", "pass2", "pass3"]}')
            temp_file = f.name

        try:
            with open(temp_file, "rb") as f:
                response = self.client.post("/api/preview", data={"passwordFile": (f, "test.json")})

            self.assertEqual(response.status_code, 200)
            data = response.json
            self.assertTrue(data["success"])
            self.assertEqual(data["password_count"], 3)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_file_processor_text_formats(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("pass1,pass2,pass3")
            temp_file = f.name

        try:
            result = password_processor.process_password_file(temp_file)
            self.assertTrue(result["success"])
            self.assertEqual(result["password_count"], 3)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("user1:pass1,pass2\nuser2:pass3")
            temp_file = f.name

        try:
            result = password_processor.process_password_file(temp_file)
            self.assertTrue(result["success"])
            self.assertEqual(result["password_count"], 3)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_rate_limiter(self):
        limiter = RateLimiter(300)
        start_time = time.time()
        for _ in range(5):
            limiter.wait()
        elapsed = time.time() - start_time
        self.assertGreaterEqual(elapsed, 0.8)

    def test_auth_handler_target_url(self):
        self.assertEqual(auth_handler.login_url, config.TARGET_LOGIN_URL)

    def test_check_credentials_against_local_login(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"success": true}'
        mock_response.json.return_value = {
            "success": True,
            "message": "Login successful",
            "user": {"username": config.DEMO_USERNAME},
        }

        with patch("auth_api.requests.post", return_value=mock_response):
            result = auth_handler.check_credentials(config.DEMO_USERNAME, config.DEMO_PASSWORD)

        self.assertTrue(result.success)
        self.assertEqual(result.username, config.DEMO_USERNAME)

    def test_task_creation(self):
        task = BFaTask(
            username="testuser",
            usernames=["testuser"],
            password_file="test.txt",
            passwords=["pass1", "pass2", "pass3"],
        )

        self.assertEqual(task.username, "testuser")
        self.assertEqual(len(task.usernames), 1)
        self.assertEqual(len(task.passwords), 3)
        self.assertEqual(task.status, "pending")

        task_dict = task.to_dict()
        self.assertIn("task_id", task_dict)
        self.assertIn("username", task_dict)
        self.assertIn("password_count", task_dict)

    def test_task_manager(self):
        task = task_manager.create_task(username="testuser", passwords=["pass1", "pass2"])
        self.assertIsNotNone(task.task_id)

        retrieved_task = task_manager.get_task(task.task_id)
        self.assertIsNotNone(retrieved_task)
        self.assertEqual(retrieved_task.username, "testuser")

        all_tasks = task_manager.get_all_tasks()
        self.assertGreaterEqual(len(all_tasks), 1)

        result = task_manager.delete_task(task.task_id)
        self.assertTrue(result)

        deleted_task = task_manager.get_task(task.task_id)
        self.assertIsNone(deleted_task)

    def test_multiple_usernames(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("pass1\npass2\npass3")
            temp_file = f.name

        try:
            with patch.object(auth_handler, "check_credentials") as mock_check:
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
                data = response.json
                self.assertTrue(data["success"])
                self.assertIn("task_id", data)

                time.sleep(0.5)

                tasks_response = self.client.get("/api/tasks")
                tasks_data = tasks_response.json
                self.assertEqual(tasks_data["count"], 1)

        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


if __name__ == "__main__":
    unittest.main()
