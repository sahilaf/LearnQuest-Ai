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
| **Avatar** | SyncTalk 2D over WebSocket, GPU service + Gemini TTS (`avatar-service/`) |
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

### 4. Run everything with one command

Once steps 2 and 3 are set up, start the avatar service, backend and frontend
together from the repo root (PowerShell):

```powershell
.\dev.ps1
```

It waits until each service answers its health check, opens the tutor page, and
**Ctrl+C stops all three**. Logs go to `.logs\<service>.log`.

No GPU? Skip the avatar; the tutor page shows "avatar offline" and everything
else works:

```powershell
.\dev.ps1 -NoAvatar
```

The avatar needs the `synctalk` conda env (found automatically; set
`SYNCTALK_PYTHON` if it lives elsewhere), `AVATAR_SERVICE_URL=http://localhost:5001`
and a Gemini key in `backend/.env`. It takes 40 s to 2 min to load. Run plugged
in. On battery the GPU throttles and the mouth gets choppy. See
[avatar-service/README.md](avatar-service/README.md).

If PowerShell refuses to run scripts, allow local ones once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

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
| `AVATAR_SERVICE_URL` | no | empty = no avatar; the tutor still answers in text |
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
the app runs the text tutor with no avatar — no GPU, no LiveKit, no realtime API. The
tutor page shows an "avatar offline" panel and everything else, including Teach-Back,
works normally. That is how Members 2, 3 and 4 should run it.

See [avatar-service/README.md](avatar-service/README.md) and [agent/README.md](agent/README.md).

Detailed folder-by-folder ownership is in [plan.md](plan.md) §1.

---

## Testing

| Level | Command | What it covers |
|---|---|---|
| Backend unit | `cd backend && .venv/Scripts/python.exe -m unittest discover -s tests` | 320 tests: services, routers, auth, the live socket |
| Frontend unit | `cd frontend && npm test` | Pure logic: speech splitting, live-call states |
| Frontend lint | `cd frontend && npm run lint` | ESLint 9 |
| **End to end** | `cd e2e && npm test` | 14 student journeys in a real browser against the real app, on a fresh database, with AI scripted — see [e2e/TEST_PLAN.md](e2e/TEST_PLAN.md) |

End-to-end setup, once: `cd e2e`, `npm install`, `npx playwright install chromium`.
`npm run report` opens the HTML report with a video and trace of every test.

---

## Provenance and consent

Declared here so nobody has to ask.

**Brought in from the team's FYDP project (`Fydp_v2`), not built for this course:**
the Alapon lip-sync model and its training pipeline (`avatar-service/`, trained on
the `redwan` recording), the avatar WebSocket server, and the design of the live
voice agent (`agent/`, kept for reference). What was built here is the
integration: the tutor page, Teach-Back, the live voice tutor
(`backend/app/routers/live.py`), speech routing, and everything else in
`backend/` and `frontend/`.

**The avatar is a real person.** The face, and the tutor's name, are those of
Redwan, the person recorded for the training data.

- [ ] Written consent from Redwan to use his likeness and name in LearnQuest is on
      file with the team (link it here before submission).

**Student data.** In a live call the student's voice is sent to Google Gemini;
the transcript is stored in that conversation; LearnQuest does not keep audio.
The Live tab says this before a call starts.

---

## Working agreement

- `main` is always deployable. Branch as `m1/...`, `m2/...`, `m3/...`, `m4/...`.
- Every PR needs one review. Keep PRs under ~400 lines.
- Never edit a file another member owns — ask them or open a PR they review.
- Shared files (`main.py`, `App.jsx`, `client.js`, `components/ui/*`) change only by agreement.
- Update [CHECKLIST.md](CHECKLIST.md) in the same PR as the work it describes.
- **Any frontend work follows [docs/DESIGN_GUIDELINES.md](docs/DESIGN_GUIDELINES.md).**
  LearnQuest uses a Duolingo-style design language — read it before building a
  page or component, and run its PR checklist before opening a review.
