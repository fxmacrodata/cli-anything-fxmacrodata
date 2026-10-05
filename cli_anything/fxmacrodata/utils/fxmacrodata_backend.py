"""HTTP backend for the FXMacroData REST API.

The "real software" behind this harness is the hosted API at
https://api.fxmacrodata.com/v1. This module is the only place that talks to it.
It uses the standard library only, so the harness adds no HTTP dependency.

Authentication: the key is read from FXMACRODATA_API_KEY and sent as an
``X-API-Key`` header. It is optional. USD releases, the USD release calendar
and the data catalogue answer without one; other currencies and FX rates
return HTTP 401 until a key is set.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = "https://api.fxmacrodata.com/v1"
API_KEY_ENV = "FXMACRODATA_API_KEY"
DEFAULT_TIMEOUT = 30.0
USER_AGENT = "cli-anything-fxmacrodata/1.0.0"

_CODE_RE = re.compile(r"^[A-Za-z]{3}$")
_SLUG_RE = re.compile(r"^[a-z0-9_]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_KEY_RE = re.compile(r"^[!-~]+$")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so the API key header is never replayed to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, f"Refusing redirect to {newurl}", headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirect)


class APIError(RuntimeError):
    """Raised when the API answers with an HTTP error status."""

    def __init__(self, status: int, message: str, payload: Any = None) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.payload = payload


def api_key() -> str | None:
    """Return the configured API key, or None when running keyless.

    The value is stripped and must be printable ASCII without spaces; anything
    else is rejected before a request is built, and the key is never echoed.
    """
    value = os.environ.get(API_KEY_ENV, "").strip()
    if not value:
        return None
    if not _KEY_RE.match(value):
        raise RuntimeError(f"{API_KEY_ENV} contains whitespace or non-printable characters; check the value")
    return value


def _redact(text: str, key: str | None) -> str:
    """Remove the API key from any text that may be shown to the user."""
    return text.replace(key, "[redacted]") if key else text


def currency_code(value: str, field: str = "currency") -> str:
    """Validate and lower-case a three-letter ISO currency code."""
    code = (value or "").strip()
    if not _CODE_RE.match(code):
        raise RuntimeError(f"{field} must be a three-letter currency code such as USD, got {value!r}")
    return code.lower()


def indicator_slug(value: str) -> str:
    """Validate an indicator slug such as 'inflation' or 'policy_rate'."""
    slug = (value or "").strip().lower()
    if not _SLUG_RE.match(slug):
        raise RuntimeError(
            f"indicator must be a slug such as inflation or policy_rate, got {value!r}. "
            "Run 'catalogue <currency>' to list the slugs."
        )
    return slug


def iso_date(value: str | None, field: str) -> str | None:
    """Validate an optional YYYY-MM-DD date."""
    if value is None:
        return None
    if not _DATE_RE.match(value):
        raise RuntimeError(f"{field} must be a date in YYYY-MM-DD form, got {value!r}")
    return value


def get(path: str, params: dict[str, Any] | None = None, timeout: float = DEFAULT_TIMEOUT) -> Any:
    """GET ``BASE_URL + path`` and return the decoded JSON body.

    Raises APIError for HTTP errors (with the API's ``detail`` message) and
    RuntimeError for network failures.
    """
    query = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"

    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    key = api_key()
    if key:
        headers["X-API-Key"] = key

    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        try:
            payload = json.loads(body)
        except ValueError:
            payload = None
        detail = payload.get("detail") if isinstance(payload, dict) else None
        message = _redact(str(detail or body[:300] or exc.reason), key)
        raise APIError(exc.code, message, payload) from None
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(_redact(f"Could not reach {BASE_URL}: {reason}", key)) from None

    try:
        payload = json.loads(raw)
    except ValueError:
        raise RuntimeError("The API returned a response that is not JSON") from None
    if isinstance(payload, dict) and ("detail" in payload or "error" in payload) and "data" not in payload:
        message = payload.get("detail") or payload.get("error")
        raise APIError(200, _redact(str(message), key), payload)
    return payload


def expect_rows(payload: Any) -> dict[str, Any]:
    """Check a list endpoint's shape: an object whose ``data`` is a list of objects."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError("Unexpected response shape: expected an object with a 'data' list")
    if not all(isinstance(row, dict) for row in payload["data"]):
        raise RuntimeError("Unexpected response shape: 'data' rows must be objects")
    return payload


def expect_object(payload: Any) -> dict[str, Any]:
    """Check that a response is a JSON object."""
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected response shape: expected a JSON object")
    return payload


def check_connectivity() -> dict[str, Any]:
    """Probe the API with a keyless-safe request and report whether a key is set."""
    key_set = bool(os.environ.get(API_KEY_ENV, "").strip())
    try:
        catalogue = expect_object(get("/data_catalogue/usd"))
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc), "base_url": BASE_URL, "api_key_set": key_set}
    return {
        "ok": True,
        "message": f"API reachable; USD catalogue lists {len(catalogue)} indicators",
        "base_url": BASE_URL,
        "api_key_set": key_set,
    }
