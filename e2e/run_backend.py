"""Start the backend for end-to-end tests, on a fresh database.

Playwright runs this (see playwright.config.js). Each run:
  1. deletes and re-creates a SQLite file in the system temp folder (never your
     Supabase DB; not in the repo, where Dropbox would lock it mid-test),
  2. seeds it with the normal seed scripts (courses, quizzes, badges, practice),
  3. starts uvicorn on port 8100 with every outside AI service scripted
     (E2E_FAKE_AI=1, see backend/app/services/e2e_fakes.py) and dev login on.

The environment set here overrides backend/.env, so real keys in that file
are never used by the tests.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
DATA = Path(tempfile.gettempdir()) / "learnquest-e2e"
DB = DATA / "e2e.db"
PORT = os.environ.get("E2E_BACKEND_PORT", "8100")
FRONTEND_ORIGIN = os.environ.get("E2E_FRONTEND_ORIGIN", "http://localhost:5180")

python = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

env = {
    **os.environ,
    "DATABASE_URL": f"sqlite:///{DB.as_posix()}",
    "E2E_FAKE_AI": "1",
    "APP_ENV": "development",
    "DEV_ALLOW_ANONYMOUS": "true",
    # Blank out anything that could reach a real service.
    "LLM_PROVIDER": "mock",
    "LLM_API_KEY": "",
    "OPENROUTER_API_KEY": "",
    "SUPABASE_URL": "",
    "SUPABASE_JWT_SECRET": "",
    "SUPABASE_SERVICE_ROLE_KEY": "",
    "AVATAR_SERVICE_URL": "",
    "CORS_ORIGINS": f"{FRONTEND_ORIGIN},http://127.0.0.1:{FRONTEND_ORIGIN.rsplit(':', 1)[-1]}",
    "PYTHONIOENCODING": "utf-8",
}

DATA.mkdir(exist_ok=True)
DB.unlink(missing_ok=True)
for module in ("app.seed.seed_data", "app.seed.practice_problems"):
    subprocess.run([str(python), "-m", module], cwd=BACKEND, env=env, check=True)

sys.exit(subprocess.call(
    [str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", PORT],
    cwd=BACKEND, env=env,
))
