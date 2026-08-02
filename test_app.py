#!/usr/bin/env python3
"""Tests for MOCKA."""

import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from app import app, parse_usernames
from config import config
from file_processor import password_processor
from instagram_api import LoginResult, RateLimiter, instagram_handler
from mock_proxy import install_mock_proxy, rewrite_instagram_url
from models import task_manager


class TestMocka(unittest.TestCase):
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
            for name in os.listdir(config.UPLOAD_FOLDER):
                path = os.path.join(config.UPLOAD_FOLDER, name)
                if os.path.isfile(path):
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
        for task in list(task_manager.get_all_tasks()):
            task_manager.delete_task(task.task_id)

    def test_parse_usernames(self):
        self.assertEqual(parse_usernames("@alice, bob\ncharlie"), ["alice", "bob", "charlie"])

    def test_mock_url_rewrite(self):
        original = "https://www.instagram.com/api/v1/web/accounts/login/ajax/"
        expected = (
            config.MOCK_API_BASE_URL.rstrip("/")
            + "/api/v1/web/accounts/login/ajax/"
        )
        self.assertEqual(rewrite_instagram_url(original), expected)

    def test_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["status"], "healthy")
        self.assertIn("target_url", res.json)
        self.assertIn("stats", res.json)
        self.assertEqual(res.json["max_passwords"], config.MAX_PASSWORDS)
        self.assertIn("total_replicas", res.json)

    def test_csv_style_txt_oneline(self):
        result = password_processor.process_password_text("alpha,beta,gamma,delta")
        self.assertTrue(result["success"])
        self.assertEqual(result["password_count"], 4)
        self.assertEqual(result["passwords"], ["alpha", "beta", "gamma", "delta"])

    def test_csv_style_txt_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as handle:
            handle.write("one,two,three\nfour,five\n")
            path = handle.name
        try:
            result = password_processor.process_password_file(path)
            self.assertTrue(result["success"])
            self.assertEqual(result["password_count"], 5)
            self.assertIn("two", result["passwords"])
        finally:
            os.unlink(path)

    def test_csv_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as handle:
            handle.write("password\nsecret\nletmein\n")
            path = handle.name
        try:
            result = password_processor.process_password_file(path)
            self.assertTrue(result["success"])
            self.assertEqual(result["password_count"], 2)
        finally:
            os.unlink(path)

    def test_replica_shard_size(self):
        from replicas import ReplicaInfo

        info = ReplicaInfo(replica_id=0, total_replicas=4)
        self.assertEqual(info.shard_size(100), 25)
        self.assertTrue(info.owns_index(0))
        self.assertFalse(info.owns_index(1))
        info2 = ReplicaInfo(replica_id=1, total_replicas=4)
        self.assertEqual(info2.shard_size(100), 25)
        self.assertTrue(info2.owns_index(1))

    def test_eta_fields(self):
        task = task_manager.create_task(
            usernames=["a"],
            passwords=["1", "2", "3", "4"],
            replica_index=0,
            total_replicas=2,
            password_count=4,
        )
        task.status = "processing"
        task.start_time = task.start_time or __import__("datetime").datetime.now()
        from datetime import datetime, timedelta

        task.start_time = datetime.now() - timedelta(seconds=10)
        task.progress = 2
        task.note_progress()
        data = task.to_dict()
        self.assertIn("eta_seconds", data)
        self.assertIn("eta_human", data)
        self.assertEqual(data["shard_label"], "1/2")

    def test_max_passwords_config(self):
        self.assertEqual(config.MAX_PASSWORDS, 100_000_000)

    def test_index(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"MOCKA", res.data)
        self.assertIn(b"New run", res.data)

    def test_meta(self):
        res = self.client.get("/api/meta")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json["success"])
        self.assertEqual(res.json["mock_url"], config.MOCK_API_BASE_URL)

    def test_sample_download(self):
        res = self.client.get("/api/sample")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"password", res.data)

    def test_preview_paste(self):
        res = self.client.post("/api/preview", data={"passwords": "a\nb\nc"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["password_count"], 3)

    def test_preview_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as handle:
            handle.write("one\ntwo\nthree")
            path = handle.name
        try:
            with open(path, "rb") as handle:
                res = self.client.post(
                    "/api/preview", data={"passwordFile": (handle, "t.txt")}
                )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json["password_count"], 3)
        finally:
            os.unlink(path)

    def test_create_task_paste(self):
        with patch.object(instagram_handler, "check_credentials") as mock_check:
            mock_check.return_value = LoginResult(
                success=False,
                username="demo",
                password="x",
                message="Invalid password",
                error_type="invalid_password",
            )
            res = self.client.post(
                "/api/tasks",
                data={
                    "usernames": "demo",
                    "source": "paste",
                    "passwords": "aaa\nbbb",
                    "stop_on_first": "true",
                },
            )
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.json["success"])
            task_id = res.json["task_id"]
            time.sleep(0.4)
            detail = self.client.get(f"/api/tasks/{task_id}")
            self.assertEqual(detail.status_code, 200)

            cancel = self.client.post(f"/api/tasks/{task_id}/cancel")
            self.assertEqual(cancel.status_code, 200)

    def test_create_task_sample(self):
        with patch.object(instagram_handler, "check_credentials") as mock_check:
            mock_check.return_value = LoginResult(
                success=False,
                username="demo",
                password="x",
                message="Invalid password",
                error_type="invalid_password",
            )
            res = self.client.post(
                "/api/tasks",
                data={"usernames": "demo", "source": "sample", "stop_on_first": "true"},
            )
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.json["success"])

    def test_clear_finished(self):
        task = task_manager.create_task(usernames=["a"], passwords=["1"])
        task.status = "completed"
        task_manager.update_task(task)
        res = self.client.post("/api/tasks/clear-finished")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["removed"], 1)

    def test_export(self):
        task = task_manager.create_task(usernames=["a"], passwords=["1", "2"])
        res = self.client.get(f"/api/tasks/{task.task_id}/export")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json["success"])

    def test_session_creation(self):
        session = instagram_handler.create_session()
        self.assertEqual(type(session).__name__, "Instaloader")

    def test_rate_limiter(self):
        limiter = RateLimiter(600)
        start = time.time()
        for _ in range(3):
            limiter.wait()
        self.assertGreaterEqual(time.time() - start, 0.15)

    def test_file_processor_formats(self):
        result = password_processor.process_password_text("a,b,c")
        self.assertEqual(result["password_count"], 3)
        result = password_processor.process_password_text("u:p1,p2")
        self.assertEqual(result["password_count"], 2)

    def test_proxy_install(self):
        install_mock_proxy()
        install_mock_proxy()


if __name__ == "__main__":
    unittest.main()
