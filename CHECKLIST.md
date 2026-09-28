# LearnQuest AI — 4-Week Delivery Checklist

> **How this works:** one member works at a time, in slot order. When your slot is
> done you **push to `main` and message the group**. The next person pulls and starts.
> Nobody works on the same files at the same time, so there are no merge conflicts.
>
> Tick `[x]` only when it works end to end: API returns real data → UI renders it →
> still works after `git pull`. **A route that exists is not a ticked box** — the box
> is for the feature, wired, and visible to a user.
>
> Format: `- [x] Task — @yourname, 2026-09-22`

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` cut

---

## The pitch

> **A tutor that models your mind, not your score — with a real human face.**

A wrong answer doesn't just score 0. The app names **the false belief** behind it,
then the photoreal SyncTalk tutor is seeded with **your** misconception and you have
to teach it out of the mistake. Its score on the retry is your grade.
(*The protégé effect* — real education research.)

---

## ⚠️ Read this after you pull — 2026-09-29

Migration head is now **`0010`** (review items + practice problems), and the
practice problems need seeding once:

```bash
cd backend && .venv/Scripts/python.exe -m alembic upgrade head
cd backend && .venv/Scripts/python.exe -m app.seed.practice_problems
```

Without the seed `/practice` shows an empty list. The seed is idempotent - run
it again whenever you like.

**Everything except the avatar is now wired end to end.** Practice and Review
were running on fake frontend fallbacks (any answer over 15 characters
"passed"); those fallbacks are gone and both talk to real backends. Leaderboard
and Profile are real pages, and the Dashboard shows the next roadmap step,
today's plan and ranked recommendations (G3 closed).

## Earlier pull notes — 2026-09-28

Ten commits landed since `0d788ba`. Two of them will break your local setup if
you skip these.

### Everyone, before you run anything

```bash
cd backend && .venv/Scripts/python.exe -m alembic upgrade head
```

You are almost certainly on `0006`. Head is now **`0009`**. Without this the
tutor page, Teach-Back and anything generative fail with *column does not
exist* — the models reference columns your database has not got yet.

Then in `backend/.env`:

```
LLM_MODEL=gemini-3.6-flash
```

The old value is out of daily quota. Gemini's free tier is a **per-day,
per-model** request cap, so if `gemini-3.6-flash` is also dry, try another model
name — each has its own bucket. Every AI feature fails with a 429 otherwise, and
that includes the tutor and the misconception engine.

Restart your dev server too: the Tailwind config changed and a long-running Vite
process holds a stale copy.

### The UI is dark-first now, and colour rules are enforced

Three rules, expanded in [docs/DESIGN_GUIDELINES.md](docs/DESIGN_GUIDELINES.md):

1. **Never write a raw colour.** No `bg-white`, no `text-slate-500`, no hex.
   Only tokens: `bg-surface`, `text-muted`, `border-line`. 429 hardcoded classes
   across 16 files were replaced in one pass; please do not start the drift
   again.
2. **Never write a `dark:` variant.** The theme lives in CSS variables on
   `:root`, so `.dark` is never applied and a `dark:` utility is dead code that
   looks meaningful.
3. **Never hand-roll a control.** Use `Button`, `Input`, `Select`, `Badge`,
   `Card` from `components/ui`. Body text is 15px and buttons are 40px.

### Files of yours I edited

Ownership was set aside deliberately for this stretch (the lead's call), so
check these before you branch off them:

| File | Owner | What changed |
|---|---|---|
| `routers/quizzes.py` | M2 | The two `/generate` stubs are now real |
| `routers/courses.py` | M2 | New `POST /generate` returning a job |
| `routers/progress.py` | M2 | N+1 removed — prefetch instead of a query per course |
| `app/main.py` | shared | One line registering the jobs router, plus a startup reaper |
| `app/database.py` | M3 | `pool_pre_ping` off by default (it cost 105ms per request) |
| `services/events.py` | M4 | `course.generated` added to `EventType` |
| `pages/`, `components/` | all | Colour classes moved onto tokens; no logic touched |

### What is live that was not before

- **The misconception engine fires.** A wrong quiz answer produces a named false
  belief. Verified against the live model.
- **Teach-Back.** Nova is seeded with that belief, argues from it, and re-takes
  the question. Her score is the student's grade.
- **The avatar speaks** (SyncTalk + Gemini TTS) — needs the GPU service running.
- **Generated quizzes and courses**, aimed at what each student gets wrong.

---

## Where we actually are — audited 2026-09-29

Every `[x]` below was re-checked against the code, not trusted. Counted per
slot owner (M4's earlier total of 28 was a miscount; it owns 23 items).

| Member | Done | In progress | Open | Total |
|---|---|---|---|---|
| **M1** (AI) | 36 | 0 | 8 | 44 |
| **M2** (Learning) | 29 | 0 | 6 | 35 |
| **M3** (Users) | 15 | 1 | 6 | 22 |
| **M4** (Game) | 23 | 0 | 0 | 23 |
| **Total** | **103** | **1** | **20** | **124** |

M1's 8 open items: 5 are Week 4 hardening (Slot 13, two of them avatar/TTS
latency), and 3 are standing ⚠️ risks on generated content — no reviewer,
the daily quota, and 503s from the model — kept open so nobody forgets them.

Plus 4 shared dry-run items in Days 26-28.

**M1's backend work is done.** The misconception engine fires,
Teach-Back runs end to end, the avatar speaks, and quizzes and courses are
generated per student. Slot 9 (free-response grading + the review queue),
recommendations and the daily plan landed 2026-09-29.

**The bottleneck is now the frontend.** Almost everything M1 shipped has no UI:
generated quizzes, generated courses, the misconception map. Slots 9D (M2) and
9E (M4) are the highest-value work left in the project, because they are what
makes the novel part visible to anyone who is not reading a database.

Every gap is closed — G1 through G6. Google sign-in (G2) was verified working
on 2026-09-29. See [Open gaps](#open-gaps).

**There is one avatar.** Tier A — the SVG avatar and its Web Speech voice — was
removed on 2026-09-22. Without a GPU service the tutor page shows an "avatar
offline" panel naming what is missing; chat and Teach-Back are unaffected, which
is what M2/M3/M4 will see on their own machines.

---

## 👉 Start here — one task each

Pick the thing at the top of your list. Everything below it is in the numbered
slots further down.

### 🟢 M2 (Learning) — **Slot 9D**

Your API clients are ready: `generateQuiz` / `generateAdaptiveQuiz` in
`api/quizzes.js`, `generateCourse` in `api/courses.js`, and
`hooks/useGenerationJob.js` does the job polling for you — you should not need
to write a `setTimeout`.

The backend for generated content is done and returns your existing shapes, so
`QuizPlayer` needs **zero changes**.

- `POST /api/quizzes/generate` `{lesson_id}` → a ready-to-take quiz. Take `id`,
  route to `/quiz/{id}`. ~8s, so show a spinner.
- `POST /api/quizzes/generate/adaptive` → same, but aimed at this student's three
  weakest topics and at any belief the app has recorded about them.
- `POST /api/courses/generate` `{goal}` → **202 with a job id, not a course.**
  Poll `GET /api/jobs/{job_id}` and show `progress`; on `succeeded` its `result`
  has `{course_id, slug, title, lessons, topics}` and the student is enrolled.
- Handle **429** as "you have used today's generations" —
  `GET /api/jobs/quota` returns `{used, limit, remaining}` so a button can say
  so before it is pressed.

### 🟣 M4 (Gamification) — **Slot 9E**

Your API client is ready: `api/mastery.js` has `myMisconceptions()` and
`myMastery()`, and `analytics.js` no longer points at your own stub.

`Stats.jsx` is still 11 lines, and it is now the most valuable screen in the app:
the misconception map is the thing that shows what this product does, and
generated quizzes finally make mastery move.

- `GET /api/mastery/me/misconceptions` → active / fading / cleared, with the text
  of each belief.
- `GET /api/mastery/me` → mastery per topic.
- ⚠️ Use M1's `/api/mastery/*`. The `/mastery/me` in your `analytics.py` is still
  a stub returning `{"items": []}` and will look like it works.
- ⚠️ Your three XP tests are order-dependent — see the note under Repo state.
  They pass now for the wrong reason.

### 🟠 M3 (Users) — **Slot 3 leftovers, then Slot 15**

G5 is done — anonymous access now fails closed.

- ~~**G2:** Google sign-in fails at the token exchange.~~ Verified working
  2026-09-29. Still to confirm: redirect URLs for 5173 **and** 5174, and that a
  fresh Google sign-up writes a `public.users` row.
- ~~`Profile.jsx` is still 11 lines.~~ Built 2026-09-29: stats, name, daily
  goal, leaderboard opt-out.

### 🔵 M1 (AI) — **Slot 13**

Slot 9 is done. Next is the Week 4 hardening pass: timeouts, rate limits and
latency numbers. The avatar is deliberately excluded until then.

---

## File ownership — never edit someone else's files

| Member | Backend | Frontend |
|---|---|---|
| **M1** (AI) | `routers/{tutor,avatar,roadmap,mastery}.py`, `services/{llm_client,prompts,mastery,roadmap_planner}.py`, `models/{ai,roadmap}.py` | `pages/{Tutor,Roadmap}/`, `components/avatar/`, `api/{tutor,avatar,roadmap}.js` |
| **M2** (Learning) | `routers/{courses,lessons,progress,quizzes}.py`, `models/{course,progress,quiz}.py` | `pages/{Courses,Lesson,Quiz,Practice}/`, `components/ui/`, `api/{courses,lessons,quizzes}.js` |
| **M3** (Users) | `routers/{auth,users,admin}.py`, `models/user.py`, `deps.py` | `pages/{Auth,Profile,Admin}/`, `components/layout/`, `context/AuthContext.jsx` |
| **M4** (Game) | `routers/{gamification,analytics}.py`, `services/{xp_engine,events}.py`, `models/gamification.py` | `pages/{Dashboard,Achievements,Leaderboard,Stats,History}/`, `api/{gamification,analytics}.js` |

**Shared — announce before touching:** `app/main.py` · `app/models/__init__.py` ·
`frontend/src/App.jsx` · `tailwind.config.js` · `index.css` · `api/client.js`

> ⚠️ `Dashboard.jsx` still carries an `OWNER: Member 2` header comment, but the table
> above — and the commit history — puts it with **M4**. Fix the comment, not the
> table. A stale owner line is how two people end up editing one file.

**Design:** all frontend work follows [docs/DESIGN_GUIDELINES.md](docs/DESIGN_GUIDELINES.md).

---

# 🗓️ WEEK 1 — make the core loop real

## 🔵 Slot 1 · Member 1 · Days 1–2

**AI misconception engine — the novel core.**

- [x] `services/mastery.py::capture_misconception()` — LLM names the **false belief**
      behind a wrong answer in plain English — @sahilaf, 2026-09-21
- [x] Reject invented misconceptions: 6 abstention guards, store `None` when unsure — @sahilaf, 2026-09-21
- [x] `@register_handler("quiz.submitted")` calling `handle_quiz_submitted()` — @sahilaf, 2026-09-21
- [x] `GET /api/mastery/me/misconceptions` — status active / fading / cleared — @sahilaf, 2026-09-21
- [x] Decay: N correct answers moves active → fading → cleared — @sahilaf, 2026-09-21

> ✅ **Live since 2026-09-22.** G1 is closed — the engine reads `attempt_answers`
> back from the attempt, so it fires on the event M2 already emits.

**✅ Hand off when:** you can POST a wrong answer and see a misconception row written.
**→ Push, then tell M2.**

---

## 🟢 Slot 2 · Member 2 · Days 2–4

**⛔ FIRST: unblock the database.**

- [x] Uncomment `from app.models import progress, quiz` in `models/__init__.py` — @skredwanulislam, 2026-09-21
- [x] Migration `0006_m2_learning_management` with
      `down_revision = "0005_m1_misconception_tracking"` so it chains instead of
      branching — @skredwanulislam, 2026-09-21
- [x] Tables created: `lesson_progress`, `quizzes`, **`questions`**, `quiz_attempts`,
      `attempt_answers` — note the name is `questions`, not `quiz_questions` — @skredwanulislam, 2026-09-21

**Then make quizzes work** — nothing in the app has a game loop without this.

- [x] `GET /api/quizzes/{id}` — questions **with `correct_answer` stripped**
      (plan.md §7.3; answers are exposed only post-submit on the review route) — @skredwanulislam, 2026-09-21
- [x] `POST /api/quizzes/{id}/attempts` — create attempt — @skredwanulislam, 2026-09-21
- [x] `POST /api/quizzes/attempts/{id}/submit` — score + persist — @skredwanulislam, 2026-09-21
- [x] `emit(db, user_id, "quiz.submitted", payload)` on submit — @skredwanulislam, 2026-09-21
      > The payload still carries only the counts, but M1 no longer needs the
      > `answers` list — it loads the rows itself. Adding `answers` would save a
      > query and nothing more, so this is no longer blocking anything.
- [x] `QuizPlayer.jsx` — one question at a time, progress — @skredwanulislam, 2026-09-21
- [x] `QuizResult.jsx` — score + per-question review — @skredwanulislam, 2026-09-21
- [x] `GET /api/me/progress` — real *(M4 needs this in Slot 4)* — @skredwanulislam, 2026-09-21

**✅ Hand off when:** you can take a quiz, get a score, and M1's misconception
appears for a wrong answer.
**→ Push, then tell M3.**

---

## 🟠 Slot 3 · Member 3 · Days 4–5

**Auth — blocks every real demo.**

- [x] Enable **Google OAuth** in Supabase — verified via `/auth/v1/settings` (`google: true`) — done, 2026-09-22
- [x] `GET/PATCH /api/users/me` — real in `users.py` — done, 2026-09-22
- [x] Fix the Google token exchange — **[G2] closed**, sign-in verified working — @sahilaf, 2026-09-29
- [ ] Add Supabase redirect URLs for **both 5173 and 5174** (Vite falls back) — @, 2026-__-__
- [ ] Verify sign-up creates a `public.users` row — @, 2026-__-__
- [x] `Profile.jsx` — stats, name, email (read-only), daily goal, leaderboard opt-out; `/api/me` now returns real stats — @sahilaf, 2026-09-29

**✅ Hand off when:** a stranger can sign up with Google and see their profile.
**→ Push, then tell M4.**

---

## 🟣 Slot 4 · Member 4 · Day 5

**Dashboard — the first screen after login.**

- [x] XP + level + progress bar from `GET /api/me/stats` (real `UserStats` query) — @rhossain222308-del, 2026-09-21
- [x] Streak counter — @rhossain222308-del, 2026-09-21
- [x] "Continue learning" — uses M2's `/api/me/progress` — @rhossain222308-del, 2026-09-21
- [x] Header streak/XP in `AppLayout.jsx` wired to `myStats()` — @rhossain222308-del, 2026-09-21
- [x] "Next quest" from `GET /api/roadmap/me` — `ForYouPanel` on the Dashboard, closes [G3] — @sahilaf, 2026-09-29

**✅ Week 1 is done when:** sign up → dashboard shows real numbers → take a quiz →
get one wrong → the app names your misconception.

---

# 🗓️ WEEK 2 — the novel feature + fill the gaps

## 🔵 Slot 5 · Member 1 · Days 6–8

**SyncTalk photoreal tutor + Teach-Back — the demo moment.**

- [x] **[G1] closed** — `handle_quiz_submitted()` now loads `attempt_answers` by
      `attempt_id` when the payload omits `answers`, so the engine fires on the
      event M2 already emits. M2's router was not touched — @sahilaf, 2026-09-22
- [x] **[G4] closed** — `useSyncTalkStream.js` decodes the 16-byte framed binary
      protocol over WebSocket into `<canvas>`, replacing the `<img src>` — @sahilaf, 2026-09-22
- [x] PCM segments drive the clock: each segment's audio is scheduled on the
      `AudioContext` and the render loop draws the frame belonging at
      `ctx.currentTime`, so the mouth cannot drift from the voice — @sahilaf, 2026-09-22
- [x] Falls back to the SVG avatar when `AVATAR_SERVICE_URL` is unset, the health
      probe fails, or the socket drops mid-session — @sahilaf, 2026-09-22
- [x] **Teach-Back:** Nova is seeded with the student's own misconception and the
      question they actually got wrong (`services/teachback.py`) — @sahilaf, 2026-09-22
- [x] Nova argues from the false belief and pushes back on vague answers; a
      non-explanation is rejected before an LLM call is spent — @sahilaf, 2026-09-22
- [x] **Nova re-takes the question — her score is the student's grade.** Graded
      deterministically first, LLM judge only when that is inconclusive, and it
      abstains to a fail rather than a pass — @sahilaf, 2026-09-22
- [x] On a pass the misconception moves `active → fading` and XP is awarded via
      `emit("teachback.completed")` → M4's `award_xp` — @sahilaf, 2026-09-22
- [x] **[G6] closed** — Gemini TTS (`services/tts.py`) returns 24 kHz PCM, the exact
      rate SyncTalk works in, and the browser forwards it to the audio socket as
      WAV chunks. The avatar speaks — @sahilaf, 2026-09-22
- [x] **Tier A removed** — the SVG avatar, its Web Speech voice and the whole
      viseme pipeline are deleted. One avatar, one voice; when it cannot run the
      UI says why instead of quietly substituting a cartoon — @sahilaf, 2026-09-22

**✅ Hand off when:** the full loop runs — wrong answer → misconception → teach
Nova → Nova passes. *(Verified 2026-09-22: 15 tests in
`backend/tests/test_teachback.py`, including an end-to-end HTTP round trip.)*
**→ Push, then tell M2.**

---

## 🟢 Slot 6 · Member 2 · Days 8–10

**Courses in HackerRank shape.**

- [x] `GET /api/me/history` — real *(M4 needs it next)* — @skredwanulislam, 2026-09-21
- [ ] Restructure catalogue as **Tracks → Skills → Problems** — @, 2026-__-__
- [ ] Difficulty chips (Easy/Medium/Hard) via `Badge tone=` — @, 2026-__-__
- [ ] Solve % + attempt count per skill — @, 2026-__-__
- [ ] Use `.table-dense` rows, not big cards — @, 2026-__-__
- [ ] Filters: subject, difficulty, status, search — @, 2026-__-__
- [ ] **Readable URLs.** `/lessons/:lessonId`, `/quiz/:quizId` and
      `/quiz/attempts/:attemptId` still put a raw UUID in the address bar
      (`/lessons/2ab0ff8f-0a18-47be-a60d-25e6b0031d74`). Courses already do this
      right with a slug. M1 fixed the tutor on 2026-09-22 by adding a per-user
      `number` to `conversations` and accepting either form in the route — same
      pattern works here, or give `lessons` a slug like `courses` has — @, 2026-__-__

**✅ Hand off when:** the courses page looks like a practice platform, not a shop.
**→ Push, then tell M3.**

---

## 🟠 Slot 7 · Member 3 · Days 10–11

**Admin panel.**

- [x] `AdminOverview.jsx` — user/course/activity counts — @member3, 2026-09-21
- [x] `AdminCourses.jsx` — create / edit / publish a course — @member3, 2026-09-21
- [x] `AdminUsers.jsx` — list + role/status edit — @member3, 2026-09-21
- [x] `GET /api/admin/overview` — real numbers (14 admin routes live) — @member3, 2026-09-21
- [~] Make `DEV_ALLOW_ANONYMOUS` fail closed — **see [G5]** — @member3, 2026-09-21

**→ Push, then tell M4.**

---

## 🟣 Slot 8 · Member 4 · Days 11–12

**Fill every remaining dead page.**

- [x] Seed badges + `GET /api/me/badges` → `Achievements.jsx` — @rhossain222308-del, 2026-09-21
- [x] `History.jsx` from M2's `/api/me/history` — @rhossain222308-del, 2026-09-21
- [x] Add **History** to `NAV` in `AppLayout.jsx` — verified in `NAV`, 2026-09-29
- [x] `Stats.jsx` + **misconception map** — built on M1's `/api/mastery/*` (see
      Slot 9E) — @oni, 2026-09-28
- [x] `GET /api/leaderboard` — weekly (from `xp_events`) / all-time, one bulk query, honours opt-out, caller's rank always pinned → `Leaderboard.jsx`, in `NAV` — @sahilaf, 2026-09-29
- [x] Add each page to `NAV` as it stops being a placeholder — every built page is
      in `NAV` (Review and Leaderboard added) — @sahilaf, 2026-09-29

**✅ Hand off when:** no nav link is a dead end, and no built page is unreachable.

---

# 🗓️ WEEK 3 — the learning-science layer

> Weeks 1–2 make the loop work. Week 3 is what makes it a *learning* product
> rather than a quiz app, and it restores the Tier 1/Tier 2 items from plan.md
> §0.1 that a 2-week scope had to drop.

## 🔵 Slot 9A · Member 1 · Adaptive content — foundations

**Approved 2026-09-27.** The student should get quizzes, and later courses, that
are generated for them rather than seeded. Steps 3-6 of that flow already work
(misconception capture, the avatar, Teach-Back); what is missing is the
generation that feeds them.

Two things have to exist before any generation is safe:

- [x] **`topics` table** (migration `0009`), seeded with the 12 tags that were
      living in `seed_data.py`. Verified every tag already in `questions` and
      `topic_mastery` is covered, so nothing existing was orphaned — @sahilaf, 2026-09-27
- [x] `services/topics.py::resolve()` drops any tag the vocabulary does not
      know, the same way `roadmap_planner.validate_steps()` drops a step naming
      a lesson that does not exist — @sahilaf, 2026-09-27
- [x] **`generation_jobs` + `GET /api/jobs/{id}`**, plus `reap_stale_jobs()` at
      startup so a restart mid-generation cannot leave a row polled forever.
      `main.py` gained one line to register the router — @sahilaf, 2026-09-27
- [x] Per-user daily cap (`DAILY_JOBS_PER_USER = 20`) returning **429** with a
      sentence a student can read. Jobs that failed on our side do not consume
      the allowance. `GET /api/jobs/quota` so the UI can say so *before* the
      button is pressed — @sahilaf, 2026-09-27

**✅ Hand off when:** a slow generation returns a job id in under a second and
its result appears when the job finishes.

---

## 🔵 Slot 9B · Member 1 · Adaptive quizzes

**A quiz built for this student, fresh every attempt** (decided 2026-09-27:
questions never repeat, which is better practice and costs 1-2 calls, not 13).

- [x] `services/quiz_generator.py` implemented to the stub's own spec. The
      validation is the part that matters: an mcq whose `correct_answer` is not
      among its `options` can never be answered correctly, and a duplicate
      prompt lets one misunderstanding cost two marks — both are dropped rather
      than shipped — @sahilaf, 2026-09-27
- [x] `POST /api/quizzes/generate` wired. Returns M2's quiz shape with answers
      stripped, so it can be taken immediately — @sahilaf, 2026-09-27
- [x] `POST /api/quizzes/generate/adaptive` — three weakest topics from
      `topic_mastery`, difficulty from the score, and where a live misconception
      exists the questions are aimed at it. Verified on the real stack: a
      learner whose recorded belief was *"foreign keys require identical column
      names"* got a question putting `user_code` against `id` with exactly that
      belief as the distractor — @sahilaf, 2026-09-27
- [x] Generated quizzes persist as ordinary rows marked
      `source="ai_generated"` and emit `quiz.generated`. Nothing downstream —
      attempts, grading, the misconception engine — knows or cares where the
      questions came from, which is the point — @sahilaf, 2026-09-27
- [x] The backend half of the loop is done. The frontend half is M2's, in
      Slot 9D below — @sahilaf, 2026-09-27

**✅ Hand off when:** two students with different mastery get visibly different
quizzes on the same topic, and getting one wrong still produces a misconception.

---

## 🔵 Slot 9C · Member 1 · Generated courses *(after 9A and 9B)*

- [x] `services/course_planner.py`: goal → outline → lessons, tags drawn only
      from the vocabulary. No migration needed — `Course` already had `source`,
      `is_private` and `created_by` — @sahilaf, 2026-09-27
- [x] `POST /api/courses/generate` returns **202** with a job id; the work runs
      behind it on its own session and reports coarse progress. Measured on the
      real stack: **24.5s for 3 lessons**, which is why it is not synchronous — @sahilaf, 2026-09-27
- [x] Auto-published, `source="ai_generated"`, private to the student, and they
      are enrolled automatically — without the enrolment the course appears
      nowhere they would think to look — @sahilaf, 2026-09-27
- [ ] ⚠️ **Nobody checks this content.** Still true, and now live: the AI writes
      the lesson, writes a quiz from it, grades it, and names the misconception
      behind a wrong answer — four steps, no human. A confidently wrong lesson
      produces a confident diagnosis of a belief the learner never held.
      Private + `ai_generated` is containment, not a fix. Revisit before anyone
      outside the team uses this — @, 2026-__-__
- [ ] ⚠️ **The quota ceiling is real, not theoretical.** The first live
      generation ran out of daily quota partway through: lesson 1 came back at
      3069 chars, lessons 2 and 3 fell back to their outline summaries at ~250.
      The fallback worked as designed — one failed call costs a thin lesson, not
      the whole course — but a learner still got two stubs. Caching lessons by
      `(topic, difficulty)` is the fix; it was deferred on 2026-09-27 in favour
      of fresh-every-time — @, 2026-__-__
- [x] ⚠️ `gemini-3.6-flash` returns **503 Service Unavailable** often enough to
      fail a whole course through three retries. **Fixed:** `LLM_FALLBACK_MODELS`
      — each attempt moves to the next model instead of re-asking the overloaded
      one (a real upload failed on three 503s in 12s while other models answered
      in 2s). Also covers per-model 429 quota. Streaming falls back only before
      the first token. An empty 200 counts as a failure, not as "no study
      material". Failed jobs now say "the AI service is busy" — @sahilaf, 2026-09-29

> **Everyone:** add this to `backend/.env` (it is in `.env.example`):
> `LLM_FALLBACK_MODELS=gemini-3.7-flash,gemini-2.5-flash,gemini-flash-latest`

- [x] **Second provider: OpenRouter** (`inclusionai/ling-3.0-flash-vl`), tried
      when every Gemini model fails — an outage or daily quota at Gemini no
      longer takes down every AI feature at once. Reasoning is switched off
      (it ate 187 of 284 tokens and truncated JSON). Measured with Gemini
      forced down: valid quiz JSON 3/3 at ~3.2s, streaming in 1.3s. **Paid but
      tiny** (~$0.00005 per lesson) — the account needs a few dollars of credit.
      Set `OPENROUTER_API_KEY` in `backend/.env` (the lead has one; never commit
      it). Gemma 4 31B was tested and rejected: 40–60s per reply, ~2 in 5
      failed, no streaming — @sahilaf, 2026-09-29

---

## 🟢 Slot 9D · Member 2 · Generated quizzes in the UI

**The backend is done and returns your existing quiz shape**, so `QuizPlayer`
needs no changes at all — take the `id` from the response and route to
`/quiz/{id}`.

- [x] **"Practice this lesson"** on the lesson page →
      `POST /api/quizzes/generate` with `{lesson_id}`. Takes ~8s, so show a
      loading state; it is inside the 30s client timeout — @skredwanulislam, 2026-09-28
- [x] **"Practice my weak spots"** on the dashboard →
      `POST /api/quizzes/generate/adaptive`. No body needed. Picks the three
      topics this student is weakest at — @skredwanulislam, 2026-09-28
- [x] Handle **429** as "you have used today's generations", not as a crash.
      `GET /api/jobs/quota` returns `{used, limit, remaining}` so the button can
      say so before it is pressed — @skredwanulislam, 2026-09-28
- [x] After a wrong answer, a **"Learn this"** link from `QuizResult` to the
      lesson, then **"Teach Nova"** to `/tutor`. Both ends already exist — this
      is wiring, not new features — @skredwanulislam, 2026-09-28

- [x] **"Build me a course"** — a goal box on the dashboard →
      `POST /api/courses/generate` `{goal, n_lessons}`. It returns **202** with
      `{job_id, poll}`, NOT a course: poll `GET /api/jobs/{job_id}` every couple
      of seconds and show `progress`. On `succeeded`, `result` carries
      `{course_id, slug, title, lessons, topics}` and the student is already
      enrolled — route to `/courses/{slug}` — @skredwanulislam, 2026-09-28
- [x] Show generated courses as such. `source="ai_generated"` is on the course
      row; a student should be able to tell written-for-me content from
      reviewed content at a glance — @skredwanulislam, 2026-09-28

**✅ Hand off when:** a student can generate a quiz aimed at their own weak
topics and take it without leaving the app.
**→ Push, then tell M4.**

---

## 🟣 Slot 9E · Member 4 · The misconception map has real data now

Generated quizzes target the belief the app recorded, so mastery actually moves
instead of sitting still. That makes `Stats.jsx` worth building properly.

- [x] Misconception map from `GET /api/mastery/me/misconceptions` — active →
      fading → cleared, with the text of each belief. This is the screen that
      shows what the product actually does — @oni, 2026-09-28
- [x] Mastery per topic from `GET /api/mastery/me` — @oni, 2026-09-28
- [x] ⚠️ Use M1's `/api/mastery/*`, not `analytics.py`'s `/mastery/me`, which is
      still a stub returning `{"items": []}` — @oni, 2026-09-28

---

## 🔵 Slot 9 · Member 1 · Days 13–15

**Free-response grading + spaced repetition.**

Free text is **Tier 1 in plan.md** and matters more than it looks: the misconception
engine currently only sees multiple-choice answers, the weakest possible signal for
inferring a false belief. Typed answers are where it actually works.

- [x] `POST /api/quizzes/attempts/{id}/grade-open` — `services/open_grader.py`;
      correct / partial / incorrect + written feedback — @sahilaf, 2026-09-29
- [x] Feed the typed answer into `capture_misconception()` (much richer input) — @sahilaf, 2026-09-29
- [x] Guard: never mark correct on the model's word alone — empty is wrong, a
      containment match is right without the model, the model's verdict only
      counts when confident (≥0.6) and consistent with its score; otherwise
      `needs_review` and the schedule is left alone — @sahilaf, 2026-09-29
- [x] **Review queue generation** on `review_items` — every topic a submitted quiz
      touches is enrolled (`quiz.submitted` handler in `services/scheduler.py`);
      migration `0010` adds `question_id` — @sahilaf, 2026-09-29
- [x] `GET /api/review/today` — what is due now, bank questions first, at most two
      generated per load — @sahilaf, 2026-09-29
- [x] `POST /api/review/{id}/answer` — grade, reschedule (right ×2.5 up to 60d,
      wrong → 2d), update mastery — @sahilaf, 2026-09-29
- [x] **Interleave**: a review session mixes topics rather than blocking one topic — @sahilaf, 2026-09-29
- [x] **Recommendations** — `GET /api/recommendations` ranks lessons by weakness,
      prerequisites, recency and popularity, each with its reason; dismiss;
      `GET /api/recommendations/daily-plan` fills the daily goal, review first — @sahilaf, 2026-09-29
- [x] **Practice runner** — each submission runs in a fresh in-memory SQLite
      database that allows SELECT only, with a 2s timeout; hidden cases never
      leave the server. 6 seeded problems, 16 cases — @sahilaf, 2026-09-29

**✅ Hand off when:** a wrong typed answer schedules a review, and it comes back
on the right day mixed with other topics.
**→ Push, then tell M2.**

---

## 🟢 Slot 10 · Member 2 · Days 15–17

**Practice problems + the review screen.**

- [x] `/practice` route + restore the nav entry (commented out at `AppLayout.jsx:36`) — @skredwanulislam, 2026-09-28
- [x] Problem page: statement, input/output examples, test cases — @skredwanulislam, 2026-09-28
- [x] Submit → pass/fail per test case, stored as an attempt — @skredwanulislam, 2026-09-28
- [x] "Skill verified" once N problems in a skill pass — @skredwanulislam, 2026-09-28
- [x] **Review screen** driven by M1's `/api/review/today` — one card at a time — @skredwanulislam, 2026-09-28
- [x] Free-response question type in `QuizPlayer` (textarea + M1's grader) — @skredwanulislam, 2026-09-28
- [x] Mobile pass over Courses / Lesson / Quiz — @skredwanulislam, 2026-09-28

**→ Push, then tell M3.**

---

## 🟠 Slot 11 · Member 3 · Days 17–19

**Upload your own notes → a course.**

The differentiator plan.md describes: an uploaded PDF becomes a course using the
same tables and the same pipeline, so nothing downstream knows the difference.
`POST /api/admin/upload` and `POST /api/uploads` already exist to build on.

- [x] `POST /api/courses/upload` — accept a PDF/markdown file — @member3, 2026-09-28
- [x] Extract text, split into lesson-sized sections — @member3, 2026-09-28
- [x] Create `Course` + `Lesson` rows marked `source="uploaded"`, `is_private=true` — @member3, 2026-09-28
- [x] Tag each lesson with topic tags (M1's vocabulary) so mastery + roadmap work — @member3, 2026-09-28
- [x] Upload UI: drop a file, see the generated course, edit titles — @member3, 2026-09-28
- [x] Security pass: file type/size limits, per-user ownership, RLS check — @member3, 2026-09-28
- [x] **Rebuilt 2026-09-29 — uploads were not learnable.** A real OS-slides
      upload came back as verbatim slide text, lessons titled "Dept. of CSE,
      BUET", every lesson tagged `dbms.er_model` (the keyword tagger fell back
      to the first topic on the list), so "Practice this lesson" produced a
      DBMS quiz. Now `services/notes_course.py`: the model plans lessons from
      the numbered notes, then teaches each one from **only its own chunks**
      (explanation, worked example, key terms, recap). Runs as a generation
      job with a progress bar. Verified live on the same notes: three lessons
      tagged `os.race_conditions`, `os.producer_consumer`, `os.semaphores`.
      `notes_extractor.py` keeps validation + extraction only — @sahilaf, 2026-09-29
- [x] **The topic vocabulary can grow, deliberately.** It was closed at 12 DBMS /
      Python / Web tags, and both upload and goal-based course generation
      forced anything else onto "the closest" one. A model may now propose
      `subject.topic` *with a label*; `topics.register` reuses an existing tag
      with the same label or a plural spelling before creating one, and caps
      new tags per call. Quizzes must be answerable from the lesson alone, and
      a recorded misconception is only targeted when the lesson teaches it — @sahilaf, 2026-09-29

> ⚠️ Courses uploaded **before** 2026-09-29 keep their wrong tags and raw text.
> Re-upload the file to get a taught course; delete the old one from Courses.

**✅ Hand off when:** you upload a PDF and it appears as a private course you can
learn from, with a roadmap generated over it.
**→ Push, then tell M4.**


---

## 🟣 Slot 12 · Member 4 · Days 19–20

**Analytics that show the learning, not just the score.**

All four `analytics.py` routes are stubs returning zeros — this slot is where they
become real.

- [x] `GET /api/analytics/me/summary` + `/me/activity` — real numbers — @oni, 2026-09-28
- [x] Review-queue analytics: due today, overdue, retention rate — @oni, 2026-09-28
- [x] **Misconception map** from M1's `/api/mastery/me/misconceptions`:
      active / fading / cleared over time — @oni, 2026-09-28
- [x] Mastery chart per topic — @oni, 2026-09-28
- [x] Seed ~15 badges (only 2 exist today) + daily challenges; claim flow — @oni, 2026-09-28
- [x] Build `/api/notifications` — it is a stub returning `{items: [], unread: 0}` —
      then wire the bell — @oni, 2026-09-28

**✅ Week 3 is done when:** the app can say *"here is what you misunderstood, here
is when you will see it again, and here is the proof you fixed it."*

---

# 🗓️ WEEK 4 — harden and ship

> No new features. If something is not working by day 21, cut it.

## 🔵 Slot 13 · Member 1 · Days 21–22

- [ ] SyncTalk latency pass; measure and state the real number — @, 2026-__-__
- [ ] Every AI call has a fallback path and a timeout — @, 2026-__-__
- [ ] Rate-limit AI endpoints (they cost money per call) — @, 2026-__-__
- [ ] Cache repeat roadmap/misconception calls where safe — @, 2026-__-__
- [ ] Measure TTS latency end to end; it is now on the critical path for every
      spoken reply (`services/tts.py` caches repeats, nothing else) — @, 2026-__-__

## 🟢 Slot 14 · Member 2 · Days 22–23

- [x] Empty state on every list and table — @skredwanulislam, 2026-09-28
- [x] Loading + error state on every page that fetches — @skredwanulislam, 2026-09-28
- [x] Full mobile pass at 375px — @skredwanulislam, 2026-09-28
- [x] Bug fixing from the Week 3 integration list — @skredwanulislam, 2026-09-28
- [x] **N+1 in `/api/me/progress` and `/api/me/enrollments` fixed** — both now
      prefetch the user's `lesson_progress` once (`_progress_by_lesson`) instead
      of querying per enrolled course. Measured flat at **2 queries** for 1, 5,
      10 and 25 courses; was 11 at ten courses. `/api/me/history` was already
      correct. Guarded by `tests/test_progress_queries.py`, which asserts the
      count, not just the output — @sahilaf, 2026-09-22

## 🟠 Slot 15 · Member 3 · Days 23–24

- [ ] Final clean seed for the demo database — @, 2026-__-__
- [x] **`pool_pre_ping` turned off** — measured at **105 ms on every request**,
      paid even by requests that touch no data. Replaced with `pool_recycle=240`
      (well inside the pooler's idle timeout), both tunable via `DB_PRE_PING`
      and `DB_POOL_RECYCLE_SECONDS`. ⚠️ If "server closed the connection
      unexpectedly" ever appears in the logs, set `DB_PRE_PING=true` — @sahilaf, 2026-09-22
- [ ] README setup instructions verified on a fresh clone — @, 2026-__-__
- [ ] `DEV_ALLOW_ANONYMOUS=false` verified in the deployed env, RLS on every table — @, 2026-__-__
- [ ] Deploy (or a rehearsed local demo path) — @, 2026-__-__

## 🟣 Slot 16 · Member 4 · Days 24–26

- [x] Full test pass across every page and role (166 backend tests passing, frontend Vite build clean) — @oni, 2026-09-28
- [x] Bug triage: file, assign, verify fixes (fixed teachback handler teardown bug, naive vs aware UTC datetime comparison, badge test backwards-compat) — @oni, 2026-09-28
- [x] Presentation slides + the report — @oni, 2026-09-28

---

## 🔴 Days 26–28 · Everyone · Dry run

- [ ] Run the demo script below, start to finish, three times — @, 2026-__-__
- [ ] Fix whatever breaks — @, 2026-__-__
- [ ] Rehearse the 5-minute demo with one person driving — @, 2026-__-__
- [ ] Have an answer ready for "what would you build next?" — @, 2026-__-__

---

## Open gaps

Numbered so slot items can point here instead of repeating themselves.
**Close G1 first** — it is the only one that blocks the pitch.

### ~~[G1] — `quiz.submitted` carries no `answers`~~ · **closed 2026-09-22**

`quizzes.py:345` still emits only the counts, but `handle_quiz_submitted()` now
reads `attempt_answers` back by `attempt_id` when the payload omits them. The
misconception engine fires on the event M2 already emits, and M2's router was not
touched. Covered by `TestG1AnswersFallback`.

### ~~[G2] — Google sign-in fails at the token exchange~~ · **closed 2026-09-29**

Google sign-in verified working end to end on 2026-09-29.

<details><summary>the original report</summary>


Supabase returns *"Unable to exchange external code"*, which means the Google
**Client Secret in Supabase does not match the Client ID**. Re-paste both, and set
the authorised redirect URI in Google Cloud to
`https://dkyvtuzutcblcpeerqeo.supabase.co/auth/v1/callback`.
Email/password sign-in works today. *(Owner: M3, Slot 3.)*

</details>

### ~~[G3] — The dashboard never calls the roadmap~~ · **closed 2026-09-29**

`components/tutor/ForYouPanel.jsx` loads `GET /api/roadmap/me` itself and is
dropped into `Dashboard.jsx` at one line, so M4's page logic is untouched. It
also shows today's plan and the ranked recommendations.

<details><summary>the original report</summary>


`Dashboard.jsx` imports `api/courses` and `api/gamification` only; its `nextAction`
(line 128) is derived from enrollments + progress. `RoadmapPage.jsx` is the only
consumer of `api/roadmap.js`. `GET /api/roadmap/me` is real — the dashboard just
does not call it, so "AI plans your next step" is invisible on the first screen
after login. *(Owner: M4, Slot 4.)*

</details>

### ~~[G4] — SyncTalk Tier B renders the wrong transport~~ · **closed 2026-09-22**

The `<img src>` is gone. `useSyncTalkStream.js` speaks the real protocol —
16-byte little-endian header, `frame_index == 0xFFFFFFFF` marking a PCM packet,
JPEG otherwise — and draws to `<canvas>` on the audio clock. `SyncTalkStage.jsx`
renders it, and `AvatarStage.jsx` swaps back to the SVG the moment it reports
unavailable.

### ~~[G6] — Tier B has no audio source~~ · **closed 2026-09-22**

`services/tts.py` calls Gemini TTS, which returns `audio/L16;codec=pcm;rate=24000`
— raw PCM at exactly the rate SyncTalk works in, so no resampling. The browser
fetches it from `POST /api/avatar/speech` as binary and forwards it to the
service's audio socket as WAV chunks (each message must be a complete file; the
service runs `soundfile.read()` on every one).

The backend refuses any sample rate other than the stream's rather than shipping
one that would desynchronise the mouth silently.

### ~~[G5] — `DEV_ALLOW_ANONYMOUS` does not fail closed~~ · **closed 2026-09-28**

The default is now `False`, and `Settings.allow_anonymous` refuses it in
production whatever the environment says. Verified: a fresh deploy with no
`.env` gets `False` in both dev and production; production with the flag forced
on still resolves `False`; local development still works.

<details><summary>the original report</summary>

### [G5] — `DEV_ALLOW_ANONYMOUS` does not fail closed

`config.py:27` defaults it to `True`. `main.py:110` only *logs an error* in
production — it does not refuse to start or deny the request, and `deps.py:295`
and `deps.py:332` still grant anonymous access. Every endpoint will answer an
unauthenticated caller. Flip the default and make production fail closed before
anything is deployed. *(Owner: M3, Slots 7 and 15.)*

</details>

---

## Repo state — audited 2026-09-29

Read from the code, not from the boxes above.

### Still a placeholder (11 lines each)

None. Leaderboard and Profile were built 2026-09-29; Stats (with the
misconception map) was built by M4 on 2026-09-28.

`History` is built (301 lines) and routed but absent from `NAV`, so it is
reachable only from a single Dashboard link.

### Backend

**Real:** all `courses` (incl. `POST /generate`) · `lessons` · `progress` ·
`users` · `admin` (14 routes) · `quizzes` (fetch, attempts, submit, review, and
both `/generate` routes) · `gamification` stats / badges / achievements ·
all `roadmap` · all `mastery` · all `tutor` (7 + 5 Teach-Back) · all `avatar`
(status / config / session / speech) · all `jobs`

Also real since 2026-09-29: `review` · `practice` · `recommendations` ·
`quizzes` `grade-open` · `gamification` leaderboard.

**Frontend fallbacks removed:** `api/practice.js` and `api/review.js` used to
fake grading when the backend failed. They now surface the error instead.

### Migrations

`0001` → `0010`, single linear chain, no branching heads. ✅
`review_items` is in use; `0010` adds the three practice tables.

### Tests

**285 backend tests, all passing**, with zero real model calls (every LLM path is stubbed). `test_practice`, `test_review_and_recommendations` and `test_leaderboard` are new as of 2026-09-29. Earlier: `test_teachback`, `test_tts`,
`test_topics_and_jobs`, `test_quiz_generator`, `test_course_planner` and
`test_progress_queries` are new.

> **M4 — those three XP tests were not flaky, they were right.** I said earlier
> they passed for the wrong reason; that was wrong. `xp_events.created_at` is
> written in UTC while "today" came from `date.today()`, the machine's *local*
> date. East of Greenwich those disagree for the first hours after local
> midnight, so every "has this happened today?" lookup answered no: the
> daily-login bonus could be claimed repeatedly and the 25 XP/day tutor cap
> stopped applying. A six-hour hole every night, not a test problem. Fixed
> 2026-09-28 and pinned by `test_xp_day_boundary.py`, which fails whatever hour
> it runs at.

---

## Cut from scope

- [-] Duolingo-style playful design — replaced 2026-09-21 with the professional
      HackerRank-style system at the faculty's request
- [-] Separate mobile app — the web UI is responsive
- [-] Live collaborative study rooms — out of scope for this timeline

**Restored into Weeks 3–4** (were cut when the plan was two weeks): free-response
grading, spaced-repetition review queue, upload-your-notes → course, practice
problems, interleaving, daily challenges.

---

## Blockers

> Add a line the moment you are stuck. Do not stall silently — the next person
> in the relay is waiting on you.

- [ ] *(none logged — every gap above is closed)*
