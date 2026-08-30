# LearnQuest AI — Development Plan

> Working plan for a 4-person, 4-week build.
> Read **§0 → §4** before writing any code. After that, jump straight to your own member section (§6–§9).

- **Duration:** 4 weeks (Agile, weekly sprints)
- **Team:** 4 members, each owning an end-to-end vertical slice (DB → API → UI)
- **Stack:** React + Tailwind (frontend) · FastAPI + SQLAlchemy (backend) · PostgreSQL (Supabase) · Firebase Auth · LLM API + SyncTalk (AI)

---

## 0. How to read this plan

Each member owns a **vertical slice**: the DB tables, the FastAPI routers, and the React pages for their feature. You do not hand your backend to someone else to build the UI for. This means:

- You can work without blocking on anyone else, as long as the **contracts in §3 and §4 are respected**.
- If you need to change a shared contract (a table another member reads, a response shape another member renders), you **must** open a PR that edits §3/§4 of this file first, and tell the team.
- "Done" means: migration applied + API returns real data + UI renders it + it still works after someone else does `git pull` on their machine.

**Ownership map:**

| Member | Module | Owns |
| --- | --- | --- |
| **Member 1 (Lead)** | AI Avatar Tutor & Intelligent Learning | `ai/`, `avatar/`, tutor chat, quiz generation, recommendations |
| **Member 2** | Learning Management | courses/lessons/quiz **consumption** UI, learner dashboard, learning history |
| **Member 3** | User & Administration | auth, users, course/lesson **CRUD**, admin panel, deployment |
| **Member 4** | Gamification & Analytics | XP, badges, streaks, challenges, leaderboard, analytics |

---

## 1. Repository structure

Single repo, two top-level apps.

```
LearnQuest/
├── plan.md
├── context.md
├── README.md
├── .gitignore
│
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/versions/         # ONE migration file per PR, never edit someone else's
│   └── app/
│       ├── main.py               # FastAPI app, CORS, router registration  [SHARED - see §2.4]
│       ├── config.py             # pydantic Settings, reads .env          [SHARED]
│       ├── database.py           # engine, SessionLocal, Base, get_db()   [SHARED]
│       ├── deps.py               # get_current_user, require_admin        [M3 owns]
│       ├── models/               # SQLAlchemy models, one file per domain
│       │   ├── user.py           # M3
│       │   ├── course.py         # M3 (courses, lessons, enrollments)
│       │   ├── quiz.py           # M2 owns attempts, M1 owns generated questions
│       │   ├── progress.py       # M2
│       │   ├── gamification.py   # M4
│       │   └── ai.py             # M1 (conversations, messages, mastery)
│       ├── schemas/              # Pydantic request/response models, same split
│       ├── routers/
│       │   ├── auth.py           # M3
│       │   ├── users.py          # M3
│       │   ├── admin.py          # M3
│       │   ├── courses.py        # M3 writes, M2 reads
│       │   ├── lessons.py        # M2
│       │   ├── progress.py       # M2
│       │   ├── quizzes.py        # M2 (attempts) + M1 (generation)
│       │   ├── tutor.py          # M1
│       │   ├── avatar.py         # M1
│       │   ├── recommendations.py# M1
│       │   ├── gamification.py   # M4
│       │   └── analytics.py      # M4
│       ├── services/             # business logic, no FastAPI imports in here
│       │   ├── llm_client.py     # M1
│       │   ├── prompts.py        # M1
│       │   ├── quiz_generator.py # M1
│       │   ├── recommender.py    # M1
│       │   ├── mastery.py        # M1
│       │   ├── tts.py            # M1
│       │   ├── xp_engine.py      # M4
│       │   └── events.py         # SHARED event bus - see §4.3
│       └── seed/seed_data.py     # M3 owns, everyone contributes fixtures
│
└── frontend/
    ├── package.json
    ├── tailwind.config.js
    ├── .env.example
    └── src/
        ├── main.jsx, App.jsx     # SHARED router - see §2.4
        ├── api/client.js         # SHARED axios instance + auth interceptor [M3]
        ├── api/                  # one file per module: courses.js, tutor.js, ...
        ├── context/AuthContext.jsx   # M3
        ├── components/ui/        # SHARED design system: Button, Card, Modal, Spinner...
        ├── components/avatar/    # M1
        ├── components/course/    # M2
        ├── components/game/      # M4
        ├── pages/                # one folder per member's pages
        └── hooks/
```

**Rule:** never edit a file owned by another member. If you need a change there, ask them or open a PR they review.

---

## 2. Week 0 / Day 1 — shared setup (do this together, 2–3 hours)

### 2.1 Accounts to create (all free tier)

| Service | Who | Purpose |
| --- | --- | --- |
| GitHub repo | M3 | source control |
| Supabase | M3 | PostgreSQL |
| Firebase | M3 | authentication |
| LLM provider key | M1 | tutor + quiz generation (see §6.2) |
| Vercel | M3 | frontend deploy |
| Render | M3 | backend deploy |

### 2.2 Backend bootstrap

```bash
cd backend && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
```

Then copy `.env.example` to `.env`, fill in the secrets, and run:

```bash
alembic upgrade head && uvicorn app.main:app --reload
```

`requirements.txt` baseline:

```
fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary
pydantic pydantic-settings python-dotenv
firebase-admin httpx python-multipart
```

### 2.3 Frontend bootstrap

```bash
cd frontend && npm install && npm run dev
```

Baseline deps: `react react-router-dom axios tailwindcss framer-motion firebase recharts lucide-react react-markdown`

### 2.4 Shared files — change only by agreement

`main.py`, `App.jsx`, `database.py`, `config.py`, `components/ui/*`, `api/client.js`.

These are merge-conflict magnets. Convention: each member adds **one line** to `main.py` (`app.include_router(...)`) and **one block** to `App.jsx` (their routes). Do it on day 1, all four at once, in a single commit — then nobody touches them again.

