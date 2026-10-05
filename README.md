# cli-anything-fxmacrodata

An agent-native command line for [FXMacroData](https://fxmacrodata.com/?utm_source=github&utm_medium=referral&utm_campaign=cli-anything-fxmacrodata&utm_content=readme), built as a [CLI-Anything](https://github.com/HKUDS/CLI-Anything) harness. It gives agents and scripts official macroeconomic releases with their publication timestamps, release calendars and FX rates for 22 currencies, with `--json` on every command and an interactive REPL.

```bash
pip install git+https://github.com/fxmacrodata/cli-anything-fxmacrodata.git

cli-anything-fxmacrodata latest usd inflation
cli-anything-fxmacrodata calendar usd --indicator non_farm_payrolls
cli-anything-fxmacrodata --json announcements usd policy_rate --from 2026-01-01
```

USD releases, the USD release calendar and the indicator catalogue work without an account. Other currencies and FX rates need an API key in `FXMACRODATA_API_KEY`; see [plans](https://fxmacrodata.com/subscribe?utm_source=github&utm_medium=referral&utm_campaign=cli-anything-fxmacrodata&utm_content=readme) and the [API reference](https://fxmacrodata.com/documentation/reference?utm_source=github&utm_medium=referral&utm_campaign=cli-anything-fxmacrodata&utm_content=readme).

## Commands

| Command | What it returns |
|---------|-----------------|
| `catalogue <currency>` | Indicator slugs with names, units and sources |
| `announcements <currency> <indicator>` | Released values, newest first, with `--from`, `--to`, `-n`, `--offset` |
| `latest <currency> <indicator>` | The most recent release |
| `calendar <currency>` | Scheduled releases, with `--indicator`, `--from`, `--to` |
| `forex <base> <quote>` | Daily FX rates (key required) |
| `server status` | Connectivity and whether a key is configured |

With `--json`, data commands print the API response unchanged, so units, source links and data-quality fields are all there. Errors print `{"error": ..., "response": ...}` and exit 1. Running the command with no subcommand opens the REPL.

The agent skill is in [`skills/cli-anything-fxmacrodata/SKILL.md`](skills/cli-anything-fxmacrodata/SKILL.md), with a copy shipped inside the package.

## Security notes

- The only network endpoint is `https://api.fxmacrodata.com/v1`, called with the standard library. The only runtime dependencies are `click` and `prompt-toolkit`.
- The key is read from the environment, stripped, and rejected if it contains whitespace or control characters. It is sent as an `X-API-Key` header, redirects are refused so the header is never replayed elsewhere, and it is removed from any error text.

## Tests

```bash
pip install -e ".[dev]"
pytest cli_anything/fxmacrodata/tests/test_core.py -v          # mocked, no network
FXMD_E2E=1 pytest cli_anything/fxmacrodata/tests/test_full_e2e.py -v   # live keyless USD calls
```

## License

MIT. `cli_anything/fxmacrodata/utils/repl_skin.py` is copied from CLI-Anything under the Apache License 2.0; see [NOTICE](NOTICE).
