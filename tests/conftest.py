import dataclasses
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The app module creates its database on import – keep that out of the repository.
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="ladecockpit-test-"))
os.environ.setdefault("APP_MODE", "demo")

from app.config import load  # noqa: E402
from app.db import DB  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return dataclasses.replace(load(), data_dir=tmp_path, lang="en", locale="en-US")


@pytest.fixture
def db(tmp_path):
    return DB(tmp_path / "test.db")
