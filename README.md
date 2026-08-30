# LearnQuest AI

**AI-Powered Personalized Learning Platform with a Real-Time Avatar Tutor**

A web-based learning platform where students get personalized recommendations, AI-generated
quizzes, adaptive lessons, and a real-time animated avatar tutor — wrapped in a gamified
XP / badge / streak system.

| | |
| --- | --- |
| **Frontend** | React 18 + Vite + Tailwind CSS + React Router + Framer Motion |
| **Backend** | FastAPI + SQLAlchemy + Alembic |
| **Database** | PostgreSQL (Supabase free tier) |
| **Auth** | Supabase Auth |
| **AI** | LLM API (Groq / Gemini / OpenAI, pluggable) |
| **Avatar** | Browser TTS + viseme lipsync (Tier A) → SyncTalk 2D, GPU service (Tier B) |
| **Voice** | LiveKit + Gemini Live realtime agent (optional — see `agent/`) |

---

## Team & modules

| Member | Module | Section in [plan.md](plan.md) |
| --- | --- | --- |
| Member 1 (Lead) | AI Avatar Tutor & Intelligent Learning | §6 |
| Member 2 | Learning Management | §7 |
| Member 3 | User & Administration | §8 |
| Member 4 | Gamification & Analytics | §9 |

**Before you write any code:** read [plan.md](plan.md) §0–§4, then your own section.
**After you finish anything:** tick it off in [CHECKLIST.md](CHECKLIST.md).

---

## Quick start

### 1. Clone

```bash
git clone https://github.com/sahilaf/LearnQuest-Ai.git
```

### 2. Backend

```bash
cd backend
```

```bash
python -m venv .venv
```

Activate it — Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install and configure:

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env
```

Fill in `.env` (see the table below), then run the migrations and the server:

```bash
alembic upgrade head
```

```bash
uvicorn app.main:app --reload
```

API docs: <http://localhost:8000/docs> · Health check: <http://localhost:8000/api/health>

> **No credentials yet?** The backend boots without a database or Supabase key.
> Auth falls back to a dev user and the LLM falls back to `MockLLMClient`, so you can
> build UI on day 1 while Member 3 sets up Supabase.

### 3. Frontend

```bash
cd frontend
```

```bash
npm install
```

```bash
cp .env.example .env
```

```bash
npm run dev
```

App: <http://localhost:5173>

---

## Environment variables

### `backend/.env`

| Variable | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | for real data | Supabase Postgres connection string |
| `SUPABASE_URL` | for real auth | project URL |
| `SUPABASE_JWT_SECRET` | for real auth | verifies access tokens locally |
| `SUPABASE_SERVICE_ROLE_KEY` | server only | bypasses RLS - never expose to the frontend |
| `LLM_PROVIDER` | yes | `groq` \| `gemini` \| `openai` \| `mock` |
| `LLM_API_KEY` | unless `mock` | provider API key |
| `LLM_MODEL` | yes | e.g. `llama-3.3-70b-versatile` |
| `AVATAR_SERVICE_URL` | no | empty = Tier A browser avatar only |
| `CORS_ORIGINS` | yes | comma-separated allowed origins |
| `DEV_ALLOW_ANONYMOUS` | dev only | `true` lets requests through without a Supabase token |

### `frontend/.env`

| Variable | Notes |
| --- | --- |
| `VITE_API_URL` | backend base URL, e.g. `http://localhost:8000` |
| `VITE_SUPABASE_URL` | project URL |
| `VITE_SUPABASE_ANON_KEY` | anon/public key - safe in the bundle |

---

## Common commands

Run the backend:

```bash
uvicorn app.main:app --reload
```

Create a migration after changing models:

```bash
alembic revision --autogenerate -m "describe the change"
```

Apply migrations:

```bash
alembic upgrade head
```

Reseed demo data:

```bash
python -m app.seed.seed_data
```

Run the frontend dev server:

```bash
npm run dev
```

---

## Project layout

```
LearnQuest/
├── plan.md          # the full development plan - read this first
├── CHECKLIST.md     # tick your tasks off here as you finish them
├── context.md       # original project proposal
├── backend/         # FastAPI app
├── frontend/        # React app
├── avatar-service/  # SyncTalk 2D talking-head service (GPU, optional - Tier B)
└── agent/           # LiveKit + Gemini Live voice agent (optional)
```

`avatar-service/` and `agent/` are both **optional**. Leave `AVATAR_SERVICE_URL` empty and
the app runs the text tutor with the Tier A browser avatar — no GPU, no LiveKit, no
realtime API. That is how Members 2, 3 and 4 should run it.

See [avatar-service/README.md](avatar-service/README.md) and [agent/README.md](agent/README.md).

Detailed folder-by-folder ownership is in [plan.md](plan.md) §1.

---

## Working agreement

- `main` is always deployable. Branch as `m1/...`, `m2/...`, `m3/...`, `m4/...`.
- Every PR needs one review. Keep PRs under ~400 lines.
- Never edit a file another member owns — ask them or open a PR they review.
- Shared files (`main.py`, `App.jsx`, `client.js`, `components/ui/*`) change only by agreement.
- Update [CHECKLIST.md](CHECKLIST.md) in the same PR as the work it describes.
