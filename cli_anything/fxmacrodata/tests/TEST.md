# TEST.md: FXMacroData CLI harness

| Layer | File | API calls | Purpose |
|-------|------|-----------|---------|
| Unit | test_core.py | None (mocked) | Validation, key handling, redirects, response shapes, CLI output |
| E2E | test_full_e2e.py | Live API, keyless USD routes | Installed command end to end, JSON contract |

## Unit (`test_core.py`)

- Currency codes, indicator slugs and dates are validated before any request
- No `X-API-Key` header without a key; a key is stripped before use
- A key containing whitespace or control characters is rejected and never echoed
- The key is redacted from HTTP and network error text
- Redirects are refused, so the key header is never replayed to another host
- HTTP 200 with an error body, non-JSON bodies and malformed shapes are errors
- `--json` prints the API payload unchanged; tables show publication times and paging hints
- A 401 from `forex` exits 1 and includes the API's explanation

## E2E (`test_full_e2e.py`, `FXMD_E2E=1`)

- `server status`, `catalogue usd`, `latest usd inflation`, `calendar usd --indicator inflation`
- `forex eur usd` without a key exits 1 with HTTP 401

## Results

Recorded on 2026-10-05 with Python 3.12 (see the README for the commands).