### 2.5 Git workflow

- `main` is always deployable. Never push directly to it.
- Branch names: `m1/avatar-pipeline`, `m2/lesson-viewer`, `m3/admin-crud`, `m4/xp-engine`
- Every PR needs 1 review. Keep PRs under ~400 lines — big ones sit unreviewed and rot.
- Rebase on main daily: `git pull --rebase origin main`
- Commit style: `feat(tutor): stream chat responses`, `fix(xp): streak reset off by one`

### 2.6 Daily rhythm

- 15-minute standup (async in the group chat is fine): yesterday / today / blockers.
- Friday: demo your slice working end to end, merge to `main`, tag `week-N`.

---

## 3. Database schema (single source of truth)

Migrations are **additive only** after Week 1. If you must change a column another module reads, announce it first.

```sql
-- ============ M3: identity & catalog ============
users (
  id UUID PK,
  firebase_uid TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  avatar_url TEXT,
  role TEXT NOT NULL DEFAULT 'student',   -- student | admin
  preferences JSONB DEFAULT '{}',         -- {tutor_tone, difficulty_pref, daily_goal_minutes, timezone}
  created_at TIMESTAMPTZ, last_login_at TIMESTAMPTZ
)

courses (
  id UUID PK, title TEXT NOT NULL, slug TEXT UNIQUE, description TEXT,
  subject TEXT, difficulty TEXT,          -- beginner | intermediate | advanced
  thumbnail_url TEXT, estimated_hours INT,
  is_published BOOLEAN DEFAULT false,
  created_by UUID FK->users, created_at TIMESTAMPTZ
)

lessons (
  id UUID PK, course_id UUID FK->courses, title TEXT,
  order_index INT NOT NULL,
  content_md TEXT,                        -- markdown body, also used as LLM context
  video_url TEXT, estimated_minutes INT,
  topic_tags TEXT[] DEFAULT '{}',         -- CRITICAL: drives mastery + recommendations
  created_at TIMESTAMPTZ
)

enrollments (
  id UUID PK, user_id UUID FK, course_id UUID FK,
  enrolled_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  UNIQUE(user_id, course_id)
)

-- ============ M2: learning activity ============
lesson_progress (
  id UUID PK, user_id UUID FK, lesson_id UUID FK,
  status TEXT DEFAULT 'not_started',      -- not_started | in_progress | completed
  seconds_spent INT DEFAULT 0,
  last_position INT DEFAULT 0,
  completed_at TIMESTAMPTZ,
  UNIQUE(user_id, lesson_id)
)

quizzes (
  id UUID PK, lesson_id UUID FK NULL, course_id UUID FK NULL,
  title TEXT, source TEXT DEFAULT 'manual',   -- manual | ai_generated
  difficulty TEXT, generated_by_user UUID FK NULL,
  topic_tags TEXT[] DEFAULT '{}', created_at TIMESTAMPTZ
)

questions (
  id UUID PK, quiz_id UUID FK,
  type TEXT,                              -- mcq | true_false | fill_blank | short_answer
  prompt TEXT NOT NULL,
  options JSONB,                          -- ["A","B","C","D"] for mcq, null otherwise
  correct_answer TEXT NOT NULL,
  explanation TEXT,
  topic_tag TEXT, difficulty TEXT, order_index INT
)

quiz_attempts (
  id UUID PK, user_id UUID FK, quiz_id UUID FK,
  score NUMERIC(5,2), total_questions INT, correct_count INT,
  started_at TIMESTAMPTZ, submitted_at TIMESTAMPTZ, duration_seconds INT
)

attempt_answers (
  id UUID PK, attempt_id UUID FK, question_id UUID FK,
  user_answer TEXT, is_correct BOOLEAN,
  topic_tag TEXT                          -- denormalised on purpose; M1 aggregates on this
)

-- ============ M1: AI layer ============
conversations (
  id UUID PK, user_id UUID FK, title TEXT,
  context_lesson_id UUID FK NULL, context_course_id UUID FK NULL,
  summary TEXT,                           -- rolling summary = long-term memory
  created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
)

messages (
  id UUID PK, conversation_id UUID FK,
  role TEXT,                              -- user | assistant | system
  content TEXT, tokens INT,
  audio_url TEXT NULL, visemes JSONB NULL,-- avatar playback payload
  created_at TIMESTAMPTZ
)

topic_mastery (
  id UUID PK, user_id UUID FK, topic_tag TEXT,
  mastery_score NUMERIC(4,3) DEFAULT 0.5, -- 0.0 .. 1.0
  attempts INT DEFAULT 0, correct INT DEFAULT 0,
  last_practiced_at TIMESTAMPTZ,
  UNIQUE(user_id, topic_tag)
)

recommendations (
  id UUID PK, user_id UUID FK,
  kind TEXT,                              -- lesson | revision | quiz | challenge
  target_id UUID, reason TEXT, score NUMERIC(4,3),
  is_dismissed BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ, expires_at TIMESTAMPTZ
)

-- ============ M4: gamification & analytics ============
user_stats (
  user_id UUID PK FK->users,
  xp INT DEFAULT 0, level INT DEFAULT 1, coins INT DEFAULT 0,
  current_streak INT DEFAULT 0, longest_streak INT DEFAULT 0,
  last_active_date DATE,
  total_learning_seconds INT DEFAULT 0
)

badges (
  id UUID PK, code TEXT UNIQUE, name TEXT, description TEXT,
  icon TEXT, criteria JSONB, xp_reward INT DEFAULT 0
)

user_badges (
  id UUID PK, user_id UUID FK, badge_id UUID FK, earned_at TIMESTAMPTZ,
  UNIQUE(user_id, badge_id)
)

xp_events (
  id UUID PK, user_id UUID FK, event_type TEXT, xp_awarded INT,
  ref_type TEXT, ref_id UUID, created_at TIMESTAMPTZ
)

daily_challenges (
  id UUID PK, date DATE, title TEXT, description TEXT,
  challenge_type TEXT, target_value INT, xp_reward INT, coin_reward INT
)

user_challenges (
  id UUID PK, user_id UUID FK, challenge_id UUID FK,
  progress_value INT DEFAULT 0, is_completed BOOLEAN DEFAULT false,
  completed_at TIMESTAMPTZ, UNIQUE(user_id, challenge_id)
)

notifications (
  id UUID PK, user_id UUID FK, type TEXT, title TEXT, body TEXT,
  is_read BOOLEAN DEFAULT false, created_at TIMESTAMPTZ
)
```

