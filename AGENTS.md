# Repository Guidelines

## Project Structure & Module Organization
- Source: `tulipee/` — core package.
  - `app.py`: App startup and message loop.
  - `client.py`: Async Zulip API client and models.
  - `settings.py`: `.env`-backed configuration via `pydantic-settings`.
  - `__main__.py`: CLI entry (`python -m tulipee`).
- Config: `pyproject.toml` (Python 3.13+, deps), `uv.lock` (dependency lock).
- Secrets: `.env` (not committed). Example:
  - `ZULIP_URL=https://your.zulip.domain`
  - `API_KEY=...`
  - `EMAIL=you@example.com`

## Build, Test, and Development Commands
- Setup (recommended, `uv`): `uv sync` — creates `.venv` and installs locked deps.
- Run (uv): `uv run python -m tulipee` — starts the echo bot.
- Fallback (pip):
  - Create venv: `python -m venv .venv && source .venv/bin/activate`
  - Install deps: `pip install httpx pydantic pydantic-settings`
  - Run: `python -m tulipee`

## Coding Style & Naming Conventions
- Indentation: 4 spaces; line length ~88–100 chars.
- Naming: `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Types: Use type hints throughout; prefer explicit `Optional`, `Literal`, and `List` from `typing`.
- Async IO: Prefer async HTTP (`httpx.AsyncClient`) and streaming patterns consistent with `client.py`.

## Testing Guidelines
- Location: Place tests in `tests/` mirroring package paths (e.g., `tests/test_client.py`).
- Framework: `pytest` is preferred; run with `pytest -q`.
- Coverage: Aim for critical paths — queue registration, event polling, and send message error handling. Mock HTTP with responses or adapters.

## Commit & Pull Request Guidelines
- Commits: Imperative mood, concise scope (e.g., "Add echo loop backoff"). Group related changes.
- PRs: Include description, rationale, screenshots/logs when relevant, and repro/verification steps.
- Checks: Ensure the app runs locally (`python -m tulipee`) and that config is documented. No secrets in diffs.

## Security & Configuration Tips
- Never commit `.env` or credentials. Use `.env` locally; set real env vars in CI.
- Handle failures by raising informative errors (as in `client.py`) and avoid logging secrets.
