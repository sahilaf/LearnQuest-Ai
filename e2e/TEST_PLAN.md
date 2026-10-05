# LearnQuest — End-to-End Test Plan and Report

**Tool:** Playwright 1.x (Chromium) · **Suite:** `e2e/tests/` · **Last run:** 2026-10-06 —
**17 / 17 passed**, stable across consecutive runs, ~65 s per run.

## 1. What "end to end" means here

Each test drives a real browser through a complete student journey against the
**real frontend** (Vite dev server), the **real backend** (FastAPI) and a **real
database** (SQLite, freshly created and seeded for every run). Assertions are made
on what a student actually sees on screen.

```
Playwright (Chromium) ──► frontend :5180 ──► backend :8100 ──► SQLite (temp, re-seeded per run)
                                                   └──► scripted AI (E2E_FAKE_AI=1)
```

## 2. Test environment

| Part | In the E2E run | Why |
|---|---|---|
| Database | SQLite file in the OS temp folder, deleted and re-seeded with the normal seed scripts at the start of every run | Repeatable state; never touches the shared Supabase database |
| Login | Frontend dev-login mode: every test signs up as a brand-new student through the real sign-up form | No real accounts or passwords; tests cannot interfere with each other |
| AI (Gemini / OpenRouter) | Scripted client (`backend/app/services/e2e_fakes.py`) that recognises each prompt the app sends and answers in the exact shape it asks for | Real models answer differently each run and cost quota; a test must fail only when the *code* is wrong |
| Text-to-speech | A short synthetic tone | No quota; the audio path is still exercised |
| Live voice tutor | A scripted Gemini-Live session behind the real WebSocket | Same reason; the browser ↔ backend socket is real |
| Microphone | Chromium's built-in fake microphone (a steady tone) | Lets the Live tab be tested without a person speaking |
| GPU avatar | Not running | Tests the "avatar offline" path; the real avatar is covered by the manual smoke test (§6) |

The scripted AI is switched on only by `E2E_FAKE_AI=1` and is **refused in
production** whatever the environment says.

## 3. Test cases

| # | Journey | Test file | Steps | Expected result | Result |
|---|---|---|---|---|---|
| 1 | Sign up | `01-auth` | Fill the sign-up form | Lands on the dashboard, welcomed, navigation visible | ✅ |
| 2 | Sign out / in | `01-auth` | Sign out, then sign in with the same email | Leaves the dashboard; signing in returns to it | ✅ |
| 3 | Protected pages | `01-auth` | Open `/tutor` while signed out | Redirected to log in | ✅ |
| 4 | Rejected session | `01-auth` | Backend answers 401 (expired / forged token) | Signed out, sent to the landing page with "Your session ended" | ✅ |
| 5 | Find and read a lesson | `02-learning` | Catalogue → course → lesson 1 | Course curriculum and lesson content shown, "Quiz me" available | ✅ |
| 6 | **Misconception engine** | `03-learning-loop` | Answer every question of quiz 1 wrong | Result page names the false belief ("You believe…") and offers "Teach Redwan to fix it" | ✅ |
| 7 | **Teach-Back** | `03-learning-loop` | Start Teach-Back; send "You are wrong."; then a real explanation; ask Redwan to re-take | Redwan holds the belief *and the question it came from*; the vague reply is pushed back on; the explanation convinces him; on the retake he gives the taught answer and the attempt passes | ✅ |
| 7b | Teach-Back fail | `03-learning-loop` | Three vague explanations, three retakes | Attempts count down 3 → 0; outcome says "Out of attempts" with the correct answer; never "fixed"; Try again opens a fresh session | ✅ |
| 7c | Teach-Back resume | `03-learning-loop` | Teach, explain once, go back, press Teach again | The same session reopens with the explanation still there | ✅ |
| 7d | Study first, hints | `03-learning-loop` | Start Teach-Back; open "Before you teach"; take 3 hints; follow the lesson link; come back | The lesson for the topic is linked; each hint is marked "only you can see this", the count drops 3 → 0 and the button disables; no hint contains the answer; the session resumes after reading | ✅ |
| 8 | Calm tutor page | `04-tutor` | Open the tutor page and wait | No avatar session, no speech request and no socket is opened | ✅ |
| 9 | Avatar unavailable | `04-tutor` | Press "Connect avatar" with no GPU service | "Avatar offline" with a plain reason and a Back button | ✅ |
| 10 | Chat with memory | `04-tutor` | Ask a question; reload the page | Answer shown; still there after reload | ✅ |
| 11 | **Live voice call** | `04-tutor` | Start a call; the fake mic "speaks"; type a message; end; open Chat | Both sides of the conversation shown as text; typed message answered; the call appears in the Chat history | ✅ |
| 12 | Turn status | `04-tutor` | Start a call | Status always shows whose turn it is, including "Redwan is speaking" | ✅ |
| 13 | SQL practice | `05-practice-progress` | Submit a wrong query, then a correct one | Wrong one fails the hidden tests; correct one passes (queries are really executed) | ✅ |
| 14 | Gamification | `05-practice-progress` | Finish a quiz; open Achievements and Leaderboard | First badge earned (1/15); student listed on the leaderboard as "You" | ✅ |