### 3.1 The two fields everything depends on

1. **`lessons.topic_tags`** — recommendations, mastery, and adaptive quizzes all key off this. M3 must enforce that every lesson has at least one tag; M1's engine is blind without it. Agree a controlled vocabulary in Week 1 (e.g. `python.loops`, `dbms.normalization`).
2. **`attempt_answers.topic_tag`** — copied from `questions.topic_tag` at submit time so mastery can be recomputed without a four-table join.

### 3.2 Migration etiquette

```bash
alembic revision --autogenerate -m "m4: add user_stats"
```

One migration per PR. If two migrations collide on `down_revision`, the **later merger** regenerates theirs.

---

## 4. Cross-module contracts

### 4.1 Auth (M3 provides, everyone consumes)

The frontend sends the Firebase ID token on every request as `Authorization: Bearer <firebase_id_token>`. The backend exposes two dependencies in `deps.py`:

```python
def get_current_user(...) -> User   # 401 if the token is invalid
def require_admin(...) -> User      # 403 if role != 'admin'
```

Every protected route takes `user: User = Depends(get_current_user)`. **Never** read `user_id` out of the request body — that is an authorization hole.

### 4.2 Standard response shapes

Success returns the resource itself. Errors are always:

```json
{ "detail": "Human readable message", "code": "QUIZ_NOT_FOUND" }
```

Lists are paginated with `?page=1&page_size=20` and return:

```json
{ "items": [], "total": 137, "page": 1, "page_size": 20 }
```

### 4.3 The event bus — how modules talk without importing each other

`app/services/events.py` (built by M4 in Week 1, used by everyone):

```python
def emit(db, user_id: UUID, event_type: str, payload: dict) -> None
```

Callers just emit. M4's handlers award XP, update streaks, check badges, and write notifications. **This is the only sanctioned cross-module coupling.**

| Event | Emitted by | Payload | M4 reaction |
| --- | --- | --- | --- |
| `lesson.completed` | M2 | `{lesson_id, course_id, seconds}` | +50 XP, streak, challenge progress |
| `quiz.submitted` | M2 | `{quiz_id, score, correct, total}` | +10–100 XP, "Quiz Master" badge |
| `course.enrolled` | M2/M3 | `{course_id}` | +20 XP |
| `tutor.session` | M1 | `{conversation_id, message_count}` | +5 XP, "Curious Mind" badge |
| `quiz.generated` | M1 | `{quiz_id, topic}` | challenge progress |
| `daily.login` | M3 | `{}` | streak increment |

M1 additionally **subscribes to** `quiz.submitted` to update `topic_mastery` (see §6.5).

### 4.4 Frontend API layer

All calls go through `src/api/client.js`. Never call `fetch` directly inside a component.

```js
// src/api/tutor.js
import client from './client';
export const sendMessage = (conversationId, text) =>
  client.post(`/api/tutor/conversations/${conversationId}/messages`, { content: text });
```

### 4.5 Design system (build day 1, M2 leads, everyone uses)

`components/ui/`: `Button`, `Card`, `Input`, `Modal`, `Spinner`, `Badge`, `ProgressBar`, `EmptyState`, `Toast`.

Tailwind tokens: primary `indigo-600`, success `emerald-500`, warning `amber-500`, danger `rose-500`, surface `slate-50` / `slate-900`. Dark mode via the `class` strategy. Radius `rounded-xl`, shadow `shadow-sm`.

---

## 5. Timeline at a glance

| Week | M1 (AI/Avatar) | M2 (Learning) | M3 (User/Admin) | M4 (Game/Analytics) |
| --- | --- | --- | --- | --- |
| **1** | LLM client, prompts, chat API, avatar spike | Course list/detail, lesson viewer, UI kit | Firebase auth, users, course+lesson CRUD, DB setup | Schema, `events.py`, XP engine, dashboard widgets |
| **2** | Streaming chat + memory, quiz generator | Quiz taking UI, progress tracking, dashboard | Admin panel, profile, roles, deploy pipeline | Badges, streaks, leaderboard |
| **3** | Avatar lipsync live, mastery + recommendations | Learning history, revision flow, mobile pass | Analytics feed for admin, security pass | Daily challenges, charts, notifications |
| **4** | Integration, latency tuning, fallbacks | Bug fixing, empty states, polish | Production deploy, seed data, docs | Full test pass, bug triage, presentation |

**Hard checkpoints**

- **End of W1:** login works, a real course renders from the DB, the tutor answers one question (even in the terminal).
- **End of W2:** a student can enroll → read a lesson → take an AI-generated quiz → see XP go up.
- **End of W3:** the avatar speaks with lipsync; the dashboard shows recommendations, streaks, and charts.
- **End of W4:** deployed, seeded, demoed.

---

## 6. Member 1 — AI Avatar Tutor & Intelligent Learning *(Team Lead)*

You own the differentiator. Everything else is a competent LMS; this module is what makes it LearnQuest AI. You are also the integrator, so budget roughly 20% of your time for unblocking other people.

**Files you own:** `services/llm_client.py`, `prompts.py`, `quiz_generator.py`, `recommender.py`, `mastery.py`, `tts.py`; `routers/tutor.py`, `avatar.py`, `recommendations.py`; `models/ai.py`; `frontend/src/components/avatar/*`, `pages/Tutor/*`; and `avatar-service/` (a separate process).

