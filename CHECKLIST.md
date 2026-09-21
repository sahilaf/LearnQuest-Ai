# LearnQuest AI — 4-Week Delivery Checklist

> **How this works:** one member works at a time, in slot order. When your slot is
> done you **push to `main` and message the group**. The next person pulls and starts.
> Nobody works on the same files at the same time, so there are no merge conflicts.
>
> Tick `[x]` only when it works end to end: API returns real data → UI renders it →
> still works after `git pull`.
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

## File ownership — never edit someone else's files

| Member | Backend | Frontend |
|---|---|---|
| **M1** (AI) | `routers/{tutor,avatar,roadmap}.py`, `services/{llm_client,prompts,mastery,roadmap_planner}.py`, `models/{ai,roadmap}.py` | `pages/{Tutor,Roadmap}/`, `components/avatar/`, `api/{tutor,avatar,roadmap}.js` |
| **M2** (Learning) | `routers/{courses,lessons,progress,quizzes}.py`, `models/{course,progress,quiz}.py` | `pages/{Courses,Lesson,Quiz,Practice}/`, `components/ui/`, `api/{courses,lessons,quizzes}.js` |
| **M3** (Users) | `routers/{auth,users,admin}.py`, `models/user.py`, `deps.py` | `pages/{Auth,Profile,Admin}/`, `components/layout/`, `context/AuthContext.jsx` |
| **M4** (Game) | `routers/{gamification,analytics}.py`, `services/{xp_engine,events}.py`, `models/gamification.py` | `pages/{Dashboard,Achievements,Leaderboard,Stats,History}/`, `api/{gamification,analytics}.js` |

**Shared — announce before touching:** `app/main.py` · `app/models/__init__.py` ·
`frontend/src/App.jsx` · `tailwind.config.js` · `index.css` · `api/client.js`

**Design:** all frontend work follows [docs/DESIGN_GUIDELINES.md](docs/DESIGN_GUIDELINES.md).

---

# 🗓️ WEEK 1 — make the core loop real

## 🔵 Slot 1 · Member 1 · Days 1–2

**AI misconception engine — the novel core.**

- [x] Implement `services/mastery.py::capture_misconception()` — LLM names the
      **false belief** behind a wrong answer in plain English — @sahilaf, 2026-09-21
- [x] Reject invented misconceptions: if the model is unsure, store `None` — @sahilaf, 2026-09-21
- [x] Register a `quiz.submitted` handler that calls it *(fires once M2 emits in Slot 2)* — @sahilaf, 2026-09-21
- [x] `GET /api/mastery/me/misconceptions` — list with status active/fading/cleared — @sahilaf, 2026-09-21
- [x] Decay: N correct answers moves active → fading → cleared — @sahilaf, 2026-09-21

**✅ Hand off when:** you can POST a wrong answer and see a misconception row written.
**→ Push, then tell M2.**

---

## 🟢 Slot 2 · Member 2 · Days 2–4

**⛔ FIRST: unblock the database.** Quiz + progress tables don't exist — the models
are commented out in `models/__init__.py:3`, so they were never migrated.

- [x] Uncomment `from app.models import progress, quiz` — @skredwanulislam, 2026-09-21
- [x] Create + run migration `0006_m2_quiz_progress_schema` — set
      `down_revision = "0005_m1_misconception_tracking"` so it chains instead of
      branching (two heads off 0004 would need an alembic merge) — @skredwanulislam, 2026-09-21
- [x] Verify `quizzes`, `quiz_questions`, `quiz_attempts`, `lesson_progress` exist — @skredwanulislam, 2026-09-21

**Then make quizzes work** — nothing in the app has a game loop without this.

- [x] `GET /api/quizzes/{id}` — questions **with `correct_answer` stripped**
      (security, plan.md 7.3 — never send answers to the client) — @skredwanulislam, 2026-09-21
- [x] `POST /api/quizzes/{id}/attempts` — create attempt — @skredwanulislam, 2026-09-21
- [x] `POST /api/quizzes/attempts/{id}/submit` — score + persist — @skredwanulislam, 2026-09-21
- [x] **`emit(db, user_id, "quiz.submitted", payload)` on submit** — triggers M1's
      misconception capture *and* M4's XP. The payload **must** include an
      `answers` list or no misconception can be identified: — @skredwanulislam, 2026-09-21
      ```python
      {"quiz_id": ..., "correct_count": 3, "total_questions": 5,
       "answers": [{"topic_tag": "dbms.sql_joins", "prompt": "...",
                    "correct_answer": "...", "user_answer": "...",
                    "is_correct": False}, ...]}
      ```
- [x] `QuizPlayer.jsx` — one question at a time, progress — @skredwanulislam, 2026-09-21
- [x] `QuizResult.jsx` — score + per-question review — @skredwanulislam, 2026-09-21
- [x] `GET /api/me/progress` — real *(M4 needs this in Slot 4)* — @skredwanulislam, 2026-09-21

