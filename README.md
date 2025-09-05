Tulipee — a small async Zulip bot playground.

Handlers include a YouTrack issue creator that listens to a specific stream/topic and creates issues using an optional LLM step to structure titles/descriptions.

Quick start
- Configure `.env` (see below), then run: `uv run python -m tulipee`

Container
- Build locally: `docker build -t cookieshake/tulipee:dev .`
- Run: `docker run --rm -e ZULIP_URL=... -e API_KEY=... -e EMAIL=... -e YOUTRACK_URL=... -e YOUTRACK_TOKEN=... -e OPENAI_API_KEY=... cookieshake/tulipee:dev`

CI/CD
- GitHub Actions workflow builds and pushes `cookieshake/tulipee` on pushes to `main` and tags `v*`.
- Configure repo secrets:
  - `DOCKERHUB_USERNAME`
  - `DOCKERHUB_TOKEN` (Docker Hub access token)

Configuration (.env)
- `ZULIP_URL` — Zulip server base URL
- `API_KEY` — Zulip bot API key
- `EMAIL` — Zulip bot email
- `LOG_LEVEL` — optional, default `DEBUG`
- `YOUTRACK_URL` — YouTrack base URL (e.g., https://youtrack.example.com)
- `YOUTRACK_TOKEN` — YouTrack permanent token (Bearer)
 - `OPENAI_API_KEY` — for LLM parsing via OpenRouter/OpenAI; if not set, uses fallback
 - `OPENAI_BASE_URL` — default `https://openrouter.ai/api/v1` (recommended)
 - `OPENAI_MODEL` — e.g., `openrouter/auto` (default) or a specific model name
 - `OPENAI_HTTP_REFERER` — optional, your site URL for OpenRouter attribution
 - `OPENAI_APP_TITLE` — optional, app name for OpenRouter attribution

YouTrack Create Issue handler
- Listens on Zulip stream `youtrack`, topic `create issue`.
- Message body is parsed into `title`/`description` via OpenAI if configured; otherwise uses first line as title and the rest as description.
- Selects the target project using the catalog defined in `tulipee/handlers/youtrack_projects.py` and LLM guidance, then replies with the issue link.

Notes
- Never commit your `.env` or tokens. Use environment variables in CI.
- The YouTrack handler requires valid URL, token, and a project id.