### 6.1 Architecture of your slice

```
Browser
  ├── ChatPanel ──HTTP/SSE──► FastAPI /api/tutor/... ──► LLMClient ──► LLM provider
  │                                     │
  │                                     ├──► ConversationMemory (summary + last N turns)
  │                                     └──► ContextBuilder (lesson content + mastery + progress)
  │
  └── AvatarStage ◄──audio + visemes── /api/avatar/speak ──► TTS ──► viseme extraction
                   ◄──MJPEG/WebRTC───── avatar-service (SyncTalk, GPU)   [Tier B, optional]
```

### 6.2 LLM provider decision (do this on Day 1)

Pick **one** and hide it behind `LLMClient` so swapping costs ten minutes:

| Option | Free tier | Notes |
| --- | --- | --- |
| **Groq** (llama-3.3-70b) | generous, very fast | recommended default — latency matters for a talking avatar |
| **Google Gemini** (2.0 Flash) | generous | good long context for lesson material |
| **OpenAI** (gpt-4o-mini) | paid only | best quality; use if you have credit |
| **Ollama** (local) | free | offline demo fallback; needs a decent machine |

```python
# services/llm_client.py
class LLMClient:
    async def complete(self, messages: list[dict], *, temperature=0.7,
                       max_tokens=800, json_mode=False) -> str: ...
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]: ...
```

Requirements: retry with exponential backoff (2 attempts), 30s timeout, log token counts into `messages.tokens`, and a `MockLLMClient` used when `LLM_PROVIDER=mock` so the other three can run the app without your API key. **Ship the mock in Week 1** — it removes you as a blocker for the rest of the team.

### 6.3 Conversation & memory system

**Context assembly** (`prompts.py::build_tutor_context`), in priority order:

1. System prompt — persona, teaching style, formatting rules, refusal rules
2. Learner profile — level, XP, top 3 weak topics, top 3 strong topics (from `topic_mastery`)
3. Current lesson content — `lessons.content_md`, truncated to roughly 2000 tokens
4. Conversation summary — `conversations.summary`
5. The last 8 message pairs verbatim

**Rolling summarisation:** once a conversation exceeds 16 messages, summarise messages 1..N-8 into `conversations.summary` with a cheap call and stop sending them. This keeps latency and cost flat over a long session instead of growing linearly.

**System prompt skeleton:**

```
You are LearnQuest, a patient AI tutor for {level} students.
Teaching rules:
- Never give the final answer immediately for a practice question; ask one guiding question first.
- Explain with a concrete example before the abstract definition.
- Keep replies under 120 words unless asked to elaborate - the reply is spoken aloud by an avatar.
- Use plain sentences. No markdown tables, no code blocks unless the topic is programming.
- If the learner is weak in {weak_topics}, connect explanations back to those gaps.
- If asked something outside the course scope, answer briefly and steer back to learning.
Current lesson: {lesson_title}
Lesson material: {lesson_excerpt}
```

**Endpoints:**

```
POST   /api/tutor/conversations                 -> {id, title}
GET    /api/tutor/conversations                 -> paginated list
GET    /api/tutor/conversations/{id}/messages   -> message history
POST   /api/tutor/conversations/{id}/messages   -> {reply, audio_url, visemes}
GET    /api/tutor/conversations/{id}/stream     -> SSE token stream
DELETE /api/tutor/conversations/{id}
POST   /api/tutor/explain                       -> {lesson_id, selection} -> explanation
```

Use **SSE** (`text/event-stream`), not WebSockets — simpler, works on Render's free tier, and `EventSource` is native in the browser.

### 6.4 AI quiz generator

`services/quiz_generator.py`:

```python
async def generate_quiz(db, *, lesson_id, user_id, num_questions=5,
                        difficulty="auto", types=("mcq", "true_false")) -> Quiz
```

Pipeline:

1. Load `lessons.content_md` and `topic_tags`.
2. If `difficulty == "auto"`, derive it from `topic_mastery`: `<0.4 → easy`, `0.4–0.75 → medium`, `>0.75 → hard`.
3. Call the LLM in **JSON mode** with a strict schema.
4. **Validate** with Pydantic; retry once on a parse failure; drop malformed questions rather than returning a 500.
5. Persist to `quizzes` + `questions` with `source='ai_generated'`, and return the quiz **in M2's exact quiz shape** so M2's existing player renders it with zero changes.
6. `emit(db, user_id, "quiz.generated", {...})`.

Output contract:

```json
{"questions": [{"type": "mcq", "prompt": "...", "options": ["a","b","c","d"],
                "correct_answer": "b", "explanation": "...",
                "topic_tag": "python.loops", "difficulty": "medium"}]}
```

Guardrails: reject any question whose `correct_answer` is not one of its `options`; reject duplicate prompts within a quiz; cap at 10 questions; rate-limit to 20 generations per user per day.

**Short-answer grading** — `POST /api/quizzes/attempts/{id}/grade-open` returns `{is_correct, score_0_1, feedback}`. M2 calls this only for `short_answer` questions.

**Endpoints:** `POST /api/quizzes/generate`, `POST /api/quizzes/generate/adaptive` (a weak-topic mix drawn from mastery, ignoring lesson scope).

### 6.5 Mastery model & recommendations

`services/mastery.py` — runs after every quiz submission (M2 emits, you subscribe):

```
for each topic_tag in the attempt:
    correct_rate = correct / attempted
    new = old + LEARNING_RATE * (correct_rate - old)     # LEARNING_RATE = 0.3
    if last_practiced more than 7 days ago: new *= 0.95  # time decay
    clamp to [0.05, 0.99]
```

Simple, explainable, and defensible in a viva. In the report, describe it as a simplified exponential-moving-average form of Bayesian Knowledge Tracing.

