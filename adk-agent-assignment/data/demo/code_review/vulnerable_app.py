"""DELIBERATELY VULNERABLE fixture for the Code Review Assistant. Do not deploy.

Every function below contains at least one planted security defect.
"""
import hashlib
import os
import pickle
import sqlite3
import subprocess

import requests
import yaml
from flask import Flask, request, send_file

app = Flask(__name__)
DB_PASSWORD = "SuperSecret123!"          # planted: hard-coded credential


def get_user(conn: sqlite3.Connection, username: str):
    query = f"SELECT * FROM users WHERE name = '{username}'"   # planted: SQL injection
    return conn.execute(query).fetchall()


@app.route("/ping")
def ping():
    host = request.args.get("host", "")
    return subprocess.check_output(f"ping -c 1 {host}", shell=True)   # planted: cmd injection


@app.route("/download")
def download():
    name = request.args.get("file")
    return send_file(os.path.join("/srv/reports", name))     # planted: path traversal


@app.route("/preview")
def preview():
    url = request.args.get("url")
    return requests.get(url, timeout=5, verify=False).text   # planted: SSRF + TLS off


@app.route("/import", methods=["POST"])
def import_profile():
    return pickle.loads(request.data)                         # planted: unsafe deserialization


def load_config(path):
    with open(path) as fh:
        return yaml.load(fh)                                  # planted: unsafe YAML


def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()         # planted: weak password hash


def calculate(expression):
    return eval(expression)                                   # planted: eval


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)                       # planted: debug mode
