from flask import Flask, jsonify, request, session
from flask_cors import CORS
import psutil
import subprocess
import threading
import time
import sys
import os
from datetime import datetime

PYTHON = sys.executable

app = Flask(__name__)
app.secret_key = "supersecretkey123"
CORS(app, supports_credentials=True)




USERNAME = "admin"
PASSWORD = "pass123"

# Container setup
container_configs = {
    "nginx": {"command": [PYTHON, "-m", "http.server", "8000"], "pid": None},
    "mysql": {"command": [PYTHON, "-c", "while True: pass"], "pid": None}
}

health_log = []
LOG_FILE = "logs.txt"

def log_to_file(entry):
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")

def start_container(name):
    config = container_configs.get(name)
    if config and config["pid"] is None:
        process = subprocess.Popen(config["command"])
        config["pid"] = process.pid
        log_to_file(f"{datetime.now()} | {name.upper()} | Started PID {process.pid}")

def stop_container(name):
    config = container_configs.get(name)
    pid = config["pid"]
    if pid and psutil.pid_exists(pid):
        psutil.Process(pid).terminate()
        config["pid"] = None
        log_to_file(f"{datetime.now()} | {name.upper()} | Stopped PID {pid}")

def restart_container(name):
    stop_container(name)
    time.sleep(1)
    start_container(name)
    log_to_file(f"{datetime.now()} | {name.upper()} | Restarted")

def monitor_and_autoheal():
    while True:
        for name, config in container_configs.items():
            pid = config["pid"]
            cpu, mem, status = 0, 0, "Crashed"

            if pid and psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                cpu = proc.cpu_percent(interval=0.5)
                mem = proc.memory_info().rss / (1024 * 1024)
                if cpu > 80 or mem > 200:
                    status = "High usage"
                    restart_container(name)
                else:
                    status = "Healthy"
            else:
                restart_container(name)

            health_log.append({
                "container": name,
                "cpu": round(cpu, 2),
                "memory": round(mem, 2),
                "status": status
            })

            log_to_file(f"{datetime.now()} | {name.upper()} | CPU: {cpu:.2f}% | MEM: {mem:.2f}MB | Status: {status}")

        time.sleep(5)

for name in container_configs:
    start_container(name)

threading.Thread(target=monitor_and_autoheal, daemon=True).start()

@app.route("/autoheal/status")
def autoheal_status():
    latest = []
    names = list(container_configs.keys())
    found = set()

    for entry in reversed(health_log):
        if entry["container"] not in found:
            latest.append(entry)
            found.add(entry["container"])
        if len(found) == len(names):
            break

    return jsonify(latest)



@app.route("/logs")
def get_logs():
    if not os.path.exists(LOG_FILE):
        return jsonify([])
    with open(LOG_FILE, "r") as f:
        return jsonify(f.readlines()[-50:])

@app.route("/control/<name>/<action>", methods=["POST"])
def control_container(name, action):
    if name not in container_configs:
        return "Invalid container name", 404
    if action == "start":
        start_container(name)
    elif action == "stop":
        stop_container(name)
    elif action == "restart":
        restart_container(name)
    else:
        return "Invalid action", 400
    return "OK", 200
    

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if data["username"] == USERNAME and data["password"] == PASSWORD:
        session["logged_in"] = True
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.before_request
def require_login():
    if request.endpoint not in ["login", "static", "get_logs", "autoheal_status", "control_container"]:
        if not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401

if __name__ == "__main__":
    app.run(debug=True)
