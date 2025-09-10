# Repository Guidelines

## Project Structure & Module Organization
- Root: backend services helper (`start_backend.py`), docs, DB snapshots.
- `backend/`: FastAPI app (`app/`), scripts, and test scripts (`test_*.py`), Python deps in `requirements.txt`.
- `web-admin/`: Vue 3 + Vite admin UI (`src/`, `router/`, `views/`).
- `uniapp-site-manager/`: UniApp mobile app (`pages/`, `stores/`, `config/`, `manifest.json`).
- Assets/uploads: `backend/uploads/` (runtime-created).

## Build, Test, and Development Commands
- Backend
  - Create venv and install: `python3 -m venv venv && ./venv/bin/pip install -r backend/requirements.txt`
  - Run API (dev): `python3 start_backend.py` or `cd backend && uvicorn app.main:app --reload --port 8000`
  - Quick tests: `python backend/test_login.py`, `python backend/test_task_api.py`
- Web Admin
  - `cd web-admin && npm install`
  - Dev server: `npm run dev`  Build: `npm run build`  Preview: `npm run preview`
- UniApp
  - `cd uniapp-site-manager && npm install`
  - Dev: `npm run dev` (requires `@dcloudio/uni-cli`/HBuilderX)  Build H5: `npm run build:h5:prod`

## Coding Style & Naming Conventions
- Python (backend): PEP8, 4-space indent, snake_case for functions/vars, PascalCase for classes; add type hints when editing.
- Vue/JS: Vue 3 SFCs; component files PascalCase (e.g., `EquipmentList.vue`), routes in `router/index.js`; 2-space indent, single quotes, trailing commas.
- APIs: Prefer RESTful paths under `/api/...`; keep request/response models in `backend/app/...` alongside routers.

## Testing Guidelines
- Backend tests are script-style in `backend/test_*.py`; run individually (e.g., `python backend/test_login.py`). Ensure the API is running on `http://localhost:8000` when tests expect a live server.
- Seed data: `start_backend.py` creates default users (admin/admin123, etc.).
- Frontends have no unit test harness; verify critical flows manually and attach screenshots for UI changes.

## Commit & Pull Request Guidelines
- Commits: concise imperative subject; use Conventional Commits where possible (e.g., `feat(web-admin): add stock history view`).
- PRs: include summary, motivation, linked issues, test steps, screenshots (UI), and notes on config/env changes. Update docs if commands or structure change.

## Security & Configuration Tips
- Backend config from `backend/.env` (copy from `.env.example`); never commit secrets. Avoid committing `*.db` and local artifacts. Enable CORS thoughtfully during dev.
