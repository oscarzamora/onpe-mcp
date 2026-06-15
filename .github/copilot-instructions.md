# Copilot Instructions

## Commands

```bash
pip install -e .          # install with dev extras: pip install -e ".[dev]"
onpe-mcp                  # run the MCP server
pytest                    # run all tests
pytest tests/test_utils.py::test_validate_mesa_code_normaliza  # single test
```

Tests are in `tests/`, configured with `-q` and no external network calls (monkeypatch all HTTP).

## Architecture

This is a Python MCP server exposing 6 tools for querying Peruvian electoral results (ONPE). The entry point is `onpe_mcp.server:main`, which initializes module-level singletons at import time.

**Two API pathways run in parallel:**

- `OnpeScraperGateway` (`gateway.py`) — dynamically imports `OnpeExtractor` from the sibling repo `onpeescraper` by injecting its `src/` directory into `sys.path` at runtime. The sibling repo path is resolved from `ONPE_SCRAPER_ROOT` (or `../onpeescraper` by default). This is why `server.py` has `# pyright: reportMissingImports=false` at the top.
- `OnpeApiClient` (`onpe_api.py`) — direct HTTP client to `resultadoelectoral.onpe.gob.pe`. Uses `curl_cffi` with `impersonate="chrome124"` to bypass ONPE's bot detection; falls back to `urllib` if `curl_cffi` is not installed.

**Persistence layer** (`storage.py` → `DataStore`):
- `data/onpe_denorm.db` — SQLite runtime única del MCP (facts/dims + tablas runtime cache)
- `data/raw/events.jsonl` — append-only audit log of every tool call
- `data/reports/` — markdown daily summaries

**Configuration** (`config.py`): single frozen `Settings` dataclass loaded via `Settings.from_env()`. Copy `.env.example` to `.env` to configure paths. Settings are read once at module import — restart the server to pick up env changes.

## Key Conventions

**Tool response shape** — every `@mcp.tool()` function must return via `ok_response()` or `error_response()` from `utils.py`:
```python
{"ok": True,  "data": ..., "errors": [],           "meta": {"duration_ms": N}}
{"ok": False, "data": None, "errors": [{"code": ..., "message": ...}], "meta": {...}}
```

**Mesa codes** — always normalized to 6-digit zero-padded strings via `validate_mesa_code()`. Never pass raw user input directly to API calls.

**Cache-first strategy** — `onpe_get_mesa` checks SQLite before hitting the live API. Use `force_live=True` to bypass. The `onpe_get_mesas_batch` tool does NOT check cache (always live).

**Text normalization** — accent-insensitive search throughout: `unicodedata.normalize("NFKD")` + strip combining chars + `casefold()`. Use `_norm()` or `_normalize_search_text()` for any user-facing string matching.

**Error hierarchy**:
- `ValueError` — validation failures (bad mesa code format, oversized batch)
- `GatewayError` — `onpeescraper` import or invocation failures
- `OnpeApiError` — HTTP/JSON failures from ONPE endpoints

**Acta selection priority** (implemented in both `OnpeApiClient._pick_mesa_acta` and `onpe_api.py`):
1. `idEleccion` match + `Contabilizada`
2. Any `Contabilizada`
3. `idEleccion` match only
4. First available

**ONPE API tolerance** — field types from ONPE are mixed (`number|string`). Always coerce with `_to_int()`. Validate for `data` array presence before parsing. The API may return HTML instead of JSON if request headers don't properly impersonate a browser.

**Foreign geo catalog** — country/city data for overseas voters lives in the `ubigeos_extranjero` SQLite table, populated by `onpe_sync_foreign_catalog`. If `ONPE_AUTO_SYNC_FOREIGN_CATALOG_ON_DEMAND=true`, `onpe_chat` will trigger a sync automatically on cold start.
