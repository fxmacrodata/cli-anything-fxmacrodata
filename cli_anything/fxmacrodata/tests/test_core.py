"""
test_core.py: unit tests for the FXMacroData CLI harness.

All HTTP is mocked; no real API calls are made.
Run with: pytest cli_anything/fxmacrodata/tests/test_core.py -v
"""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.fxmacrodata.fxmacrodata_cli import cli
from cli_anything.fxmacrodata.utils import fxmacrodata_backend as backend

ANNOUNCEMENTS = {
    "currency": "USD",
    "indicator": "inflation",
    "name": "Inflation (CPI)",
    "source": "BLS",
    "pagination": {"limit": 2, "offset": 0, "has_more": True, "next_offset": 2},
    "data": [
        {
            "date": "2026-08-31",
            "val": 3.4,
            "announcement_datetime_local": "2026-09-11T08:30:00-04:00",
            "source_url": "https://www.bls.gov/news.release/archives/cpi_09112026.htm",
        },
        {"date": "2026-07-31", "val": 3.4, "announcement_datetime_local": None, "source_url": None},
    ],
}

CALENDAR = {
    "currency": "USD",
    "data": [
        {
            "release": "inflation",
            "name": "Inflation (CPI)",
            "announcement_datetime_utc": "2026-10-14T12:30:00+00:00",
            "announcement_datetime_local": "2026-10-14T08:30:00-04:00",
            "event_importance": "high",
        }
    ],
}

CATALOGUE = {
    "gdp": {"name": "GDP", "unit": "USD bn", "source": "BEA"},
    "inflation": {"name": "Inflation (CPI)", "unit": "%YoY", "source": "BLS"},
}


def _response(payload, status: int = 200):
    """A context-manager stand-in for the object urlopen returns."""
    body = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body.encode() if isinstance(body, str) else body
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def _http_error(status: int, payload) -> urllib.error.HTTPError:
    body = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
    return urllib.error.HTTPError("https://api.fxmacrodata.com/v1/x", status, "error", {}, io.BytesIO(body))


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def no_key(monkeypatch):
    monkeypatch.delenv(backend.API_KEY_ENV, raising=False)


def _sent_request(mock_open):
    return mock_open.call_args[0][0]


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------


class TestValidation:
    def test_currency_code_lowercases(self):
        assert backend.currency_code(" USD ") == "usd"

    @pytest.mark.parametrize("bad", ["us", "usdd", "u$d", "", "us dollar"])
    def test_currency_code_rejects(self, bad):
        with pytest.raises(RuntimeError, match="three-letter"):
            backend.currency_code(bad)

    def test_indicator_slug_rejects_path_characters(self):
        with pytest.raises(RuntimeError, match="slug"):
            backend.indicator_slug("../forex")

    def test_date_validation(self):
        assert backend.iso_date("2026-01-01", "--from") == "2026-01-01"
        with pytest.raises(RuntimeError, match="YYYY-MM-DD"):
            backend.iso_date("01/01/2026", "--from")


class TestApiKey:
    def test_keyless_sends_no_header(self):
        with patch.object(backend._OPENER, "open", return_value=_response(CATALOGUE)) as mock_open:
            backend.get("/data_catalogue/usd")
        assert _sent_request(mock_open).get_header("X-api-key") is None

    def test_key_is_stripped_and_sent(self, monkeypatch):
        monkeypatch.setenv(backend.API_KEY_ENV, "  secret-key-123\n")
        with patch.object(backend._OPENER, "open", return_value=_response(CATALOGUE)) as mock_open:
            backend.get("/data_catalogue/usd")
        assert _sent_request(mock_open).get_header("X-api-key") == "secret-key-123"

    def test_key_with_inner_whitespace_is_rejected_without_echoing_it(self, monkeypatch):
        monkeypatch.setenv(backend.API_KEY_ENV, "secret key")
        with patch.object(backend._OPENER, "open") as mock_open:
            with pytest.raises(RuntimeError) as exc:
                backend.get("/data_catalogue/usd")
        assert "secret" not in str(exc.value)
        mock_open.assert_not_called()

    def test_key_is_redacted_from_error_text(self, monkeypatch):
        monkeypatch.setenv(backend.API_KEY_ENV, "secret-key-123")
        error = _http_error(403, {"detail": "Key secret-key-123 is not valid for EUR"})
        with patch.object(backend._OPENER, "open", side_effect=error):
            with pytest.raises(backend.APIError) as exc:
                backend.get("/announcements/eur/inflation")
        assert "secret-key-123" not in str(exc.value)
        assert "[redacted]" in str(exc.value)

    def test_network_error_text_is_redacted(self, monkeypatch):
        monkeypatch.setenv(backend.API_KEY_ENV, "secret-key-123")
        with patch.object(backend._OPENER, "open", side_effect=urllib.error.URLError("bad secret-key-123")):
            with pytest.raises(RuntimeError) as exc:
                backend.get("/calendar/usd")
        assert "secret-key-123" not in str(exc.value)


