"""fxmacrodata_cli.py: CLI harness for FXMacroData.

Agent-native command line over the FXMacroData API:
  - the indicator catalogue for a currency
  - released values with publication timestamps and source links
  - scheduled release calendars
  - daily FX rates

Usage (non-interactive):
    cli-anything-fxmacrodata catalogue usd
    cli-anything-fxmacrodata latest usd inflation
    cli-anything-fxmacrodata --json announcements usd policy_rate --from 2026-01-01
    cli-anything-fxmacrodata calendar usd --indicator inflation
    cli-anything-fxmacrodata forex eur usd -n 5
    cli-anything-fxmacrodata server status

Usage (interactive REPL):
    cli-anything-fxmacrodata
"""

from __future__ import annotations

import functools
import json
import os
import sys
from typing import Any

import click

from cli_anything.fxmacrodata.core import data as data_core
from cli_anything.fxmacrodata.utils.fxmacrodata_backend import check_connectivity

VERSION = "1.0.0"

_json_output: bool = False


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _out(payload: Any, render) -> None:
    """Emit the API payload as JSON, or render it for a human."""
    if _json_output:
        click.echo(json.dumps(payload, indent=2, default=str))
    else:
        render(payload)


def _table(headers: list[str], rows: list[list[Any]]) -> None:
    if not rows:
        click.echo("No rows returned.")
        return
    cells = [[("" if c is None else str(c)) for c in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) for i, h in enumerate(headers)]
    click.echo("  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip())
    click.echo("  ".join("-" * w for w in widths))
    for row in cells:
        click.echo("  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip())


def _render_catalogue(payload: dict[str, Any]) -> None:
    rows = []
    for slug, meta in payload.items():
        meta = meta if isinstance(meta, dict) else {}
        rows.append([slug, meta.get("name"), meta.get("unit"), meta.get("source")])
    _table(["indicator", "name", "unit", "source"], rows)


def _render_announcements(payload: dict[str, Any]) -> None:
    click.echo(f"{payload.get('name') or payload.get('indicator')} ({payload.get('currency')}), "
               f"source: {payload.get('source')}")
    rows = [
        [row.get("date"), row.get("val"), row.get("announcement_datetime_local") or "unknown", row.get("source_url")]
        for row in payload.get("data", [])
    ]
    _table(["period", "value", "published", "source_url"], rows)
    pagination = payload.get("pagination") or {}
    if pagination.get("has_more"):
        click.echo(f"More rows available: rerun with --offset {pagination.get('next_offset')}")


def _render_calendar(payload: dict[str, Any]) -> None:
    rows = [
        [
            row.get("announcement_datetime_local") or row.get("announcement_datetime_utc"),
            row.get("name"),
            row.get("release"),
            row.get("event_importance"),
        ]
        for row in payload.get("data", [])
    ]
    _table(["time (local)", "release", "indicator", "importance"], rows)


def _render_forex(payload: dict[str, Any]) -> None:
    click.echo(f"{payload.get('base')}/{payload.get('quote')}, source: {payload.get('source')}")
    _table(["date", "rate"], [[row.get("date"), row.get("val")] for row in payload.get("data", [])])


def _render_status(payload: dict[str, Any]) -> None:
    status = "OK" if payload.get("ok") else "ERROR"
    click.echo(f"[{status}] {payload.get('message', '')}")
    click.echo(f"base_url: {payload.get('base_url')}")
    click.echo(f"api_key_set: {payload.get('api_key_set')}")


def _err(msg: str, payload: Any = None) -> None:
    if _json_output:
        body: dict[str, Any] = {"error": msg}
        if isinstance(payload, dict):
            body["response"] = payload
        click.echo(json.dumps(body))
    else:
        click.echo(f"Error: {msg}", err=True)


def _handle_errors(fn):
    """Catch API and validation errors and exit 1 with a clear message."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except RuntimeError as exc:
            _err(str(exc), getattr(exc, "payload", None))
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            _err(f"Unexpected error: {exc}")
            sys.exit(1)

    return wrapper


_date_option_from = click.option("--from", "start_date", default=None, metavar="YYYY-MM-DD",
                                 help="Start date.")
_date_option_to = click.option("--to", "end_date", default=None, metavar="YYYY-MM-DD", help="End date.")


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Emit the API response as JSON.")
@click.version_option(VERSION, prog_name="cli-anything-fxmacrodata")
@click.pass_context
def cli(ctx: click.Context, use_json: bool) -> None:
    """CLI harness for FXMacroData: official macroeconomic releases, calendars and FX rates.

    Run without a subcommand to enter the interactive REPL.
    USD data works without a key; set FXMACRODATA_API_KEY for other currencies and FX rates.
    """
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ---------------------------------------------------------------------------
# Data commands
# ---------------------------------------------------------------------------


@cli.command("catalogue")
@click.argument("currency")
@_handle_errors
def catalogue_cmd(currency: str) -> None:
    """List the indicators available for CURRENCY (slug, name, unit, source)."""
    _out(data_core.catalogue(currency), _render_catalogue)


@cli.command("announcements")
@click.argument("currency")
@click.argument("indicator")
@_date_option_from
@_date_option_to
@click.option("--limit", "-n", default=20, show_default=True, type=click.IntRange(1, 100),
              help="Rows per page (1-100).")
@click.option("--offset", default=None, type=click.IntRange(0), help="Row offset for paging.")
@_handle_errors
def announcements_cmd(currency: str, indicator: str, start_date: str | None, end_date: str | None,
                      limit: int, offset: int | None) -> None:
    """Released values of INDICATOR for CURRENCY, newest first, with publication times."""
    payload = data_core.announcements(currency, indicator, start_date=start_date, end_date=end_date,
                                      limit=limit, offset=offset)
    _out(payload, _render_announcements)


@cli.command("latest")
@click.argument("currency")
@click.argument("indicator")
@_handle_errors
def latest_cmd(currency: str, indicator: str) -> None:
    """The most recent release of INDICATOR for CURRENCY."""
    _out(data_core.announcements(currency, indicator, limit=1), _render_announcements)


@cli.command("calendar")
@click.argument("currency")
@click.option("--indicator", default=None, help="Only releases of this indicator slug.")
@_date_option_from
@_date_option_to
@_handle_errors
def calendar_cmd(currency: str, indicator: str | None, start_date: str | None, end_date: str | None) -> None:
    """Scheduled releases for CURRENCY, in the publisher's local time."""
    payload = data_core.calendar(currency, indicator=indicator, start_date=start_date, end_date=end_date)
    _out(payload, _render_calendar)


@cli.command("forex")
@click.argument("base")
@click.argument("quote")
@_date_option_from
@_date_option_to
@click.option("--limit", "-n", default=20, show_default=True, type=click.IntRange(1, 100),
              help="Rows per page (1-100).")
@_handle_errors
def forex_cmd(base: str, quote: str, start_date: str | None, end_date: str | None, limit: int) -> None:
    """Daily FX rates for BASE/QUOTE (needs FXMACRODATA_API_KEY)."""
    payload = data_core.forex(base, quote, start_date=start_date, end_date=end_date, limit=limit)
    _out(payload, _render_forex)


# ---------------------------------------------------------------------------
# server
# ---------------------------------------------------------------------------


@cli.group("server")
def server_group() -> None:
    """API connectivity commands."""


@server_group.command("status")
@_handle_errors
def server_status() -> None:
    """Check that the API is reachable and whether an API key is configured."""
    result = check_connectivity()
    _out(result, _render_status)
    if not result.get("ok"):
        sys.exit(1)


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------


@cli.command("repl")
def repl() -> None:
    """Start the interactive REPL (default when no subcommand is given)."""
    import shlex

    # The shared skin suggests installing the skill from this repository.
    os.environ.setdefault("CLI_ANYTHING_SKILL_REPO", "fxmacrodata/cli-anything-fxmacrodata")
    from cli_anything.fxmacrodata.utils.repl_skin import ReplSkin

    skin = ReplSkin(software="fxmacrodata", version=VERSION)
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    while True:
        try:
            line = skin.get_input(pt_session).strip()
        except (KeyboardInterrupt, EOFError):
            skin.print_goodbye()
            break

        if not line:
            continue
        if line.lower() in ("exit", "quit", "q"):
            skin.print_goodbye()
            break

        try:
            cli.main(args=shlex.split(line), standalone_mode=False)
        except SystemExit:
            pass
        except ValueError as exc:
            _err(f"Invalid input: {exc}")
        except Exception as exc:  # noqa: BLE001
            _err(str(exc))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
