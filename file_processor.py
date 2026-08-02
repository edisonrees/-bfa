"""Streaming password file / paste processor with CSV-style TXT support."""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Generator, Iterable, List, Optional, Tuple

from config import config

logger = logging.getLogger(__name__)


class CapExceededError(Exception):
    def __init__(self, count: int, limit: int):
        self.count = count
        self.limit = limit
        super().__init__(f"Password cap exceeded: found > {limit:,} (max {limit:,})")


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
        # unique name to avoid collisions across replicas
        stem, ext = os.path.splitext(filename)
        unique = f"{stem}_{os.getpid()}_{int(__import__('time').time())}{ext}"
        filepath = os.path.join(self.upload_folder, unique)
        try:
            file_storage.save(filepath)
            return filepath
        except Exception as exc:
            logger.error("Error saving file: %s", exc)
            return None

    def _split_csv_line(self, line: str) -> List[str]:
        """Parse a CSV-style line (quoted fields, commas)."""
        line = line.strip()
        if not line or line.startswith("#"):
            return []
        try:
            row = next(csv.reader([line]))
        except Exception:
            row = [p.strip() for p in line.split(",")]
        return [cell.strip() for cell in row if cell and cell.strip() and not cell.strip().startswith("#")]

    def _tokens_from_line(self, line: str) -> List[str]:
        line = line.strip()
        if not line or line.startswith("#"):
            return []

        # user:pass or user:pass1,pass2
        if ":" in line and not line.startswith("{"):
            left, right = line.split(":", 1)
            # If left looks like a header-ish single token and right has commas → passwords only
            right = right.strip()
            if "," in right:
                return [p for p in self._split_csv_line(right)]
            if right:
                return [right]
            return []

        # CSV / comma-separated values (including one long TXT line)
        if "," in line:
            return self._split_csv_line(line)

        return [line]

    def iter_password_text(self, text: str) -> Generator[str, None, None]:
        # Support a single giant comma-separated blob with no newlines
        if "\n" not in text and "\r" not in text and "," in text:
            for token in self._split_csv_line(text):
                yield token
            return
        for line in text.splitlines():
            for token in self._tokens_from_line(line):
                yield token

    def iter_password_file(self, filepath: str) -> Generator[str, None, None]:
        extension = os.path.splitext(filepath)[1].lower()
        if extension == ".json":
            yield from self._iter_json_file(filepath)
            return
        if extension == ".csv":
            yield from self._iter_csv_file(filepath)
            return
        # .txt and unknown → stream lines; CSV-style commas supported
        with open(filepath, "r", encoding="utf-8", errors="ignore", newline="") as handle:
            first = handle.readline()
            if not first:
                return
            # One-line comma-separated TXT
            rest_pos = handle.tell()
            second = handle.readline()
            handle.seek(0)
            if second == "" and "," in first:
                for token in self._split_csv_line(first):
                    yield token
                return
            handle.seek(0)
            for line in handle:
                for token in self._tokens_from_line(line):
                    yield token

    def _iter_csv_file(self, filepath: str) -> Generator[str, None, None]:
        with open(filepath, "r", encoding="utf-8", errors="ignore", newline="") as handle:
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
                    # if header-only first column, still take other cells if present
                    cells = row[1:] if len(row) > 1 else []
                    if not cells:
                        continue
                    row = cells
                for cell in row:
                    cell = (cell or "").strip()
                    if cell and not cell.startswith("#"):
                        yield cell

    def _iter_json_file(self, filepath: str) -> Generator[str, None, None]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    yield item
                elif isinstance(item, dict):
                    value = item.get("password") or item.get("pass")
                    if value:
                        yield str(value)
        elif isinstance(data, dict):
            if isinstance(data.get("passwords"), list):
                for item in data["passwords"]:
                    yield str(item)
            elif "password" in data:
                yield str(data["password"])

    def collect_passwords(
        self,
        source: Iterable[str],
        *,
        dedupe: bool = True,
        limit: Optional[int] = None,
    ) -> Tuple[List[str], int, bool]:
        """
        Collect passwords up to limit.
        Returns (list, total_seen_or_collected, capped).
        For huge streams, set dedupe=False.
        """
        limit = limit if limit is not None else config.MAX_PASSWORDS
        seen = set() if dedupe else None
        out: List[str] = []
        total = 0
        capped = False
        for password in source:
            if not password:
                continue
            total += 1
            if total > limit:
                capped = True
                break
            if seen is not None:
                if password in seen:
                    continue
                seen.add(password)
            out.append(password)
            # If streaming into memory past threshold, caller should use path mode instead
            if len(out) > config.STREAM_THRESHOLD and dedupe:
                # keep going for count accuracy only when small; otherwise stop collecting list
                pass
        return out, len(out) if seen is None else len(out), capped

    def count_passwords(self, filepath: str) -> Tuple[int, bool]:
        """Stream-count passwords; returns (count, capped)."""
        count = 0
        capped = False
        for _ in self.iter_password_file(filepath):
            count += 1
            if count > config.MAX_PASSWORDS:
                return config.MAX_PASSWORDS, True
        return count, capped

    def preview_file(self, filepath: str, sample_size: int = 8) -> dict:
        sample: List[str] = []
        count = 0
        capped = False
        for password in self.iter_password_file(filepath):
            count += 1
            if len(sample) < sample_size:
                sample.append(password)
            if count > config.MAX_PASSWORDS:
                count = config.MAX_PASSWORDS
                capped = True
                break
        return {
            "success": True,
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "password_count": count,
            "preview": sample,
            "capped": capped,
            "max_passwords": config.MAX_PASSWORDS,
            "stream": count > config.STREAM_THRESHOLD,
            "error": None,
        }

    def process_password_file(self, filepath: str, *, load_into_memory: Optional[bool] = None) -> dict:
        try:
            # First pass: count + sample
            preview = self.preview_file(filepath)
            count = preview["password_count"]
            if count == 0:
                return {
                    "success": False,
                    "filepath": filepath,
                    "filename": os.path.basename(filepath),
                    "password_count": 0,
                    "passwords": [],
                    "stream": False,
                    "capped": False,
                    "error": "No passwords found",
                }

            if preview["capped"]:
                return {
                    "success": False,
                    "filepath": filepath,
                    "filename": os.path.basename(filepath),
                    "password_count": count,
                    "passwords": [],
                    "stream": True,
                    "capped": True,
                    "error": f"Password cap exceeded (max {config.MAX_PASSWORDS:,})",
                }

            should_load = (
                load_into_memory
                if load_into_memory is not None
                else count <= config.STREAM_THRESHOLD
            )

            passwords: List[str] = []
            if should_load:
                # small lists: load + dedupe
                passwords, _, _ = self.collect_passwords(
                    self.iter_password_file(filepath),
                    dedupe=True,
                    limit=config.MAX_PASSWORDS,
                )
                count = len(passwords)

            return {
                "success": True,
                "filepath": filepath,
                "filename": os.path.basename(filepath),
                "password_count": count,
                "passwords": passwords,
                "stream": not should_load,
                "capped": False,
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
                "stream": False,
                "capped": False,
                "error": str(exc),
            }

    def process_password_text(self, text: str, label: str = "pasted.txt") -> dict:
        try:
            # Paste is always in-memory; still enforce cap
            passwords, _, capped = self.collect_passwords(
                self.iter_password_text(text),
                dedupe=True,
                limit=config.MAX_PASSWORDS,
            )
            if capped:
                return {
                    "success": False,
                    "filepath": None,
                    "filename": label,
                    "password_count": config.MAX_PASSWORDS,
                    "passwords": [],
                    "stream": False,
                    "capped": True,
                    "error": f"Password cap exceeded (max {config.MAX_PASSWORDS:,})",
                }
            return {
                "success": True,
                "filepath": None,
                "filename": label,
                "password_count": len(passwords),
                "passwords": passwords,
                "stream": False,
                "capped": False,
                "error": None,
            }
        except Exception as exc:
            return {
                "success": False,
                "filepath": None,
                "filename": label,
                "password_count": 0,
                "passwords": [],
                "stream": False,
                "capped": False,
                "error": str(exc),
            }

    # Back-compat helpers
    def parse_password_text(self, text: str) -> List[str]:
        passwords, _, _ = self.collect_passwords(self.iter_password_text(text), dedupe=True)
        return passwords

    def parse_password_file(self, filepath: str) -> List[str]:
        result = self.process_password_file(filepath, load_into_memory=True)
        if not result["success"]:
            raise ValueError(result["error"] or "parse failed")
        return result["passwords"]

    def get_password_generator(
        self, passwords: List[str], batch_size: int = 100
    ) -> Generator[List[str], None, None]:
        for i in range(0, len(passwords), batch_size):
            yield passwords[i : i + batch_size]

    def iter_sharded(
        self, source: Iterable[str], *, replica_id: int, total_replicas: int
    ) -> Generator[Tuple[int, str], None, None]:
        for index, password in enumerate(source):
            if total_replicas <= 1 or index % total_replicas == replica_id:
                yield index, password

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
