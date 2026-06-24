# Log Observability – Testing Rig

Three independent sub-projects for testing observability tooling. All emit JSON-structured logs with correlation IDs.

## Sub-projects

### `emily/` – Python Flask app (port 5000)
- **Files:** `api_server.py` (Flask REST + frontend), `db_server.py` (SQLite backing), `init_db.py` (standalone DB setup)
- **Dependency:** `Flask==3.0.3` (`pip install -r emily/requirements.txt`)
- **Run:** `python emily/api_server.py` (auto-creates `grades.db` on startup)
- **Import bug:** `api_server.py:14` has `import testing_rig.Emily.db_server` — this will **fail** at runtime. The path doesn't match directory layout. Fix depends on intended packaging (no `setup.py`/`pyproject.toml` exists).
- Logs to `emily/app_activity.log` and stdout (JSON format, same file shared by api & db modules).

### `Reem/` – Node.js auth microservice (port 3000)
- **File:** `app.js` (Express 5, single `POST /validate-token` endpoint)
- **Dependency:** `express@^5.2.1` (`npm install`)
- **Run:** `node Reem/app.js`
- **Hardcoded token:** Validates against `"secret-group-token-123"` (`app.js:9`).
- **No test script** — `package.json` test is a placeholder (`echo "Error: no test specified"`).

### `Annika/` – Kubernetes + Docker deployment configs
- Three microservices, each with a Dockerfile and K8s manifests:
  - **`api-ms`** – Python/Flask (Linux), port 5000. Env vars: `AUTH_URL=http://auth-service:3000`, `DB_URL=http://db-service:6000`
  - **`db-ms`** – Python (Linux), port 6000. Uses `emptyDir` volume at `/data`. FROM `python:3`, no pinned version.
  - **`auth-ms`** – Node.js (**Windows container**, `windowsservercore-ltsc2025`), port 3000. Node selector `kubernetes.io/os: windows`.
- **No `app.py` or `requirements.txt` are committed** inside `Annika/services/*/` — they would need to be written before the Dockerfiles can build.
- All K8s services are `ClusterIP` (not exposed externally).

## Architecture notes

- `Annika/k8s/api-ms/deployment.yaml` references `auth-service:3000` (the Reem app) and `db-service:6000` (the Annika db-ms). The `emily/` API (`api_server.py`) runs in-process with its DB and has a commented-out auth integration (lines 91–94) pointing at Reem.
- There is **no monorepo tooling, no linter config, no formatter config, no CI**.
- The `.gitignore` patterns in `emily/` exclude `*.db`, `*.sqlite`, `*.log`, and Python cache dirs.

### `final/` – Unified K8s deployment

Separates the emily/ monolith into two Linux services and runs auth on a Windows node:

| Service | Port | Node OS | Source | Image tag |
|---------|------|---------|--------|-----------|
| `api-ms` (`final/services/api-ms/app.py`) | 5000 | Linux | Adapted from `emily/api_server.py` — calls db-ms via HTTP instead of in-process import. Serves frontend. | `final-api-ms:latest` |
| `db-ms` (`final/services/db-ms/app.py`) | 6000 | Linux | Adapted from `emily/db_server.py` — now a standalone Flask HTTP server with POST `/init`, POST `/grades`, GET `/grades`. SQLite stored on `emptyDir` at `/data`. | `final-db-ms:latest` |
| `auth-ms` (`final/services/auth-ms/app.js`) | 3000 | Windows | Same as `Reem/app.js` — validates against `secret-group-token-123`. | `final-auth-ms:windows-latest` |

K8s manifests under `final/k8s/` — all `ClusterIP` services. Node selectors: `kubernetes.io/os: linux` for api-ms/db-ms, `kubernetes.io/os: windows` for auth-ms.

**Build from** `final/services/*/` directories. The api-ms Dockerfile includes `templates/` and `static/` for the frontend. The auth-ms Dockerfile expects `package.json` + `package-lock.json` in the build context (they are checked in under `final/services/auth-ms/`).

The `final/services/api-ms/app.py` includes token validation against auth-ms (commented out by default — enable by uncommenting the early return in `attach_correlation_id`).

**Local run** — `final/run_all.ps1` builds both Linux Docker images, launches db-ms/api-ms as Linux containers, and runs auth-ms natively on the Windows host (via `host.docker.internal`). Requires Docker Desktop in Linux container mode. Stop with `final/stop_all.ps1` or Ctrl+C.

## Common gotchas

- Do not try to install `testing_rig` as a package — there is no setup/pyproject and the import in `api_server.py` is currently broken.
- The Annika K8s auth-ms requires a **Windows** node pool; api-ms and db-ms require **Linux** nodes.
- The auth-ms Dockerfile uses `npm ci` but expects `package.json`/`package-lock.json` in its build context (`Annika/services/auth-ms/`), which doesn't have them. The real source files are in `Reem/`.