`services/recommender.py` — hybrid scoring, recomputed on dashboard load and cached for 1 hour in `recommendations`:

```
score = 0.45 * weakness      (1 - mastery of the lesson's topics)
      + 0.25 * prerequisite  (next unstarted lesson in an enrolled course)
      + 0.20 * recency       (topic not practiced in N days)
      + 0.10 * popularity    (completion rate across all users)
```

Every recommendation carries a human-readable `reason` — *"You scored 40% on loops last week."* The reason is what sells the feature in the demo; do not skip it.

**Endpoints:**

```
GET  /api/recommendations              -> [{kind, target_id, title, reason, score}]
POST /api/recommendations/{id}/dismiss
GET  /api/recommendations/daily-plan   -> {minutes, items: [...]}
GET  /api/analytics/mastery/me         -> [{topic_tag, mastery_score, attempts}]   (M4 renders this)
```

### 6.6 Avatar pipeline — two tiers, ship Tier A first

> **Risk, read before planning Week 1.** SyncTalk requires a CUDA GPU and per-identity training, and cannot run on the Render/Vercel free tier. Treat it as an enhancement running on a separate GPU box, not as the thing the demo depends on.

**Tier A — browser avatar (must ship, Weeks 1–2).** Zero infrastructure cost, works on any laptop.

- TTS: the Web Speech API `speechSynthesis` (free, offline, instant), or a server TTS endpoint returning MP3.
- Lipsync: map text/phonemes to a viseme timeline, then drive either
  - a **2D sprite/SVG mouth** swapped per viseme (simplest, perfectly fine for a college demo), or
  - a **Three.js / ReadyPlayerMe GLB** head with ARKit morph targets (`viseme_aa`, `viseme_O`, …) via `@react-three/fiber`.
- Idle animation: blink every 3–6s, subtle head sway, and expression states `neutral | thinking | explaining | encouraging` chosen by a keyword pass over the reply.
- Viseme payload contract (also stored in `messages.visemes`):

```json
[{"t": 0.00, "v": "sil"}, {"t": 0.08, "v": "AA"}, {"t": 0.19, "v": "M"}]
```

**Tier B — SyncTalk (Week 3, only if Tier A is stable).**

