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

## Where we actually are — audited 2026-09-22

Every `[x]` below was re-checked against the code, not trusted.

| Member | Done | In progress | Open | Total |
|---|---|---|---|---|
| **M1** (AI) | 15 | 0 | 12 | 27 |
| **M2** (Learning) | 12 | 0 | 17 | 29 |
| **M3** (Users) | 7 | 1 | 14 | 22 |
| **M4** (Game) | 6 | 0 | 19 | 25 |
| | **40** | **1** | **62** | **103** | **1** | **61** | **100** | **1** | **61** | **98** | **2** | **68** | **97** |

Plus 4 shared dry-run items in Days 26-28.

Week 1 is nearly closed and the admin panel shipped a week early. **Slot 5 is
done: the misconception engine fires, the Teach-Back loop runs end to end, and
the avatar speaks.** G1, G4 and G6 are closed. G2, G3 and G5 remain, and none of
them block the pitch. See [Open gaps](#open-gaps) — slot items reference them by
ID so the lists stay scannable.

**Tier A was removed on 2026-09-22.** There is one avatar (SyncTalk) and one
voice (Gemini TTS). Without a GPU service the tutor page shows an "avatar
offline" panel naming what is missing; chat and Teach-Back are unaffected, which
is what M2/M3/M4 will see.

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
- [ ] Fix the Google token exchange — **see [G2]** — @, 2026-__-__
- [ ] Add Supabase redirect URLs for **both 5173 and 5174** (Vite falls back) — @, 2026-__-__
- [ ] Verify sign-up creates a `public.users` row — @, 2026-__-__
- [ ] `Profile.jsx` — name, email, avatar (still an 11-line placeholder) — @, 2026-__-__

**✅ Hand off when:** a stranger can sign up with Google and see their profile.
**→ Push, then tell M4.**

---

## 🟣 Slot 4 · Member 4 · Day 5

**Dashboard — the first screen after login.**

- [x] XP + level + progress bar from `GET /api/me/stats` (real `UserStats` query) — @rhossain222308-del, 2026-09-21
- [x] Streak counter — @rhossain222308-del, 2026-09-21
- [x] "Continue learning" — uses M2's `/api/me/progress` — @rhossain222308-del, 2026-09-21
- [x] Header streak/XP in `AppLayout.jsx` wired to `myStats()` — @rhossain222308-del, 2026-09-21
- [ ] "Next quest" from `GET /api/roadmap/me` — **see [G3]**, not wired — @, 2026-__-__

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
- [ ] Add **History** to `NAV` in `AppLayout.jsx` — the page is built and routed but
      reachable only from a single Dashboard link — @, 2026-__-__
- [ ] `Stats.jsx` + **misconception map** — use M1's `GET /api/mastery/me` and
      `GET /api/mastery/me/misconceptions`, which return real data.
      **Not** `analytics.py`'s `/mastery/me`, which is a stub — @, 2026-__-__
- [ ] `GET /api/leaderboard` — currently returns `{items: [], me: null}` → `Leaderboard.jsx` — @, 2026-__-__
- [ ] Add each page to `NAV` as it stops being a placeholder — @, 2026-__-__

**✅ Hand off when:** no nav link is a dead end, and no built page is unreachable.

---

# 🗓️ WEEK 3 — the learning-science layer

> Weeks 1–2 make the loop work. Week 3 is what makes it a *learning* product
> rather than a quiz app, and it restores the Tier 1/Tier 2 items from plan.md
> §0.1 that a 2-week scope had to drop.

## 🔵 Slot 9 · Member 1 · Days 13–15

**Free-response grading + spaced repetition.**

Free text is **Tier 1 in plan.md** and matters more than it looks: the misconception
engine currently only sees multiple-choice answers, the weakest possible signal for
inferring a false belief. Typed answers are where it actually works.

- [ ] `POST /api/quizzes/attempts/{id}/grade-open` — LLM grades a typed answer against
      the expected one → correct / partial / incorrect + written feedback
      *(the route exists as a stub today)* — @, 2026-__-__
- [ ] Feed the typed answer into `capture_misconception()` (much richer input) — @, 2026-__-__
- [ ] Guard: never mark correct on the model's word alone — require the rubric match,
      abstain to "needs review" when unsure — @, 2026-__-__
- [ ] **Review queue generation** on the `review_items` table — it exists in
      `models/ai.py:214` and migration `0003`, with `due_at` indexed, and is unused — @, 2026-__-__
- [ ] `GET /api/review/today` — what is due now, weakest and most overdue first — @, 2026-__-__
- [ ] `POST /api/review/{id}/answer` — grade, reschedule, update mastery — @, 2026-__-__
- [ ] **Interleave**: a review session mixes topics rather than blocking one topic — @, 2026-__-__

**✅ Hand off when:** a wrong typed answer schedules a review, and it comes back
on the right day mixed with other topics.
**→ Push, then tell M2.**

---

## 🟢 Slot 10 · Member 2 · Days 15–17

**Practice problems + the review screen.**

- [ ] `/practice` route + restore the nav entry (commented out at `AppLayout.jsx:36`) — @, 2026-__-__
- [ ] Problem page: statement, input/output examples, test cases — @, 2026-__-__
- [ ] Submit → pass/fail per test case, stored as an attempt — @, 2026-__-__
- [ ] "Skill verified" once N problems in a skill pass — @, 2026-__-__
- [ ] **Review screen** driven by M1's `/api/review/today` — one card at a time — @, 2026-__-__
- [ ] Free-response question type in `QuizPlayer` (textarea + M1's grader) — @, 2026-__-__
- [ ] Mobile pass over Courses / Lesson / Quiz — @, 2026-__-__

**→ Push, then tell M3.**

---

## 🟠 Slot 11 · Member 3 · Days 17–19

**Upload your own notes → a course.**

The differentiator plan.md describes: an uploaded PDF becomes a course using the
same tables and the same pipeline, so nothing downstream knows the difference.
`POST /api/admin/upload` and `POST /api/uploads` already exist to build on.

- [ ] `POST /api/courses/upload` — accept a PDF/markdown file — @, 2026-__-__
- [ ] Extract text, split into lesson-sized sections — @, 2026-__-__
- [ ] Create `Course` + `Lesson` rows marked `source="upload"`, `is_private=true` — @, 2026-__-__
- [ ] Tag each lesson with topic tags (M1's vocabulary) so mastery + roadmap work — @, 2026-__-__
- [ ] Upload UI: drop a file, see the generated course, edit titles — @, 2026-__-__
- [ ] Security pass: file type/size limits, per-user ownership, RLS check — @, 2026-__-__

**✅ Hand off when:** you upload a PDF and it appears as a private course you can
learn from, with a roadmap generated over it.
**→ Push, then tell M4.**

---

## 🟣 Slot 12 · Member 4 · Days 19–20

**Analytics that show the learning, not just the score.**

All four `analytics.py` routes are stubs returning zeros — this slot is where they
become real.

- [ ] `GET /api/analytics/me/summary` + `/me/activity` — real numbers — @, 2026-__-__
- [ ] Review-queue analytics: due today, overdue, retention rate — @, 2026-__-__
- [ ] **Misconception map** from M1's `/api/mastery/me/misconceptions`:
      active / fading / cleared over time — @, 2026-__-__
- [ ] Mastery chart per topic — @, 2026-__-__
- [ ] Seed ~15 badges (only 2 exist today) + daily challenges; claim flow — @, 2026-__-__
- [ ] Build `/api/notifications` — it is a stub returning `{items: [], unread: 0}` —
      then wire the bell — @, 2026-__-__

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

- [ ] Empty state on every list and table — @, 2026-__-__
- [ ] Loading + error state on every page that fetches — @, 2026-__-__
- [ ] Full mobile pass at 375px — @, 2026-__-__
- [ ] Bug fixing from the Week 3 integration list — @, 2026-__-__
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

- [ ] Full test pass across every page and role — @, 2026-__-__
- [ ] Bug triage: file, assign, verify fixes — @, 2026-__-__
- [ ] Presentation slides + the report — @, 2026-__-__

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

### [G2] — Google sign-in fails at the token exchange

Supabase returns *"Unable to exchange external code"*, which means the Google
**Client Secret in Supabase does not match the Client ID**. Re-paste both, and set
the authorised redirect URI in Google Cloud to
`https://dkyvtuzutcblcpeerqeo.supabase.co/auth/v1/callback`.
Email/password sign-in works today. *(Owner: M3, Slot 3.)*

### [G3] — The dashboard never calls the roadmap

`Dashboard.jsx` imports `api/courses` and `api/gamification` only; its `nextAction`
(line 128) is derived from enrollments + progress. `RoadmapPage.jsx` is the only
consumer of `api/roadmap.js`. `GET /api/roadmap/me` is real — the dashboard just
does not call it, so "AI plans your next step" is invisible on the first screen
after login. *(Owner: M4, Slot 4.)*

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

### [G5] — `DEV_ALLOW_ANONYMOUS` does not fail closed

`config.py:27` defaults it to `True`. `main.py:110` only *logs an error* in
production — it does not refuse to start or deny the request, and `deps.py:295`
and `deps.py:332` still grant anonymous access. Every endpoint will answer an
unauthenticated caller. Flip the default and make production fail closed before
anything is deployed. *(Owner: M3, Slots 7 and 15.)*

---

## Repo state — audited 2026-09-22

### Frontend pages

| Built | Still an 11-line placeholder |
|---|---|
| Landing (353) · Login (198) · Register (228) · ForgotPassword (133) | **Leaderboard** |
| Dashboard (547) · CourseCatalog (319) · CourseDetail (684) | **Stats** |
| LessonViewer (761) · QuizPlayer (453) · QuizResult (300) | **Profile** |
| Roadmap (443) · Tutor (441) · Achievements (271) · History (301) | |
| Admin: Overview (320) · Users (303) · Courses (1323) | |

All are routed in `App.jsx`. Only five appear in `NAV` — **History is built but
effectively unreachable** (Slot 8).

### Backend endpoints

**Real:** all `courses` · `lessons` · `progress` · `users` · `admin` (14 routes) ·
`quizzes` fetch + attempts + submit + review · `gamification` stats / badges /
achievements · all `roadmap` (4) · all `mastery` (2) · all `tutor` (7 + 5 Teach-Back) ·
all `avatar` (status / config / session / speech)

**Still stubs:** `analytics.py` (all 4) · `gamification` leaderboard + challenges +
notifications · `quizzes` generate / generate-adaptive / grade-open ·
`recommendations` list + dismiss + daily-plan

### Migrations

`0001` → `0007`, single linear chain, no branching heads. ✅
`0007_m1_teachback_sessions` adds the Teach-Back table.
Unused table ready for Slot 9: `review_items` (`models/ai.py:214`, migration `0003`).

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

- [ ] *(none logged — G2, G3, G5 and G6 above are tracked work, not stalls)*
