# service.py
from threading import Thread
import time
import subprocess
import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status":"ok", "project":"SafeArchive"})

@app.route("/health")
def health():
    return "ok", 200

def run_cli_background():
    """
    Try to run the CLI entry in background (non-interactive).
    If cli.py is interactive, this function will just return.
    Adjust the call below if your CLI needs extra args.
    """
    try:
        # If you have a CLI entry that can run headless, use it:
        # e.g., python -u cli.py --serve
        cmd = ["python", "-u", "cli.py"]
        # If cli.py requires TTY/interactive, skip launching to avoid blocking the container.
        # We attempt to run it; if it exits quickly, that's ok.
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

if __name__ == "__main__":
    # Launch CLI in background (best-effort). If this causes problems, remove this line.
    t = Thread(target=run_cli_background, daemon=True)
    t.start()
    # Start Flask app
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
