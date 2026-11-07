"""Browser smoke test for the standalone dashboard (no Home Assistant)."""
from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def wait_for_server(url: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Ladecockpit exited with code {process.returncode}")
        try:
            with urllib.request.urlopen(url + "/healthz", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise TimeoutError("Ladecockpit did not start within 30 seconds")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ladecockpit-browser-") as data_dir:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        base_url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env.update({"APP_MODE": "demo", "DATA_DIR": data_dir, "APP_LANG": "de"})
        process = subprocess.Popen(
            ["python", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        try:
            wait_for_server(base_url, process)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    for width, height in ((1440, 1000), (390, 844)):
                        page = browser.new_page(viewport={"width": width, "height": height})
                        errors: list[str] = []
                        page.on("pageerror", lambda error: errors.append(str(error)))

                        def without_home_assistant(route):
                            response = route.fetch()
                            payload = response.json()
                            payload.setdefault("setup", {})["ha_configured"] = False
                            route.fulfill(response=response, json=payload)

                        page.route("**/api/dashboard", without_home_assistant)
                        page.goto(base_url, wait_until="networkidle")
                        page.locator("#h-ops").wait_for()

                        # HA-only panels must be absent in standalone mode.
                        for selector in ("#h-batt", "#h-next", "#h-health", "#h-climate", "#h-rec"):
                            assert page.locator(selector).count() == 0, f"{selector} unexpectedly visible at {width}px"

                        # Core charging/invoice features must remain available.
                        for selector in ("#h-last", "#h-month", "#h-radar", "#h-sites", "#h-hist", "#h-list", "#h-ops"):
                            assert page.locator(selector).count() == 1, f"{selector} missing at {width}px"

                        headers = page.locator("#sessions-panel thead th").all_text_contents()
                        assert not any("HA" in header for header in headers), f"HA table column remains: {headers}"
                        assert "optional" in page.locator("#h-ops").locator("xpath=../..").inner_text().lower()
                        assert not errors, f"Browser JavaScript errors at {width}px: {errors}"
                        page.close()
                    browser.close()
                finally:
                    if browser.is_connected():
                        browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
