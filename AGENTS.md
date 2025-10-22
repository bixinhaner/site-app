# Repository Guidelines

## Rule
- Always do not generate .md file when running tasks if user do not ask.
- If temporary verification and test scripts or code are generated during the task, please create them in the project's temp directory. If the directory does not exist, create it. Additionally, please delete them after completing the task. Other temporary files or code that do not affect business operations during the task should also be placed in the temp directory.

## Project Structure & Module Organization
- Root helpers: `start_backend.py` boots the FastAPI server; `docs/` holds reference material; DB snapshots live under `db/`.
- `backend/app/` contains the FastAPI application, with routers, models, and utilities grouped by feature; script-style tests sit alongside in `backend/test_*.py`.
- `web-admin/` hosts the Vue 3 + Vite admin UI (`src/`, `router/`, `views/`, static assets in `public/`).
- `uniapp-site-manager/` provides the UniApp mobile client (`pages/`, `stores/`, `config/`, `manifest.json`). Runtime uploads persist in `backend/uploads/` (keep out of version control).

## Build, Test, and Development Commands
- `python3 -m venv venv && ./venv/bin/pip install -r backend/requirements.txt` — create an isolated backend environment.
- `python3 start_backend.py` or `uvicorn app.main:app --reload --port 8000` (from `backend/`) — launch the API locally on port 8000.
- `python backend/test_login.py` / `python backend/test_task_api.py` — run smoke tests against the live API (users seeded such as `admin/admin123`).
- `npm install && npm run dev` in `web-admin/` — start the Vue admin console with hot reload.
- `npm install && npm run dev` in `uniapp-site-manager/` — launch the UniApp dev server (requires `@dcloudio/uni-cli` or HBuilderX).

## Coding Style & Naming Conventions
- Python follows PEP 8: 4-space indents, `snake_case` for functions/variables, `PascalCase` for classes, type hints on touched signatures.
- Vue/JS uses 2-space indents, single quotes, trailing commas; Single File Components named in `PascalCase` (e.g., `EquipmentList.vue`).
- Keep REST endpoints under `/api/...`; colocate request/response schemas with their router modules.

## Testing Guidelines
- Backend tests are standalone scripts; ensure the API is running before executing them.
- Name new tests `backend/test_<feature>.py` and target local endpoints.
- No automated frontend tests; validate critical UI flows manually and capture evidence for PRs.

## Commit & Pull Request Guidelines
- Use Conventional Commit headers, e.g., `feat(web-admin): add stock history view`; keep messages concise and imperative.
- PRs should summarize motivation, link issues, list verification steps, attach UI screenshots when UI changes, and call out config or env updates.

## Security & Configuration Tips
- Load backend config from `backend/.env` (copy from `.env.example`); never commit secrets or `.db` artifacts.
- Limit CORS to required origins in development and production.
- Treat `backend/uploads/` as runtime storage only; do not store credentials or long-lived assets there.
