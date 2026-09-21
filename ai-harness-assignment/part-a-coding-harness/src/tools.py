
import os
import subprocess

def list_files(path="."):
    return os.listdir(path)

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)
    return f"Wrote {len(content)} chars to {path}"

def run_shell_command(cmd, cwd="."):
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=10)
    return res.stdout if res.returncode == 0 else res.stderr
