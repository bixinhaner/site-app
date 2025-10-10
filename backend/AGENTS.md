# Repository Guidelines

## Project Structure & Module Organization
- Root helpers: `start_backend.py` boots the FastAPI server; `docs/` holds reference material; DB snapshots live under `db/`.
- `backend/app/` contains the FastAPI app with routers, models, and utilities grouped by feature; smoke tests live alongside as `backend/test_*.py`.
- `web-admin/` hosts the Vue 3 + Vite admin UI (`src/`, `router/`, `views/`, static assets in `public/`).
- `uniapp-site-manager/` is the UniApp mobile client (`pages/`, `stores/`, `config/`, `manifest.json`). Runtime uploads persist in `backend/uploads/` and are excluded from version control.

## Build, Test, and Development Commands
- Backend env: `python3 -m venv venv && ./venv/bin/pip install -r backend/requirements.txt`.
- Run API: `python3 start_backend.py` or (from `backend/`) `uvicorn app.main:app --reload --port 8000`.
- Smoke tests: `python backend/test_login.py`, `python backend/test_task_api.py` (ensure API is running; seeded user `admin/admin123`).
- Web admin: `cd web-admin && npm install && npm run dev`.
- UniApp: `cd uniapp-site-manager && npm install && npm run dev` (requires `@dcloudio/uni-cli` or HBuilderX).

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indents; `snake_case` for functions/variables, `PascalCase` for classes; add type hints on touched signatures.
- JS/Vue: 2-space indents, single quotes, trailing commas. SFCs named in `PascalCase` (e.g., `EquipmentList.vue`).
- API: keep REST endpoints under `/api/...`; colocate request/response schemas with their router modules.

## Testing Guidelines
- Backend tests are standalone scripts hitting the live API; no framework runner needed.
- Name new tests `backend/test_<feature>.py` and target local endpoints.
- No automated frontend tests; validate critical UI flows manually and capture screenshots for PRs.

## Commit & Pull Request Guidelines
- Use Conventional Commits, e.g., `feat(web-admin): add stock history view`, `fix(backend): handle 401 on login`.
- PRs should summarize motivation, link issues, list verification steps, attach UI screenshots when UI changes, and call out config or env updates/migrations.

## Security & Configuration Tips
- Load backend config from `backend/.env` (copy from `.env.example`); never commit secrets or `.db` artifacts.
- Limit CORS to required origins in development and production.
- Treat `backend/uploads/` as runtime storage only; do not store credentials or long‑lived assets.