- Lives in a separate folder `avatar-service/`, run on a GPU machine (a lab PC, Colab + ngrok, or a friend's card).
- Pipeline: text → TTS wav → SyncTalk inference → frames → stream to the browser.
- Transport: MJPEG over HTTP is far easier than WebRTC and good enough for a demo. Use WebRTC (`aiortc`) only if you have time to spare.
- The contract stays identical: `POST /api/avatar/speak {text}` returns `{audio_url, visemes, video_stream_url?}`. The frontend renders Tier B when `video_stream_url` is present and falls back to Tier A otherwise. **Same endpoint, graceful degradation.**
- Prepare/train the avatar identity offline in Week 2, not during Week 3.

**Endpoints:** `POST /api/avatar/speak`, `GET /api/avatar/status` (which tier is live), `GET /api/avatar/config`.

### 6.7 Frontend you build

- `pages/Tutor/TutorPage.jsx` — split view: avatar stage on the left, chat on the right; stacks on mobile.
- `components/avatar/AvatarStage.jsx` — canvas/video plus the expression state machine.
- `components/avatar/useLipsync.js` — hook that maps an audio element's `currentTime` onto the viseme timeline via `requestAnimationFrame`.
- `components/tutor/ChatPanel.jsx` — SSE streaming, typing indicator, light markdown rendering, an "Explain this" entry point from a lesson selection, and a mic button (Web Speech recognition) as a stretch goal.
- `components/tutor/RecommendationCard.jsx` — used by M2's dashboard, so export it cleanly and keep the props stable.

### 6.8 Your week by week

- **W1:** LLM client + mock, prompt v1, `conversations`/`messages` tables and CRUD, non-streaming chat endpoint, minimal chat UI, Tier A avatar spike (mouth moves to `speechSynthesis`).
- **W2:** SSE streaming, memory + summarisation, quiz generator with validation and M2 integration, adaptive difficulty, TTS endpoint.
- **W3:** Accurate lipsync + expressions, mastery engine wired to `quiz.submitted`, recommender + daily plan, SyncTalk spike if there is time.
- **W4:** Latency tuning (target: under 2s to first token), quota/error fallbacks, prompt tuning against real usage, demo script, and integration support for everyone.

### 6.9 Definition of done

- [ ] The tutor answers in the context of the current lesson and remembers earlier turns in the session
- [ ] The avatar's mouth is visibly in sync with the speech, and idle animation runs
- [ ] Quiz generation produces valid, non-duplicate questions that M2's player renders unmodified
- [ ] Weak topics update after a quiz and visibly change the recommendations
- [ ] Every AI call has a timeout, a retry, and a user-visible fallback message
- [ ] `LLM_PROVIDER=mock` lets teammates run the whole app with no API key

---

## 7. Member 2 — Learning Management Module

You own the path a student actually walks: browse → enroll → learn → quiz → track. Most of the app's visible surface area is yours, so you also lead the shared UI kit.

**Files:** `routers/lessons.py`, `progress.py`, `quizzes.py` (attempts); `models/progress.py`, `models/quiz.py` (attempts); `components/ui/*`, `components/course/*`; `pages/Courses/*`, `pages/Lesson/*`, `pages/Quiz/*`, `pages/Dashboard/*`.

### 7.1 Build on day 1: the UI kit

`Button` (variants primary/secondary/ghost/danger, with a loading state), `Card`, `Input`, `Select`, `Modal`, `Spinner`, `ProgressBar`, `Badge`, `Tabs`, `EmptyState`, `Toast`.

Everyone else imports these. Ship them on the Monday of Week 1 or the app ends up with four different visual styles.

### 7.2 Pages

1. **Course catalog** `/courses` — grid, search, filter by subject and difficulty, enroll button, "enrolled" badge.
2. **Course detail** `/courses/:slug` — description, lesson list with completion ticks, "Continue where you left off", progress ring.
3. **Lesson viewer** `/lessons/:id` — markdown rendering (`react-markdown`), video embed, prev/next navigation, sticky outline sidebar, an **"Ask the tutor about this"** button (text selection → M1's `POST /api/tutor/explain`), auto "mark complete" at 90% scroll plus a manual button, and time-on-page tracking (heartbeat every 30s).
4. **Quiz player** `/quiz/:id` — one question per screen, timer, answer persistence across refresh, submit, a result screen with per-question explanations, and retake.
5. **Student dashboard** `/dashboard` — assembles widgets from all four modules: your progress cards, M4's XP/streak/challenges, M1's recommendations, and a recent activity feed.
6. **Learning history** `/history` — timeline of completed lessons and quiz attempts, filterable by course.

### 7.3 Endpoints you own

```
GET  /api/courses                       ?search=&subject=&difficulty=&page=
GET  /api/courses/{slug}
POST /api/courses/{id}/enroll
GET  /api/me/enrollments
GET  /api/lessons/{id}
POST /api/lessons/{id}/progress         {status, seconds_spent, last_position}
GET  /api/me/progress                   -> per-course completion %
GET  /api/me/history                    ?page=
GET  /api/quizzes/{id}                  -> questions WITHOUT correct_answer
POST /api/quizzes/{id}/attempts         -> {attempt_id}
POST /api/quizzes/attempts/{id}/submit  {answers: [{question_id, user_answer}]}
GET  /api/quizzes/attempts/{id}         -> result + explanations
```

**Security note:** `GET /api/quizzes/{id}` must strip `correct_answer` and `explanation`. Grading happens server-side only. This is the single easiest bug to ship in this project, and the easiest to catch in review.

**On submit you must:** write `attempt_answers` rows with `topic_tag` copied from each question, then call `emit(db, user, "quiz.submitted", {...})`. M1 and M4 both depend on that event — no event means no XP and no mastery update.

### 7.4 Your week by week

- **W1:** UI kit, catalog, course detail, lesson viewer reading real seeded data, enrollment.
- **W2:** Quiz player + attempts + results, lesson progress and completion, dashboard v1.
- **W3:** Learning history, the revision flow from M1's recommendations, responsive/mobile pass, `EmptyState` everywhere.
- **W4:** Bug fixing, loading skeletons, error states, cross-browser check.

### 7.5 Definition of done

- [ ] A new student can enroll, complete a lesson, take a quiz, and see it all in history
- [ ] Progress percentages stay correct after a refresh and on a second device
- [ ] Correct answers never appear in the pre-submit network response
- [ ] Every list has a loading skeleton and an empty state
- [ ] Everything is usable at 375px width

---

## 8. Member 3 — User & Administration Module

You own the foundation the other three stand on. Your Week 1 is the most time-critical work in the project: **nobody can build anything real until auth and seeded courses exist.**

**Files:** `deps.py`; `routers/auth.py`, `users.py`, `admin.py`, `courses.py` (writes); `models/user.py`, `course.py`; `seed/seed_data.py`; `api/client.js`, `context/AuthContext.jsx`; `pages/Auth/*`, `pages/Profile/*`, `pages/Admin/*`; plus all deployment config.

### 8.1 Week 1 is a sprint — deliver in this order

1. **Day 1:** Supabase project, connection string in `.env.example`, `database.py`, Alembic initialised, and the `users` / `courses` / `lessons` / `enrollments` tables migrated. Post the DB URL to the team.
2. **Day 2:** Firebase project, frontend `AuthContext` (email/password + Google), and `client.js` with the token interceptor.
3. **Day 3:** Backend token verification with `firebase-admin`, `get_current_user`, auto-create the `users` row on first login, and `require_admin`.
4. **Day 4:** **Seed data — 3 courses × 5 lessons with real markdown content and `topic_tags`.** M1 cannot test the tutor and M2 cannot test the viewer without this. It is your highest-leverage deliverable of the week.
5. **Day 5:** Course and lesson CRUD endpoints, and deploy a hello-world backend to Render and frontend to Vercel so the pipeline is proven early rather than on the last day.

### 8.2 Auth flow

```
Browser --Firebase SDK--> Firebase --idToken--> AuthContext
AuthContext --Bearer idToken--> FastAPI --verify_id_token--> firebase-admin
  -> look up users.firebase_uid -> create if absent -> return User
```

Handle: token refresh on a 401 (retry once), logout clearing state, `<PrivateRoute>` and `<AdminRoute>` wrappers, password reset via Firebase, and `emit(db, user, "daily.login", {})` on the first request of each day.

### 8.3 Endpoints

```
POST   /api/auth/sync             -> upsert the user from the token, return the profile
GET    /api/me                    -> profile + stats
PATCH  /api/me                    -> full_name, avatar_url, preferences
GET    /api/admin/users           ?search=&role=&page=
PATCH  /api/admin/users/{id}      -> role, is_active
POST   /api/admin/courses         | PATCH /api/admin/courses/{id} | DELETE
POST   /api/admin/courses/{id}/lessons | PATCH /api/admin/lessons/{id} | DELETE
POST   /api/admin/lessons/{id}/publish
POST   /api/admin/upload          -> returns a URL (Supabase Storage)
GET    /api/admin/overview        -> counts: users, courses, enrollments, active today
```

**Validation rule you enforce:** a lesson cannot be saved without at least one `topic_tag`. The admin lesson form gets a tag input with autocomplete over existing tags. This one check is what keeps M1's recommender alive.

### 8.4 Pages

Login, Register, Forgot password, Profile (edit details + preferences: tutor tone, daily goal minutes, difficulty, timezone), and an Admin shell with a sidebar leading to: Users table, Courses table, Course editor (markdown editor with preview, drag-to-reorder lessons, tag picker), and an Overview page (M4 supplies the charts).

### 8.5 Deployment (yours — start in Week 1, finish in Week 4)

- **Backend → Render:** start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, env vars set in the dashboard, and `alembic upgrade head` in the build command. Note the free tier sleeps after 15 minutes — add a keep-alive ping before the demo.
- **Frontend → Vercel:** set `VITE_API_URL` and `VITE_FIREBASE_*`. Add the SPA rewrite to `/index.html`.
- **CORS** in `main.py`: allow the Vercel domain and `http://localhost:5173`.
- Document every env var in both `.env.example` files.

### 8.6 Week by week

- **W1:** the sprint above.
- **W2:** admin panel CRUD complete, profile and settings, role management, staging deploy live.
- **W3:** security pass (rate limiting, input validation, no secrets committed, least-privilege on Supabase), admin analytics wiring, file upload.
- **W4:** production deploy, final seed (5+ courses), README + setup docs + API docs (FastAPI's `/docs` is free — curate the tags and descriptions so it reads well).

### 8.7 Definition of done

- [ ] Register → login → refresh → still logged in
- [ ] A student hitting an admin route gets a 403, and the admin nav is not rendered for them
- [ ] An admin can create a course and lessons that immediately appear in M2's catalog
- [ ] The seed script rebuilds a full demo database from empty in one command
- [ ] The deployed URLs work from another person's machine and from a phone

---

## 9. Member 4 — Gamification & Analytics Module

You own motivation and measurement — and you own `events.py`, which the whole app depends on. You are also the QA lead in Week 4.

**Files:** `services/events.py`, `xp_engine.py`; `routers/gamification.py`, `analytics.py`; `models/gamification.py`; `components/game/*`; `pages/Achievements/*`, `pages/Leaderboard/*`, `pages/Stats/*`.

### 9.1 Week 1, days 1–2: `events.py` — unblock the team

```python
# app/services/events.py
HANDLERS: dict[str, list[Callable]] = {}

def on(event_type): ...          # decorator used to register a handler
def emit(db, user_id, event_type, payload):
    """Synchronous, best-effort. A failing handler must NEVER fail the caller's request."""
```

Wrap each handler in try/except and log failures. M2's lesson completion must not return a 500 because a badge check has a bug.

### 9.2 XP & levels

```
lesson.completed          +50 XP
quiz.submitted            +10 base, +5 per correct answer, +25 perfect-score bonus
course.completed          +200 XP
tutor.session (>=3 msgs)  +5 XP  (capped at 25/day)
daily.login               +10 XP
daily challenge completed +challenge.xp_reward
streak bonus              +5 * min(current_streak, 10) on the first activity of the day
```

Level curve: `xp_for_level(n) = 100 * n^1.5` → level 2 at 283 XP, level 5 at 1118, level 10 at 3162.

Every XP award writes an `xp_events` row. That table is your analytics source of truth — never mutate `user_stats.xp` without a matching event row.

### 9.3 Streaks

On any activity: if `last_active_date == today`, do nothing; if it equals yesterday, increment; otherwise reset to 1. Update `longest_streak` alongside.

Compute this in the **user's local date** — take a timezone from `users.preferences` or send the client's date. Server-UTC silently breaks streaks for anyone east of London, and it is a bug that only surfaces during the demo.

### 9.4 Badges (seed about 15)

`first_lesson`, `first_quiz`, `perfect_score`, `quiz_master_10`, `course_complete`, `streak_3` / `streak_7` / `streak_30`, `night_owl`, `early_bird`, `curious_mind_50_msgs`, `comeback` (returned after 7 idle days), `topic_master` (mastery > 0.9), `level_5`, `level_10`.

`badges.criteria` is JSONB so the checker stays data-driven: `{"type": "count", "event": "lesson.completed", "threshold": 10}`. Earning a badge fires a Framer Motion celebration modal with confetti and writes a `notifications` row.

### 9.5 Daily challenges

Seed a pool of templates; a job (or lazy generation on the first request of the day) picks 3 for today: *"Complete 2 lessons"*, *"Score 80%+ on any quiz"*, *"Ask the tutor 5 questions"*, *"Study for 20 minutes"*, *"Practice a weak topic"* (that last one calls M1's `/api/recommendations`). Progress updates flow through the same event handlers.

### 9.6 Leaderboard

`GET /api/leaderboard?scope=global|course&period=weekly|alltime` — ranked by XP, top 50 plus the current user's own rank pinned even when they are outside the top 50. Weekly leaderboards sum `xp_events` over the window, which is exactly why every award needs an event row. Respect a `preferences.leaderboard_opt_out` flag.

### 9.7 Analytics

**Student** (`/stats`, plus widgets embedded in M2's dashboard) — all with Recharts:

- Weekly activity chart (minutes per day, last 8 weeks)
- XP over time (line)
- Topic mastery radar or horizontal bars (data from M1's `/api/analytics/mastery/me`)
- Quiz accuracy trend (line)
- Time-of-day study pattern
- Course completion donuts

**Admin** (feeds M3's admin overview) — DAU/WAU, new signups, course popularity, average completion rate, quiz difficulty analysis (the questions with the lowest correct rate — genuinely useful, and a great demo talking point), and tutor usage volume.

### 9.8 Endpoints

```
GET  /api/me/stats                  -> xp, level, next_level_xp, coins, streak, totals
GET  /api/me/badges                 -> earned + locked, with progress
GET  /api/challenges/today          -> 3 challenges with progress
POST /api/challenges/{id}/claim
GET  /api/leaderboard               ?scope=&period=
GET  /api/notifications             | POST /api/notifications/{id}/read
GET  /api/analytics/me/activity     ?days=56
GET  /api/analytics/me/summary
GET  /api/admin/analytics/overview  (admin only)
```

### 9.9 Components you export for others

`XPBar`, `LevelBadge`, `StreakFlame`, `BadgeCard`, `ChallengeCard`, `LeaderboardRow`, `AchievementToast`, `StatCard`. M2's dashboard imports these — keep the props stable after Week 2.

### 9.10 Week by week

- **W1:** all gamification tables, `events.py` + XP engine, `/api/me/stats`, and the `XPBar` / `StreakFlame` components.
- **W2:** badges + checker + celebration UI, achievements page, leaderboard.
- **W3:** daily challenges, all analytics charts, notifications, admin analytics.
- **W4:** **QA lead** — write and run the test matrix, file bugs with reproduction steps, verify all four slices, and help fix.

### 9.11 Definition of done

- [ ] XP is awarded exactly once per action (no double award on retry or refresh)
- [ ] Streaks survive a timezone change and a midnight boundary
- [ ] A badge earned mid-session shows the celebration without a page reload
- [ ] Charts render sensibly with 0 data, 1 day of data, and 8 weeks of data
- [ ] A handler raising an exception does not break the caller's request

---

## 10. Integration plan (Week 4, all four)

Integration is not really a Week 4 activity if you have followed the contracts — but reserve these sessions anyway:

| Day | Session | Owner |
| --- | --- | --- |
| Mon | Full happy-path walkthrough on staging; list every break | All |
| Tue | Fix P0s: auth edge cases, event double-fires, quiz payload mismatches | All |
| Wed | Performance: N+1 queries, add indexes, lazy-load the avatar bundle, image sizes | M3 + M1 |
| Thu | Final deploy, seed production, mobile pass, record a backup demo video | All |
| Fri | Documentation, report, presentation dry run | All |

### 10.1 Test matrix (M4 runs this)

1. Register → verify the user row exists → login → refresh → session persists
2. Browse → enroll → open a lesson → complete it → XP and streak update
3. Generate an AI quiz → take it → submit → score is correct → mastery moves → recommendations change
4. Chat with the tutor → the avatar speaks with lipsync → history persists after a reload
5. Earn a badge → celebration fires → it appears on the achievements page
6. Admin creates a course → it appears in the catalog for a student
7. A student opens an admin URL directly → 403
8. All of the above on a phone
9. LLM key removed → the app is still usable with a clear error, no white screen
10. A brand-new empty account → every page renders without crashing

### 10.2 Demo script (about 8 minutes)

Login → dashboard (streak, XP, recommendations with reasons) → open a recommended lesson → highlight text → "Ask the tutor" → **the avatar explains it aloud** → generate a quiz from that lesson → take it and deliberately miss one topic → return to the dashboard → **show that the recommendation changed because of that miss** → badge celebration → analytics page → admin panel.

That "the recommendation changed because I got it wrong" beat is the strongest twenty seconds in the demo. Rehearse it.

---

## 11. Risk register

| # | Risk | Owner | Mitigation |
| --- | --- | --- | --- |
| 1 | **SyncTalk needs a GPU and cannot deploy on a free tier** | M1 | Tier A browser avatar ships first and always works; SyncTalk is an upgrade behind the same API, never demo-critical |
| 2 | LLM rate limits or an exhausted key mid-demo | M1 | Two providers configured; response cache for repeated prompts; `MockLLMClient`; a pre-generated quiz in the seed data |
| 3 | Render free-tier cold start (~50s) | M3 | Keep-alive ping 10 minutes before the demo; loading states everywhere |
| 4 | Lessons shipped without `topic_tags` → recommender dead | M3 | Server-side validation plus an admin form requirement; seed data fully tagged |
| 5 | Merge conflicts in shared files | All | Shared files finalised on day 1; one line each; small PRs |
| 6 | A member falls behind | Lead | Friday demos surface it at the end of week 1, not week 3; cut scope down to the DoD checklist and drop stretch goals |
| 7 | Avatar tanks performance on weak laptops | M1 | 2D sprite fallback and a "disable avatar" toggle in preferences |
| 8 | Timezone/streak bugs found during the demo | M4 | Explicit timezone handling plus a case in the test matrix |
| 9 | Everyone builds their own button | M2 | UI kit shipped on the Monday of Week 1 |

---

## 12. Scope guard — what to cut if you fall behind

Cut in this order, from the top:

1. WebRTC / SyncTalk (Tier B avatar)
2. Voice input (speech to text)
3. Coins and any shop economy — keep XP and badges
4. Course-scoped leaderboards — keep global only
5. Notifications — fold them into toasts
6. Short-answer AI grading — keep MCQ / true-false / fill-blank

**Never cut:** auth, the course → lesson → quiz flow, tutor chat, the Tier A avatar, XP + streaks, and recommendations. That set *is* the project.

---

## 13. Quick reference

**Env vars — `backend/.env`**

```
DATABASE_URL=postgresql://...
FIREBASE_CREDENTIALS_JSON=./firebase-admin.json
LLM_PROVIDER=groq            # groq | gemini | openai | mock
LLM_API_KEY=...
LLM_MODEL=llama-3.3-70b-versatile
AVATAR_SERVICE_URL=          # empty means Tier A only
CORS_ORIGINS=http://localhost:5173,https://learnquest.vercel.app
```

**Env vars — `frontend/.env`**

```
VITE_API_URL=http://localhost:8000
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
```

**Commands**

```bash
uvicorn app.main:app --reload
```

```bash
alembic revision --autogenerate -m "describe the change"
```

```bash
alembic upgrade head
```

```bash
python -m app.seed.seed_data
```

```bash
npm run dev
```

**Who to ask**

| Topic | Ask |
| --- | --- |
| Auth, DB, deployment, admin | M3 |
| UI kit, lesson/quiz UI, dashboard layout | M2 |
| XP, badges, charts, events | M4 |
| Tutor, avatar, quiz generation, recommendations, integration | M1 (Lead) |