class TestRedirects:
    def test_opener_refuses_redirects(self):
        handler = backend._NoRedirect()
        req = MagicMock(full_url="https://api.fxmacrodata.com/v1/calendar/usd")
        with pytest.raises(urllib.error.HTTPError, match="Refusing redirect"):
            handler.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, "http://evil.example/x")

    def test_redirect_surfaces_as_error(self, runner, monkeypatch):
        monkeypatch.setenv(backend.API_KEY_ENV, "secret-key-123")
        error = _http_error(302, b"")
        with patch.object(backend._OPENER, "open", side_effect=error):
            result = runner.invoke(cli, ["--json", "calendar", "usd"])
        assert result.exit_code == 1
        assert "HTTP 302" in result.output
        assert "secret-key-123" not in result.output


class TestResponseShape:
    def test_error_body_with_200_is_an_error(self):
        with patch.object(backend._OPENER, "open", return_value=_response({"detail": "quota exceeded"})):
            with pytest.raises(backend.APIError, match="quota exceeded"):
                backend.get("/calendar/usd")

    def test_non_json_body_is_an_error(self):
        with patch.object(backend._OPENER, "open", return_value=_response("<html>gateway</html>")):
            with pytest.raises(RuntimeError, match="not JSON"):
                backend.get("/calendar/usd")

    @pytest.mark.parametrize("payload", [[], {"data": "x"}, {"data": [1, 2]}, {"rows": []}])
    def test_malformed_list_payloads_are_rejected(self, runner, payload):
        with patch.object(backend._OPENER, "open", return_value=_response(payload)):
            result = runner.invoke(cli, ["calendar", "usd"])
        assert result.exit_code == 1
        assert "Unexpected response shape" in result.output

    def test_malformed_catalogue_is_rejected(self, runner):
        with patch.object(backend._OPENER, "open", return_value=_response(["gdp"])):
            result = runner.invoke(cli, ["catalogue", "usd"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "FXMacroData" in result.output

    def test_catalogue_table(self, runner):
        with patch.object(backend._OPENER, "open", return_value=_response(CATALOGUE)) as mock_open:
            result = runner.invoke(cli, ["catalogue", "USD"])
        assert result.exit_code == 0
        assert _sent_request(mock_open).full_url == "https://api.fxmacrodata.com/v1/data_catalogue/usd"
        assert "inflation" in result.output and "BLS" in result.output

    def test_announcements_json_is_unchanged_payload(self, runner):
        with patch.object(backend._OPENER, "open", return_value=_response(ANNOUNCEMENTS)) as mock_open:
            result = runner.invoke(
                cli, ["--json", "announcements", "usd", "inflation", "--from", "2026-01-01", "-n", "2"]
            )
        assert result.exit_code == 0
        assert json.loads(result.output) == ANNOUNCEMENTS
        url = _sent_request(mock_open).full_url
        assert url.startswith("https://api.fxmacrodata.com/v1/announcements/usd/inflation?")
        assert "start_date=2026-01-01" in url and "limit=2" in url

    def test_announcements_table_shows_publication_time_and_paging(self, runner):
        with patch.object(backend._OPENER, "open", return_value=_response(ANNOUNCEMENTS)):
            result = runner.invoke(cli, ["announcements", "usd", "inflation"])
        assert "2026-09-11T08:30:00-04:00" in result.output
        assert "unknown" in result.output
        assert "--offset 2" in result.output

    def test_latest_requests_one_row(self, runner):
        with patch.object(backend._OPENER, "open", return_value=_response(ANNOUNCEMENTS)) as mock_open:
            runner.invoke(cli, ["latest", "usd", "inflation"])
        assert "limit=1" in _sent_request(mock_open).full_url

    def test_calendar_with_indicator(self, runner):
        with patch.object(backend._OPENER, "open", return_value=_response(CALENDAR)) as mock_open:
            result = runner.invoke(cli, ["calendar", "usd", "--indicator", "inflation"])
        assert result.exit_code == 0
        assert "indicator=inflation" in _sent_request(mock_open).full_url
        assert "2026-10-14T08:30:00-04:00" in result.output

    def test_forex_401_explains_key(self, runner):
        error = _http_error(401, {"detail": "This endpoint requires an Individual or Business API key."})
        with patch.object(backend._OPENER, "open", side_effect=error):
            result = runner.invoke(cli, ["--json", "forex", "eur", "usd"])
        assert result.exit_code == 1
        body = json.loads(result.output)
        assert body["error"].startswith("HTTP 401")
        assert body["response"]["detail"].startswith("This endpoint requires")

    def test_invalid_currency_never_calls_api(self, runner):
        with patch.object(backend._OPENER, "open") as mock_open:
            result = runner.invoke(cli, ["calendar", "dollars"])
        assert result.exit_code == 1
        mock_open.assert_not_called()

    def test_server_status(self, runner):
        with patch.object(backend._OPENER, "open", return_value=_response(CATALOGUE)):
            result = runner.invoke(cli, ["--json", "server", "status"])
        assert result.exit_code == 0
        body = json.loads(result.output)
        assert body["ok"] is True and body["api_key_set"] is False