**✅ Hand off when:** you can take a quiz, get a score, and M1's misconception
appears for a wrong answer.
**→ Push, then tell M3.**

---

## 🟠 Slot 3 · Member 3 · Day 4–5

**Auth — blocks every real demo.**

- [ ] Enable **Google OAuth** in the Supabase dashboard (only `email` is on today —
      verified via `/auth/v1/settings`) — @, 2026-__-__
- [ ] Add redirect URLs for **both 5173 and 5174** (Vite falls back) — @, 2026-__-__
- [ ] Verify sign-up creates a `public.users` row — @, 2026-__-__
- [ ] `GET/PATCH /api/users/me` — @, 2026-__-__
- [ ] `Profile.jsx` — name, email, avatar — @, 2026-__-__

**✅ Hand off when:** a stranger can sign up with Google and see their profile.
**→ Push, then tell M4.**

---

## 🟣 Slot 4 · Member 4 · Day 5

**Dashboard — the first screen after login, currently blank.**

- [x] XP + level + progress bar — `GET /api/me/stats` *(already real)* — @rhossain222308-del, 2026-09-21
- [x] Streak counter *(already real)* — @rhossain222308-del, 2026-09-21
- [x] "Continue learning" — uses M2's `/api/me/progress` — @rhossain222308-del, 2026-09-21
- [x] "Next quest" — `GET /api/roadmap/me` *(already real)* — @rhossain222308-del, 2026-09-21
- [x] Wire header streak/XP in `AppLayout.jsx` to real values (hardcoded `0` today) — @rhossain222308-del, 2026-09-21

**✅ Week 1 is done when:** sign up → dashboard shows real numbers → take a quiz →
get one wrong → the app names your misconception.

---

# 🗓️ WEEK 2 — the novel feature + fill the gaps

## 🔵 Slot 5 · Member 1 · Days 6–8

**SyncTalk photoreal tutor + Teach-Back — the demo moment.**

⚠️ The current Tier B code is **wrong**: `AvatarStage.jsx` renders the stream as
`<img src>` (MJPEG), but the server sends framed binary over WebSocket:
`[4B segment][4B frame_idx][4B total][4B audio_ms] + JPEG`.

- [ ] WS client: decode binary frames → `<canvas>` — @, 2026-__-__
- [ ] Sync the PCM audio segments to the frames — @, 2026-__-__
- [ ] Fall back to the SVG avatar when `AVATAR_SERVICE_URL` is unset or down — @, 2026-__-__
- [ ] **Teach-Back:** seed Nova with the student's own misconception — @, 2026-__-__
- [ ] Nova asks naive questions and pushes back on vague answers — @, 2026-__-__
- [ ] **Nova re-takes the question — its score is the student's grade** — @, 2026-__-__
- [ ] On success mark the misconception `fading` + award XP via `emit()` — @, 2026-__-__

**✅ Hand off when:** the full loop runs — wrong answer → misconception → teach
Nova → Nova passes.
**→ Push, then tell M2.**

---

## 🟢 Slot 6 · Member 2 · Days 8–10

**Courses in HackerRank shape.**

- [ ] Restructure catalogue as **Tracks → Skills → Problems** — @, 2026-__-__
- [ ] Difficulty chips (Easy/Medium/Hard) via `Badge tone=` — @, 2026-__-__
- [ ] Solve % + attempt count per skill — @, 2026-__-__
- [ ] Use `.table-dense` rows, not big cards — @, 2026-__-__
- [ ] Filters: subject, difficulty, status, search — @, 2026-__-__
- [x] `GET /api/me/history` — real *(M4 needs it next)* — @skredwanulislam, 2026-09-21

**✅ Hand off when:** the courses page looks like a practice platform, not a shop.
**→ Push, then tell M3.**

---

## 🟠 Slot 7 · Member 3 · Day 10–11

**Admin panel.**

- [x] `AdminOverview.jsx` — user/course/activity counts — @member3, 2026-09-21
- [x] `AdminCourses.jsx` — create / edit / publish a course — @member3, 2026-09-21
- [x] `GET /api/admin/overview` — real numbers — @member3, 2026-09-21
- [x] Confirm `DEV_ALLOW_ANONYMOUS=false` anywhere deployed — @member3, 2026-09-21 · guarded by `is_production` check and env settings

**→ Push, then tell M4.**

---

## 🟣 Slot 8 · Member 4 · Days 11–12

**Fill every remaining dead page.**

