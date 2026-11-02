import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request

from conftest import ROOT


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_sigterm_ends_with_exit_code_0(tmp_path):
    # Home Assistant stops an app with SIGTERM and warns when it ends with 143.
    port = _free_port()
    env = {**os.environ, "DATA_DIR": str(tmp_path), "APP_MODE": "demo"}
    proc = subprocess.Popen(
        [sys.executable, "-c", f"from app.__main__ import main; main({port})"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1)
                break
            except OSError:
                assert proc.poll() is None, proc.stdout.read()
                assert time.monotonic() < deadline, "app did not start"
                time.sleep(0.2)
        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 0, out
    assert "Application shutdown complete" in out
