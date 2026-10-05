"""
test_full_e2e.py: end-to-end tests against the live FXMacroData API.

These use the keyless USD routes only, so no API key is needed. They make
real network calls and are skipped unless FXMD_E2E=1 is set.
Run with: FXMD_E2E=1 pytest cli_anything/fxmacrodata/tests/test_full_e2e.py -v

Each test runs the installed command through a subprocess (falling back to
``python -m cli_anything.fxmacrodata``) and checks the JSON it prints.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("FXMD_E2E") != "1", reason="set FXMD_E2E=1 to call the live API")


def _resolve_cli() -> list[str]:
    cmd = "cli-anything-fxmacrodata"
    if shutil.which(cmd):
        return [cmd]
    return [sys.executable, "-m", "cli_anything.fxmacrodata"]


def _run_json(*args: str) -> tuple[int, dict]:
    env = {k: v for k, v in os.environ.items() if k != "FXMACRODATA_API_KEY"}
    cmd = _resolve_cli() + ["--json", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env, check=False)
    return proc.returncode, json.loads(proc.stdout)


def test_server_status():
    code, body = _run_json("server", "status")
    assert code == 0 and body["ok"] is True and body["api_key_set"] is False


def test_catalogue_lists_cpi():
    code, body = _run_json("catalogue", "usd")
    assert code == 0
    assert "inflation" in body and body["inflation"]["source"]


def test_latest_cpi_has_publication_time():
    code, body = _run_json("latest", "usd", "inflation")
    assert code == 0
    assert body["indicator"] == "inflation"
    assert len(body["data"]) == 1
    row = body["data"][0]
    assert row["date"] and row["val"] is not None and "announcement_datetime" in row


def test_calendar_rows_have_times():
    code, body = _run_json("calendar", "usd", "--indicator", "inflation")
    assert code == 0
    assert all(row["release"] == "inflation" for row in body["data"])
    assert all(row.get("announcement_datetime_utc") for row in body["data"])


def test_forex_without_key_is_a_clear_401():
    code, body = _run_json("forex", "eur", "usd", "-n", "1")
    assert code == 1
    assert body["error"].startswith("HTTP 401")
