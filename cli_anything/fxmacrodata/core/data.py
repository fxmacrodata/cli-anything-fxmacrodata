"""Read operations over the FXMacroData API.

Each function returns the API's JSON payload unchanged, so ``--json`` output
keeps every field, unit, source link and data-quality flag the API publishes.
"""

from __future__ import annotations

from typing import Any

from cli_anything.fxmacrodata.utils import fxmacrodata_backend as backend


def catalogue(currency: str) -> dict[str, Any]:
    """Indicators available for a currency, keyed by slug."""
    return backend.expect_object(backend.get(f"/data_catalogue/{backend.currency_code(currency)}"))


def announcements(
    currency: str,
    indicator: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Released values for one indicator, newest first, with publication times."""
    path = f"/announcements/{backend.currency_code(currency)}/{backend.indicator_slug(indicator)}"
    payload = backend.get(
        path,
        {
            "start_date": backend.iso_date(start_date, "--from"),
            "end_date": backend.iso_date(end_date, "--to"),
            "limit": limit,
            "offset": offset,
        },
    )
    return backend.expect_rows(payload)


def calendar(
    currency: str,
    *,
    indicator: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Scheduled releases for a currency."""
    payload = backend.get(
        f"/calendar/{backend.currency_code(currency)}",
        {
            "indicator": backend.indicator_slug(indicator) if indicator else None,
            "start_date": backend.iso_date(start_date, "--from"),
            "end_date": backend.iso_date(end_date, "--to"),
        },
    )
    return backend.expect_rows(payload)


def forex(
    base: str,
    quote: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Daily FX rates for a currency pair (needs an API key)."""
    path = f"/forex/{backend.currency_code(base, 'base')}/{backend.currency_code(quote, 'quote')}"
    payload = backend.get(
        path,
        {
            "start_date": backend.iso_date(start_date, "--from"),
            "end_date": backend.iso_date(end_date, "--to"),
            "limit": limit,
        },
    )
    return backend.expect_rows(payload)