- [ ] `GET /api/leaderboard` — real → `Leaderboard.jsx` (`.table-dense`) — @, 2026-__-__ *(descoped for Week 2)*
- [x] Seed badges + `GET /api/me/badges` → `Achievements.jsx` — @rhossain222308-del, 2026-09-21
- [ ] `GET /api/mastery/me` → `Stats.jsx` + **misconception map** (M1's API) — @, 2026-__-__
- [x] `History.jsx` from M2's `/api/me/history` — @rhossain222308-del, 2026-09-21

**✅ Hand off when:** no nav link is a dead end.

---

# 🗓️ WEEK 3 — the learning-science layer

> Weeks 1–2 make the loop work. Week 3 is what makes it a *learning* product
> rather than a quiz app, and it restores the Tier 1/Tier 2 items from plan.md
> §0.1 that a 2-week scope had to drop.

## 🔵 Slot 9 · Member 1 · Days 13–15

**Free-response grading + spaced repetition.**

Free text is **Tier 1 in plan.md** and it matters more than it looks: the
misconception engine currently only sees multiple-choice answers, which is the
weakest possible signal for inferring a false belief. Typed answers are where it
actually works.

- [ ] `POST /api/quizzes/attempts/{id}/grade-open` — LLM grades a typed answer
      against the expected one, returns correct/partial/incorrect + written feedback — @, 2026-__-__
- [ ] Feed the typed answer into `capture_misconception()` (much richer input) — @, 2026-__-__
- [ ] Guard: never mark correct on the model's word alone — require the rubric
      match, and abstain to "needs review" when unsure — @, 2026-__-__
- [ ] **Review queue generation** on the unused `review_items` table: schedule a
      topic for review at expanding intervals after a wrong answer — @, 2026-__-__
- [ ] `GET /api/review/today` — what is due now, weakest and most overdue first — @, 2026-__-__
- [ ] `POST /api/review/{id}/answer` — grade, reschedule, update mastery — @, 2026-__-__
- [ ] **Interleave**: a review session mixes topics rather than blocking one
      topic at a time (plan.md calls this half a day's work, real gain) — @, 2026-__-__

**✅ Hand off when:** a wrong typed answer schedules a review, and it comes back
on the right day mixed with other topics.
**→ Push, then tell M2.**

---

## 🟢 Slot 10 · Member 2 · Days 15–17

**Practice problems + the review screen.**

- [ ] `/practice` route + add the nav entry (marked TODO in `AppLayout.jsx`) — @, 2026-__-__
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

- [ ] `POST /api/courses/upload` — accept a PDF/markdown file — @, 2026-__-__
- [ ] Extract text, split into lesson-sized sections — @, 2026-__-__
- [ ] Create a `Course` + `Lesson` rows marked `source="upload"`, `is_private=true` — @, 2026-__-__
- [ ] Tag each lesson with topic tags (M1's vocabulary) so mastery + roadmap work — @, 2026-__-__
- [ ] Upload UI: drop a file, see the generated course, edit titles — @, 2026-__-__
- [ ] Security pass: file type/size limits, per-user ownership, RLS check — @, 2026-__-__

**✅ Hand off when:** you upload a PDF and it appears as a private course you can
learn from, with a roadmap generated over it.
**→ Push, then tell M4.**

---

## 🟣 Slot 12 · Member 4 · Days 19–20

**Analytics that show the learning, not just the score.**

- [ ] Review-queue analytics: due today, overdue, retention rate — @, 2026-__-__
- [ ] **Misconception map** from M1's `/api/mastery/me/misconceptions`:
      active / fading / cleared over time — @, 2026-__-__
- [ ] Mastery chart per topic — @, 2026-__-__
- [ ] Seed ~15 badges + daily challenges; claim flow — @, 2026-__-__
- [ ] Notifications bell wired to `/api/notifications` *(already real)* — @, 2026-__-__

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

## 🟢 Slot 14 · Member 2 · Days 22–23

- [ ] Empty state on every list and table — @, 2026-__-__
- [ ] Loading + error state on every page that fetches — @, 2026-__-__
- [ ] Full mobile pass at 375px — @, 2026-__-__
- [ ] Bug fixing from the Week 3 integration list — @, 2026-__-__

## 🟠 Slot 15 · Member 3 · Days 23–24

- [ ] Final clean seed for the demo database — @, 2026-__-__
- [ ] README setup instructions verified on a fresh clone — @, 2026-__-__
- [ ] `DEV_ALLOW_ANONYMOUS=false`, RLS verified on every table — @, 2026-__-__
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

## 🎬 Demo script

**Core loop (weeks 1–2):**

1. Sign up → state a goal → **AI draws a branching roadmap** from the real catalogue
2. Open a lesson → take a quiz → **answer in your own words** → get one wrong
3. Screen names **the false belief**, not just "incorrect"
4. **Nova appears — photoreal — holding that same wrong belief**
5. Student talks her out of it
6. **Nova re-takes the question and passes** → XP → roadmap re-plans

**The learning-science close (week 3) — this is what separates it from a quiz app:**

7. *"That misconception is now scheduled for review in 2 days."*
8. Come back → the review queue **mixes it with other topics** (interleaving)
9. Answer it right twice → the misconception map shows **active → fading → cleared**
10. *"And you can upload your own notes"* → drop a PDF → it becomes a course
    with its own roadmap

---

## Already working (don't rebuild)

Landing · Login/Register · Courses list · Course detail · Lesson viewer ·
AI Tutor chat · **AI Roadmap** · XP engine · DB with 3 courses / 15 lessons ·
Professional design system

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

- [ ] *(none logged)*
