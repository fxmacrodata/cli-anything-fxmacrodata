---
name: "cli-anything-fxmacrodata"
description: >-
  Agent-native CLI for FXMacroData: official macroeconomic releases with publication
  timestamps, release calendars and FX rates for 22 currencies.
---

# FXMacroData CLI Skill

## Identity
- **Name**: cli-anything-fxmacrodata
- **Version**: 1.0.0
- **Category**: finance
- **Entry Point**: `cli-anything-fxmacrodata`

## What This CLI Does
Wraps the FXMacroData REST API (`https://api.fxmacrodata.com/v1`). It answers questions
such as "what was the last US CPI print and when was it published", "when is the next
ECB decision" or "how has the RBA cash rate moved this year" with official-source data.
Every release carries the period it refers to, the time it was published and a link to
the publisher.

## Prerequisites
- Python >= 3.10
- Optional: `export FXMACRODATA_API_KEY="your-key"`. USD releases, the USD calendar and
  the catalogue work without a key. Other currencies and FX rates need one.

## Installation
```bash
pip install git+https://github.com/fxmacrodata/cli-anything-fxmacrodata.git
```

## Command Reference

### catalogue: indicators for a currency
```bash
cli-anything-fxmacrodata catalogue <currency>
```

### announcements: released values, newest first
```bash
cli-anything-fxmacrodata announcements <currency> <indicator> [--from YYYY-MM-DD] [--to YYYY-MM-DD] [-n 1-100] [--offset N]
```

### latest: the most recent release
```bash
cli-anything-fxmacrodata latest <currency> <indicator>
```

### calendar: scheduled releases
```bash
cli-anything-fxmacrodata calendar <currency> [--indicator SLUG] [--from YYYY-MM-DD] [--to YYYY-MM-DD]
```

### forex: daily FX rates (API key required)
```bash
cli-anything-fxmacrodata forex <base> <quote> [--from YYYY-MM-DD] [--to YYYY-MM-DD] [-n 1-100]
```

### server status: connectivity and key check
```bash
cli-anything-fxmacrodata server status
```

## JSON Output
Put `--json` before the subcommand. Data commands print the API response unchanged:
```bash
cli-anything-fxmacrodata --json latest usd inflation
```
Errors print `{"error": "...", "response": {...}}` and exit 1.

## Common Agent Patterns

### Find the slug first
```bash
cli-anything-fxmacrodata --json catalogue jpy
```

### Latest print with its publication time
```bash
cli-anything-fxmacrodata --json latest usd non_farm_payrolls
```
Read `data[0].date` (the period), `data[0].val` and `data[0].announcement_datetime_local`.

### Policy-rate path this year
```bash
cli-anything-fxmacrodata --json announcements usd policy_rate --from 2026-01-01
```

### What is due next
```bash
cli-anything-fxmacrodata --json calendar usd --from 2026-10-01 --to 2026-10-31
```

### Page through long histories
When `pagination.has_more` is true, rerun with `--offset <pagination.next_offset>`.

## Interactive REPL
```bash
cli-anything-fxmacrodata   # no subcommand enters the REPL
```

## Notes
- HTTP 401 or 403 means the currency or dataset needs an API key; say so instead of guessing a value.
- Keyless USD data is the most recent 90 days and each release becomes readable 15 minutes after publication.
- Keyless traffic has a fair-use allowance of 100 requests per day.
