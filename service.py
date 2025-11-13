# service.py
# Flask REST API for SafeArchive cloud deployment
# Endpoints: /health, /zip, /backup, /download, /restore
# Uses headless helpers in Scripts/api_helpers.py

import os
import sys
import tempfile
import shutil
import traceback
import subprocess
from threading import Thread

# Ensure Scripts module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

try:
    from Scripts import api_helpers
except ImportError as e:
    print(f"Error importing api_helpers: {e}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"sys.path: {sys.path}")
    sys.exit(1)

app = Flask(__name__)

# Limit total upload size (bytes) — adjust as needed
MAX_TOTAL_UPLOAD_BYTES = int(os.environ.get("MAX_TOTAL_UPLOAD_BYTES", 150 * 1024 * 1024))  # 150 MB
app.config["MAX_CONTENT_LENGTH"] = MAX_TOTAL_UPLOAD_BYTES

# Use api_helpers' BACKUP_STORE if present, otherwise default
BACKUP_STORE = getattr(api_helpers, "BACKUP_STORE", os.path.join(tempfile.gettempdir(), "safearchive_backups"))
os.makedirs(BACKUP_STORE, exist_ok=True)

print(f"[SafeArchive] Using BACKUP_STORE: {BACKUP_STORE}")

# API key for protecting sensitive endpoints (set in Render env / GitHub Secrets)
SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY")


def require_api_key():
    """
    If SERVICE_API_KEY is set, require a matching key in:
      - header 'x-api-key' OR
      - query param 'api_key'
    Returns (True, None) if permitted, otherwise (False, (response, status_code)).
    """
    if not SERVICE_API_KEY:
        # No API key set -> open access (backwards compatible)
        return True, None

    header_key = request.headers.get("x-api-key")
    if header_key and header_key == SERVICE_API_KEY:
        return True, None

    q = request.args.get("api_key")
    if q and q == SERVICE_API_KEY:
        return True, None

    return False, (jsonify({"error": "unauthorized - invalid or missing API key"}), 401)


@app.route("/")
def home():
    return jsonify({"status": "ok", "project": "SafeArchive"})


@app.route("/health")
def health():
    return "ok", 200


def run_cli_background():
    """
    Best-effort: try to run CLI entry in background. If cli.py is interactive or absent, this will harmlessly fail.
    """
    try:
        cmd = ["python", "-u", "cli.py"]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


@app.route("/zip", methods=["POST"])
def zip_route():
    """
    POST /zip
      - form-data files: one or more 'file' fields
      - optional form field: password (plaintext) to AES-encrypt the zip entries
    Returns: downloadable zip containing uploaded files (optionally AES-encrypted)
    """
    try:
        if "file" not in request.files:
            return jsonify({"error": "file field missing; send at least one 'file' in form-data"}), 400

        files = request.files.getlist("file")
        if not files:
            return jsonify({"error": "no files uploaded"}), 400

        password_txt = request.form.get("password")
        password_bytes = password_txt.encode("utf-8") if password_txt else None

        tmp_dir = tempfile.mkdtemp(prefix="safearchive_upload_")
        saved_paths = []
        total_bytes = 0
        try:
            for f in files:
                filename = f.filename or "file"
                filename = secure_filename(filename)
                if filename == "":
                    filename = "file"
                dest_path = os.path.join(tmp_dir, filename)
                f.save(dest_path)
                size = os.path.getsize(dest_path)
                total_bytes += size
                saved_paths.append(dest_path)

                if total_bytes > MAX_TOTAL_UPLOAD_BYTES:
                    return jsonify({"error": "uploaded data too large"}), 413

            # create zip using helper
            zip_path = api_helpers.create_zip_from_uploaded_files(saved_paths, password=password_bytes)

            download_name = f"safearchive_files.zip"
            return send_file(zip_path, as_attachment=True, download_name=download_name)

        finally:
            # cleanup uploaded files (keep zip for send_file; helper writes zip into tmpdir/tempfile)
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "server_error", "details": str(e)}), 500


@app.route("/backup", methods=["POST"])
def backup_route():
    """
    POST /backup
      form-data:
        - file=@...   (one or more files)
        - backup_name (optional string)
        - password (optional string; if provided, stored backup will be encrypted)
    Response:
      JSON {status: "ok", backup_file: "<filename>"} or error.
    """
    ok, resp = require_api_key()
    if not ok:
        return resp

    try:
        if "file" not in request.files:
            return jsonify({"error": "file field missing"}), 400
        files = request.files.getlist("file")
        if not files:
            return jsonify({"error": "no files uploaded"}), 400

        backup_name = request.form.get("backup_name") or f"backup_{os.getpid()}"
        password_txt = request.form.get("password")
        password = password_txt.encode("utf-8") if password_txt else None

        tmp_dir = tempfile.mkdtemp(prefix="safearchive_upload_")
        saved_paths = []
        try:
            for f in files:
                fname = secure_filename(f.filename or "file")
                dest = os.path.join(tmp_dir, fname)
                f.save(dest)
                saved_paths.append(dest)

            stored_path = api_helpers.save_and_encrypt_backup(saved_paths, backup_name, password)
            stored_name = os.path.basename(stored_path)
            return jsonify({"status": "ok", "backup_file": stored_name}), 200

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "server_error", "details": str(e)}), 500


@app.route("/download", methods=["GET"])
def download_backup():
    """
    GET /download?backup=<backup_filename>
    Returns the raw stored backup file (encrypted .enc.zip or plain .zip)
    """
    ok, resp = require_api_key()
    if not ok:
        return resp

    try:
        backup = request.args.get("backup")
        if not backup:
            return jsonify({"error": "backup param missing"}), 400
        path = os.path.join(BACKUP_STORE, secure_filename(backup))
        if not os.path.exists(path):
            return jsonify({"error": "not_found"}), 404
        return send_file(path, as_attachment=True, download_name=backup)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "server_error", "details": str(e)}), 500


@app.route("/restore", methods=["POST"])
def restore_route():
    """
    POST /restore
      form-data:
        - backup (name returned from /backup)
        - password (required if encrypted)
    Returns: a plain zip containing restored folder/files (downloadable)
    """
    ok, resp = require_api_key()
    if not ok:
        return resp

    try:
        backup = request.form.get("backup")
        if not backup:
            return jsonify({"error": "backup param missing"}), 400
        password_txt = request.form.get("password")
        password = password_txt.encode("utf-8") if password_txt else None

        stored_path = os.path.join(BACKUP_STORE, secure_filename(backup))
        if not os.path.exists(stored_path):
            return jsonify({"error": "not_found"}), 404

        restored_zip = api_helpers.decrypt_backup_to_zip(stored_path, password)
        download_name = f"restored_{os.path.splitext(backup)[0]}.zip"
        return send_file(restored_zip, as_attachment=True, download_name=download_name)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "server_error", "details": str(e)}), 500


if __name__ == "__main__":
    # Launch CLI in background (best-effort). If this causes problems, remove the thread start.
    t = Thread(target=run_cli_background, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
