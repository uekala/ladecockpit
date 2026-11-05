#!/usr/bin/env python3
"""Check that the application version and both changelogs stay in sync."""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def fail(message: str) -> None:
    raise SystemExit(f"Version check failed: {message}")


source = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
match = re.search(r"""^__version__\s*=\s*["']([^"']+)["']""", source, re.MULTILINE)
if not match:
    fail("app/__init__.py does not define __version__")
version = match.group(1)
if not SEMVER.fullmatch(version):
    fail(f"invalid application version: {version!r}")

for relative in ("CHANGELOG.md", "ladecockpit-app/CHANGELOG.md"):
    path = ROOT / relative
    if not path.is_file():
        fail(f"missing {relative}")
    headings = re.findall(
        r"^##\s+(\d+\.\d+\.\d+)(?:\s|$)", path.read_text(encoding="utf-8"), re.MULTILINE
    )
    if not headings:
        fail(f"{relative} has no version heading")
    if headings[0] != version:
        fail(f"{relative} starts at {headings[0]}, but app/__init__.py says {version}")

ref = os.environ.get("GITHUB_REF", "")
if ref.startswith("refs/tags/"):
    tag_version = ref.removeprefix("refs/tags/").removeprefix("v")
    if tag_version != version:
        fail(f"tag {ref!r} does not match application version {version}")

print(f"Ladecockpit version {version}: source, changelogs and tag are consistent.")
