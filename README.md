# Squatter

A multiplayer web version of Squatter, the Australian sheep-station board
game. FastAPI + PostgreSQL backend, React (Vite) frontend, server-driven
AI opponents, and Server-Sent Events for real-time play.

## Layout

- `app/` — API routes, SQLAlchemy models, game-rule services
  (turn manager, space resolver, stock sale, cards, AI)
- `web-client/` — React frontend (built into the backend's static mount)
- `alembic/` — schema migrations (run on every boot via `start.sh`)
- `data/` — board, card, and price data seeded at startup
- `tests/` — pytest suite (see below)

## Running tests

```bash
./run_tests.sh            # all tests
./run_tests.sh -k lobby   # just the lobby/auth tests
```

The script creates `.venv/` on first use with the newest Python ≥ 3.10 it
can find (the system `python3` may be too old for this codebase's type
hints). Tests run against a throwaway SQLite database and never touch
PostgreSQL. Note SQLite ignores `FOR UPDATE` row locks — concurrency
guards are tested behaviourally; the lock itself relies on Postgres in
production.

## Deployment

Pushed commits on `main` deploy to Railway. See `DEPLOYMENT.md`.
Destructive `/admin/*` endpoints require the `ADMIN_SECRET` environment
variable and matching `X-Admin-Secret` header.
