# LearnQuest AI — Team Checklist

> **Update this file in the same PR as the work it describes.** Not afterwards, not at the end of the week.
>
> Mark a box `[x]` only when it is **done end to end**: migration applied + API returns real data +
> UI renders it + it still works after someone else runs `git pull`.
> Use `[~]` for in-progress and add your name + date next to anything you tick.
>
> Format: `- [x] Task description — @yourname, 2026-09-03`

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` cut from scope (say why)

---

## How to update

1. Find your section (Member 1–4) and the current week.
2. Change the box and append `— @yourname, YYYY-MM-DD`.
3. If you got blocked, add a line under **Blockers** at the bottom instead of silently stalling.
4. Commit it with your work: `git commit -m "feat(tutor): streaming chat + checklist"`.

---

## Week 0 — Shared setup (all four, together, day 1)

- [ ] GitHub repo created and everyone has push access — @
- [ ] Supabase project created, `DATABASE_URL` shared with the team — @
- [ ] Firebase project created, web config + service account shared — @
- [ ] LLM provider account + API key obtained — @
- [ ] Vercel account connected to the repo — @
- [ ] Render account connected to the repo — @
- [ ] Everyone can run the backend locally (`uvicorn app.main:app --reload`) — @
- [ ] Everyone can run the frontend locally (`npm run dev`) — @
- [ ] All four routers registered in `main.py` in ONE shared commit — @
- [ ] All four route groups added to `App.jsx` in ONE shared commit — @
- [ ] Topic-tag vocabulary agreed and written down (e.g. `python.loops`) — @
- [ ] Everyone has read plan.md §0–§4 — @

---

## Member 1 — AI Avatar Tutor & Intelligent Learning (Lead)

### Week 1 — foundations
- [ ] Decide the LLM provider and record it in `backend/.env.example` — @
- [ ] `services/llm_client.py`: `complete()` + `stream()` with retry, timeout, token logging — @
- [ ] `MockLLMClient` working under `LLM_PROVIDER=mock` (unblocks the whole team) — @
- [ ] `services/prompts.py`: tutor system prompt v1 — @
- [ ] `models/ai.py`: `conversations`, `messages`, `topic_mastery`, `recommendations` + migration — @
- [ ] `POST /api/tutor/conversations` and message CRUD working — @
- [ ] Non-streaming chat endpoint returns a real LLM answer — @
- [ ] Minimal chat UI at `/tutor` talking to the backend — @
- [ ] Tier A avatar spike: mouth moves in time with `speechSynthesis` — @

### Week 2 — streaming, memory, quizzes
- [ ] SSE streaming endpoint `GET /api/tutor/conversations/{id}/stream` — @
- [ ] Context builder: system + profile + lesson content + summary + last 8 turns — @
- [ ] Rolling summarisation kicks in past 16 messages — @
- [ ] `services/quiz_generator.py` with JSON-mode output + Pydantic validation — @
- [ ] Guardrails: answer-in-options check, duplicate-prompt check, 10-question cap, rate limit — @
- [ ] `POST /api/quizzes/generate` returns a quiz in M2's exact shape — @
- [ ] Adaptive difficulty derived from `topic_mastery` — @
- [ ] `emit("quiz.generated", ...)` wired — @
- [ ] TTS endpoint returning `{audio_url, visemes}` — @

### Week 3 — mastery, recommendations, avatar
- [ ] Lipsync accurate against real audio; idle blink + head sway — @
- [ ] Expression state machine (`neutral / thinking / explaining / encouraging`) — @
- [ ] `services/mastery.py` subscribed to `quiz.submitted` and updating `topic_mastery` — @
- [ ] `services/recommender.py` hybrid scoring with a human-readable `reason` on every item — @
- [ ] `GET /api/recommendations` + `/daily-plan` live — @
- [ ] `GET /api/analytics/mastery/me` exposed for M4's charts — @
- [ ] `RecommendationCard` exported and rendering in M2's dashboard — @
- [ ] Tier B / SyncTalk spike (optional — cut first if behind) — @
- [ ] Short-answer AI grading endpoint (optional) — @

### Week 4 — polish & integration
- [ ] Time to first token under 2s on the deployed backend — @
- [ ] Every AI call has a timeout, a retry, and a user-visible fallback message — @
- [ ] App fully usable with the LLM key removed (no white screen) — @
- [ ] Prompt tuning pass against real logged conversations — @
- [ ] Demo script rehearsed (plan.md §10.2) — @
- [ ] Integration support: unblocked M2, M3, M4 on their AI touchpoints — @

### Definition of done (plan.md §6.9)
- [ ] Tutor answers in the context of the current lesson and remembers earlier turns — @
- [ ] Avatar mouth visibly in sync; idle animation runs — @
- [ ] Generated quizzes render in M2's player unmodified — @
- [ ] Weak topics update after a quiz and visibly change recommendations — @
- [ ] `LLM_PROVIDER=mock` lets teammates run the app with no API key — @

---

## Member 2 — Learning Management

### Week 1 — UI kit + course browsing
- [ ] UI kit shipped Monday: `Button`, `Card`, `Input`, `Select`, `Modal`, `Spinner` — @
- [ ] UI kit part 2: `ProgressBar`, `Badge`, `Tabs`, `EmptyState`, `Toast` — @
- [ ] Tailwind theme tokens agreed and applied (plan.md §4.5) — @
- [ ] `/courses` catalog: grid, search, subject + difficulty filters — @
- [ ] `/courses/:slug` detail: lesson list, completion ticks, progress ring — @
- [ ] `POST /api/courses/{id}/enroll` + enrolled state in the UI — @
- [ ] `/lessons/:id` viewer rendering seeded markdown — @

### Week 2 — quizzes and progress
- [ ] `GET /api/quizzes/{id}` strips `correct_answer` and `explanation` — @
- [ ] Quiz player: one question per screen, timer, answers persist across refresh — @
- [ ] `POST /api/quizzes/attempts/{id}/submit` grades server-side — @
- [ ] `attempt_answers` rows written with `topic_tag` copied from the question — @
- [ ] `emit("quiz.submitted", ...)` fired on submit (M1 + M4 depend on it) — @
- [ ] Result screen with per-question explanations + retake — @
- [ ] `POST /api/lessons/{id}/progress` + 30s heartbeat time tracking — @
- [ ] Auto "mark complete" at 90% scroll + manual button — @
- [ ] `emit("lesson.completed", ...)` fired — @
- [ ] `/dashboard` v1 with progress cards — @

### Week 3 — history, revision, mobile
- [ ] `/history` timeline of lessons + attempts, filterable by course — @
- [ ] "Ask the tutor about this" from a lesson text selection → M1's `/api/tutor/explain` — @
- [ ] Revision flow driven by M1's recommendations — @
- [ ] Dashboard assembles M1 recommendations + M4 XP/streak/challenge widgets — @
- [ ] Responsive pass: everything usable at 375px — @
- [ ] `EmptyState` on every list — @

### Week 4 — polish
- [ ] Loading skeletons on every page — @
- [ ] Error states on every fetch — @
- [ ] Cross-browser check (Chrome, Firefox, Edge, mobile Safari) — @
- [ ] Bug fixes from M4's test matrix — @

### Definition of done (plan.md §7.5)
- [ ] A new student can enroll → complete a lesson → take a quiz → see it in history — @
- [ ] Progress percentages correct after refresh and on a second device — @
- [ ] Correct answers never appear in the pre-submit network response — @
- [ ] Every list has a loading skeleton and an empty state — @
- [ ] Usable at 375px width — @

---

## Member 3 — User & Administration

### Week 1 — THE critical sprint (everyone is blocked on this)
- [ ] **Day 1:** Supabase project + `DATABASE_URL` posted to the team — @
- [ ] **Day 1:** `database.py`, `config.py`, Alembic initialised — @
- [ ] **Day 1:** `users`, `courses`, `lessons`, `enrollments` migrated — @
- [ ] **Day 2:** Firebase project + web config shared — @
- [ ] **Day 2:** `AuthContext` with email/password + Google sign-in — @
- [ ] **Day 2:** `api/client.js` axios instance with the Bearer token interceptor — @
- [ ] **Day 3:** `firebase-admin` token verification in `deps.py` — @
- [ ] **Day 3:** `get_current_user` auto-creates the `users` row on first login — @
- [ ] **Day 3:** `require_admin` returning 403 for students — @
- [ ] **Day 4:** **Seed data: 3 courses × 5 lessons, real markdown, real `topic_tags`** — @
- [ ] **Day 5:** Course + lesson CRUD endpoints — @
- [ ] **Day 5:** Hello-world deploy proven on Render + Vercel — @
- [ ] Login / Register / Forgot-password pages — @
- [ ] `PrivateRoute` and `AdminRoute` wrappers — @

### Week 2 — admin panel & profile
- [ ] Admin shell with sidebar navigation — @
- [ ] Admin users table: search, filter by role, change role — @
- [ ] Admin courses table + course editor (markdown + preview) — @
- [ ] Drag-to-reorder lessons — @
- [ ] Tag picker with autocomplete over existing tags — @
- [ ] **Server-side rule: a lesson cannot be saved without a `topic_tag`** — @
- [ ] `/profile` page: name, avatar, preferences (tone, daily goal, difficulty, timezone) — @
- [ ] `emit("daily.login", ...)` on the first request of each day — @
- [ ] Staging deploy live and shared with the team — @

### Week 3 — security & analytics wiring
- [ ] Rate limiting on write endpoints — @
- [ ] Input validation pass on every admin endpoint — @
- [ ] No secrets committed anywhere in the repo history — @
- [ ] Least-privilege / RLS review on Supabase — @
- [ ] `POST /api/admin/upload` → Supabase Storage — @
- [ ] `GET /api/admin/overview` counts wired to M4's charts — @
- [ ] Token refresh on 401 with a single retry — @

### Week 4 — ship it
- [ ] Production deploy: backend on Render, frontend on Vercel — @
- [ ] CORS correct for the production domain — @
- [ ] Final seed: 5+ courses with full content — @
- [ ] Keep-alive ping configured for the Render cold start — @
- [ ] README + setup docs finalised — @
- [ ] FastAPI `/docs` curated (tags, summaries, descriptions) — @

### Definition of done (plan.md §8.7)
- [ ] Register → login → refresh → still logged in — @
- [ ] Student on an admin route gets 403 and sees no admin nav — @
- [ ] Admin-created courses appear immediately in M2's catalog — @
- [ ] Seed script rebuilds a full demo DB from empty in one command — @
- [ ] Deployed URLs work from another machine and from a phone — @

---

## Member 4 — Gamification & Analytics

### Week 1 — the event bus (the team is blocked on this too)
- [ ] **Day 1–2:** `services/events.py` with `on()` + `emit()` — @
- [ ] **Every handler wrapped in try/except — a failing handler must never 500 the caller** — @
- [ ] `models/gamification.py`: all 7 tables + migration — @
- [ ] `services/xp_engine.py` with the award table from plan.md §9.2 — @
- [ ] Every XP award writes an `xp_events` row — @
- [ ] Level curve `100 * n^1.5` implemented — @
- [ ] `GET /api/me/stats` returning xp, level, next_level_xp, coins, streak — @
- [ ] `XPBar` + `StreakFlame` components exported for M2's dashboard — @

### Week 2 — badges, streaks, leaderboard
- [ ] Streak logic using the **user's local date**, not server UTC — @
- [ ] `longest_streak` maintained — @
- [ ] ~15 badges seeded with JSONB `criteria` — @
- [ ] Data-driven badge checker running on every event — @
- [ ] Celebration modal + confetti on badge earned (Framer Motion) — @
- [ ] `/achievements` page: earned + locked with progress — @
- [ ] `GET /api/leaderboard` with `scope` + `period`, user's rank pinned — @
- [ ] `leaderboard_opt_out` preference respected — @

### Week 3 — challenges, charts, notifications
- [ ] Daily challenge template pool seeded — @
- [ ] 3 challenges generated per day + progress via event handlers — @
- [ ] `POST /api/challenges/{id}/claim` — @
- [ ] "Practice a weak topic" challenge calling M1's `/api/recommendations` — @
- [ ] `/stats`: weekly activity, XP over time, quiz accuracy trend — @
- [ ] Topic mastery chart fed by M1's `/api/analytics/mastery/me` — @
- [ ] Time-of-day pattern + course completion donuts — @
- [ ] Notifications list + mark-as-read — @
- [ ] Admin analytics: DAU/WAU, signups, course popularity, quiz difficulty — @

### Week 4 — QA lead
- [ ] Test matrix written out (plan.md §10.1) — @
- [ ] All 10 matrix cases run and results recorded — @
- [ ] Bugs filed with reproduction steps — @
- [ ] Charts verified with 0 data, 1 day, and 8 weeks of data — @
- [ ] Re-test after fixes — @

### Definition of done (plan.md §9.11)
- [ ] XP awarded exactly once per action (no double award on retry/refresh) — @
- [ ] Streaks survive a timezone change and a midnight boundary — @
- [ ] A badge earned mid-session celebrates without a page reload — @
- [ ] Charts render sensibly at 0 / 1 day / 8 weeks of data — @
- [ ] A raising handler does not break the caller's request — @

---

## Weekly checkpoints (plan.md §5)

- [ ] **End W1:** login works · a real course renders from the DB · the tutor answers one question — @
- [ ] **End W2:** enroll → read a lesson → take an AI-generated quiz → XP goes up — @
- [ ] **End W3:** avatar speaks with lipsync · dashboard shows recommendations, streaks, charts — @
- [ ] **End W4:** deployed, seeded, demoed — @

---

## Integration week (plan.md §10)

- [ ] **Mon:** full happy-path walkthrough on staging, every break listed — @
- [ ] **Tue:** P0 fixes (auth edge cases, event double-fires, quiz payload mismatches) — @
- [ ] **Wed:** performance (N+1 queries, indexes, lazy-load avatar bundle, image sizes) — @
- [ ] **Thu:** final deploy, production seed, mobile pass, backup demo video recorded — @
- [ ] **Fri:** documentation, report, presentation dry run — @

---

## Blockers

> Add a line here the moment you are stuck for more than half a day. Remove it when resolved.

| Date | Who | Blocked on | Needs | Status |
| --- | --- | --- | --- | --- |
| | | | | |

---

## Scope cuts

> Anything moved to `[-]` above gets a line here so it is a decision, not a gap.
> Cut order is in plan.md §12.

| Date | Item | Reason | Decided by |
| --- | --- | --- | --- |
| | | | |
