# Repository Guidelines

## Project Structure & Module Organization
- Root: `start_backend.py` (backend helper), `docs/`, DB snapshots.
- `backend/`: FastAPI app in `app/`, scripts, Python deps in `requirements.txt`, uploads in `backend/uploads/`, script-style tests `backend/test_*.py`.
- `web-admin/`: Vue 3 + Vite admin UI (`src/`, `router/`, `views/`).
- `uniapp-site-manager/`: UniApp mobile app (`pages/`, `stores/`, `config/`, `manifest.json`).

## Build, Test, and Development Commands
- Backend setup: `python3 -m venv venv && ./venv/bin/pip install -r backend/requirements.txt`.
- Run API (dev): `python3 start_backend.py` or `cd backend && uvicorn app.main:app --reload --port 8000`.
- Quick tests (API running at `http://localhost:8000`): `python backend/test_login.py`, `python backend/test_task_api.py` (seeded users e.g., `admin/admin123`).
- Web Admin: `cd web-admin && npm install`; dev `npm run dev`; build `npm run build`; preview `npm run preview`.
- UniApp: `cd uniapp-site-manager && npm install`; dev `npm run dev` (needs `@dcloudio/uni-cli`/HBuilderX); H5 build `npm run build:h5:prod`.

## Coding Style & Naming Conventions
- Python: PEP8, 4-space indent, `snake_case` for functions/vars, `PascalCase` for classes; add type hints on edit. Keep REST under `/api/...`; keep request/response models with routers in `backend/app/...`.
- Vue/JS: 2-space indent, single quotes, trailing commas. SFCs use `PascalCase` (e.g., `EquipmentList.vue`); routes live in `web-admin/router/index.js`.

## Testing Guidelines
- Backend: tests are standalone scripts; run individually while the API is up. Name new tests `backend/test_<feature>.py` and hit local endpoints.
- Frontends: no unit tests; verify critical flows manually and attach screenshots to PRs.

## Commit & Pull Request Guidelines
- Commits: concise, imperative; prefer Conventional Commits, e.g., `feat(web-admin): add stock history view`.
- PRs: include summary, motivation, linked issues, test steps, screenshots (UI), and notes on env/config changes. Update docs if commands or structure change.

## Security & Configuration Tips
- Backend config from `backend/.env` (copy from `.env.example`); never commit secrets.
- Avoid committing `*.db` and local artifacts. Enable CORS only as needed in development.
- Treat `backend/uploads/` as runtime data; do not store secrets there.

