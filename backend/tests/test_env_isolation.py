"""The tests never see the developer's backend/.env (see tests/conftest.py). Only key NAMES are read, never values."""
import os

from app.settings import BACKEND_ROOT
from tests import conftest
from tests.test_api import make_settings


def dotenv_names():
    p = BACKEND_ROOT / ".env"
    if not p.is_file():
        return set()
    names = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            names.add(line.split("=", 1)[0].strip())
    return names


def test_no_dotenv_value_reaches_the_test_process():
    leaked = sorted(n for n in conftest.LEAKED_FROM_DOTENV if n in os.environ)
    assert leaked == [], f"variabel dari backend/.env masih ada: {leaked}"


def test_settings_use_documented_defaults_whatever_the_local_env_says(tmp_path, monkeypatch):
    s = make_settings(tmp_path, monkeypatch)
    assert (s.evidence_retention_hours, s.evidence_hold_days, s.report_frame_retention_hours) == (24.0, 7.0, 24.0)
    assert s.evidence_key == "" and str(s.db_path).startswith(str(tmp_path))


def test_only_names_from_dotenv_were_removed():
    """Whatever was removed came from backend/.env (and was not in the real environment before)."""
    assert set(conftest.LEAKED_FROM_DOTENV) <= dotenv_names()
