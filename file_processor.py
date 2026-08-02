"""Password file / paste processor."""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Generator, List, Optional
import logging

from config import config

logger = logging.getLogger(__name__)


class PasswordFileProcessor:
    def __init__(self) -> None:
        self.upload_folder = config.UPLOAD_FOLDER
        self.allowed_extensions = config.ALLOWED_EXTENSIONS
        os.makedirs(self.upload_folder, exist_ok=True)

    def allowed_file(self, filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in self.allowed_extensions

    def sanitize_filename(self, filename: str) -> str:
        filename = os.path.basename(filename)
        return re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

    def save_uploaded_file(self, file_storage) -> Optional[str]:
        if not file_storage or not file_storage.filename:
            return None
        filename = self.sanitize_filename(file_storage.filename)
        if not self.allowed_file(filename):
            return None
        filepath = os.path.join(self.upload_folder, filename)
        try:
            file_storage.save(filepath)
            return filepath
        except Exception as exc:
            logger.error("Error saving file: %s", exc)
            return None

    def parse_password_text(self, text: str) -> List[str]:
        passwords: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                password_part = line.split(":", 1)[1].strip()
                if "," in password_part:
                    passwords.extend(p.strip() for p in password_part.split(",") if p.strip())
                elif password_part:
                    passwords.append(password_part)
            elif "," in line:
                passwords.extend(p.strip() for p in line.split(",") if p.strip())
            else:
                passwords.append(line)
        return self._dedupe(passwords)

    def parse_password_file(self, filepath: str) -> List[str]:
        extension = os.path.splitext(filepath)[1].lower()
        if extension == ".csv":
            return self._parse_csv_file(filepath)
        if extension == ".json":
            return self._parse_json_file(filepath)
        with open(filepath, "r", encoding="utf-8", errors="ignore") as handle:
            return self.parse_password_text(handle.read())

    def _parse_csv_file(self, filepath: str) -> List[str]:
        passwords: List[str] = []
        with open(filepath, "r", encoding="utf-8", errors="ignore") as handle:
            reader = csv.reader(handle)
            for row_index, row in enumerate(reader):
                if not row:
                    continue
                if row_index == 0 and row[0].strip().lower() in {
                    "password",
                    "passwords",
                    "pass",
                    "username",
                    "user",
                }:
                    continue
                for cell in row:
                    cell = cell.strip()
                    if cell and not cell.startswith("#"):
                        passwords.append(cell)
        return self._dedupe(passwords)

    def _parse_json_file(self, filepath: str) -> List[str]:
        passwords: List[str] = []
        with open(filepath, "r", encoding="utf-8", errors="ignore") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    passwords.append(item)
                elif isinstance(item, dict):
                    value = item.get("password") or item.get("pass")
                    if value:
                        passwords.append(str(value))
        elif isinstance(data, dict):
            if "passwords" in data and isinstance(data["passwords"], list):
                passwords.extend(str(p) for p in data["passwords"])
            elif "password" in data:
                passwords.append(str(data["password"]))
        return self._dedupe(passwords)

    def _dedupe(self, passwords: List[str]) -> List[str]:
        seen = set()
        unique: List[str] = []
        for password in passwords:
            if password and password not in seen:
                seen.add(password)
                unique.append(password)
        limit = getattr(config, "MAX_PASSWORDS", 5000)
        return unique[:limit]

    def process_password_file(self, filepath: str) -> dict:
        try:
            passwords = self.parse_password_file(filepath)
            return {
                "success": True,
                "filepath": filepath,
                "filename": os.path.basename(filepath),
                "password_count": len(passwords),
                "passwords": passwords,
                "error": None,
            }
        except Exception as exc:
            logger.error("Error processing file %s: %s", filepath, exc)
            return {
                "success": False,
                "filepath": filepath,
                "filename": os.path.basename(filepath),
                "password_count": 0,
                "passwords": [],
                "error": str(exc),
            }

    def process_password_text(self, text: str, label: str = "pasted.txt") -> dict:
        try:
            passwords = self.parse_password_text(text)
            return {
                "success": True,
                "filepath": None,
                "filename": label,
                "password_count": len(passwords),
                "passwords": passwords,
                "error": None,
            }
        except Exception as exc:
            return {
                "success": False,
                "filepath": None,
                "filename": label,
                "password_count": 0,
                "passwords": [],
                "error": str(exc),
            }

    def get_password_generator(
        self, passwords: List[str], batch_size: int = 100
    ) -> Generator[List[str], None, None]:
        for i in range(0, len(passwords), batch_size):
            yield passwords[i : i + batch_size]

    def cleanup_file(self, filepath: str) -> bool:
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                return True
            return False
        except Exception as exc:
            logger.error("Error removing file %s: %s", filepath, exc)
            return False

    def sample_passwords_path(self) -> Path:
        return Path(__file__).resolve().parent / "static" / "sample-passwords.txt"


password_processor = PasswordFileProcessor()