## 4. Defects found by this suite (all fixed)

Writing and running the suite found real bugs that the 320 backend unit
tests and 11 frontend unit tests did not:

| # | Defect | Severity | Fix |
|---|---|---|---|
| D1 | **Live tab never showed the transcript in development builds.** React StrictMode calls state updaters twice; the transcript updater changed a ref inside the updater, so the second call discarded the new line. Students saw no text reply. | High | Decide the bubble before calling `setTurns` (`useLiveConversation.js`) |
| D2 | **Teach-Back paired the wrong belief with the wrong question.** Misconceptions are stored per topic; with several wrong answers on one topic, Redwan held the belief from question 3 but was asked question 1. | High | Store the source question with the belief (`topic_mastery.misconception_question_id`, migration `0011`) and re-ask exactly that question |
| D3 | **Signing out right after signing up could sign the student straight back in.** A profile sync still in flight restored the user it was merging into. | Medium | Merge into the signed-in user only — never recreate one (`AuthContext.jsx`) |
| D4 | **Login and sign-up pages redirected during render**, a React error in the console on every visit. | Low | Redirect from an effect (`Login.jsx`, `Register.jsx`) |
| D5 | **A failed Teach-Back showed "Misconception Addressed"** directly under "Redwan still got it wrong". | High | Separate pass / fail outcomes; fail shows the answer and Try again |
| D6 | **Redwan repeated his previous line after every retake** (the retake adds no new line, but the speech hook fired on any session change). | Medium | Each line is spoken once, keyed by its timestamp |
| D7 | **Every "Teach" press opened a new session**, losing the student's explanations. | Medium | Resume the open session for that belief (backend) |
| D8 | **"Connect avatar" opened two GPU sessions** in development (StrictMode). | Medium | Defer session creation one tick |
| D9 | **Database one migration behind the code** made Teach-Back show "Network Error" and silently dropped misconceptions. | High | Migration applied; documented in the pull note |

## 5. How to run

One-time setup:

```bash
cd e2e
npm install
npx playwright install chromium
```

Run (starts the test backend and frontend itself, then stops them):

```bash
npm test
```

```bash
npm run report
```

`npm run report` opens the HTML report: every test with its steps, a **video**,
screenshots and a step-by-step **trace**. Ports 8100 and 5180 must be free; your
normal dev stack (8000 / 5173 / 5001) can keep running.

## 6. Manual smoke test with the real services

Automated runs use scripted AI by design. Before a demo, run once by hand with
the real services (`.\dev.ps1`, plugged in, Gemini key with quota):

1. Quiz 1 → answer wrong → a *sensible* misconception appears.
2. Teach Redwan → a real explanation convinces him → retake passes.
3. Tutor → Connect avatar → the face appears and idles.
4. Live conversation → speak into the real microphone → Redwan answers aloud through
   the avatar, the transcript fills in, the face does not drop to idle mid-sentence.
5. Chat → ask a question → a real answer; "Listen" speaks it in the male voice.

Record the date, tester and outcome of this run in the report.

## 7. Limits (stated honestly)

- AI *quality* is not tested automatically — only that every AI-driven feature
  works end to end. Quality is a human judgement (§6).
- Only Chromium is run; Firefox and WebKit could be added as extra projects in
  `playwright.config.js`.
- The GPU avatar's video is not tested automatically (needs the GPU service).
