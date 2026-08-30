# agent — real-time voice tutor (LiveKit + Gemini Live + SyncTalk)

**Owner:** Member 1 (Lead). Brought over from the `Fydp_v2` project.

A working **real-time voice agent**: the learner speaks, Gemini Live replies in audio,
and that audio drives the SyncTalk avatar's mouth — all streamed through a LiveKit room.

> **This is a bigger deal than a code copy.** LearnQuest's plan (§6.3) specifies a *text*
> tutor with SSE streaming, and `context.md` lists "Voice conversation with the avatar"
> under **Future Enhancements**. That future is already built. See
> [Decision needed](#decision-needed) before wiring it into the app.

---

## How it fits together

```
Browser  ──join room──►  LiveKit  ◄──publishes audio+video──  agent_bangla.py
   │                                                              │   ▲
   │  token from                                        Gemini Live│   │ WS: PCM out,
   │  POST /token                                        (realtime)│   │ audio+jpg back
   ▼                                                              ▼   │
token_server.py                                          ../avatar-service (GPU)
```

The agent is a **LiveKit worker**: it joins the room, subscribes to the learner's mic,
sends speech to Gemini Live, pipes Gemini's audio to the avatar service, and publishes
the returned audio + video frames back into the room as tracks.

---

## Files

| File | What | Note |
| --- | --- | --- |
| `agent_bangla.py` | **the current agent, 1321 lines** | most up to date — start here |
| `agent_english.py` | earlier English version, 695 lines | predates the audio-master rewrite |
| `synctalk_agent.py` | earlier avatar agent, 542 lines | superseded, kept for reference |
| `token_server.py` | Flask app that mints LiveKit access tokens | should move into the FastAPI backend |
| `reference-client/playground.html` | **working browser client, 1102 lines** | the LiveKit + avatar playback logic to port into React |
| `reference-client/index.html` | earlier client | reference only |
| `requirements.txt` | livekit-agents, google + silero plugins | pin the same minor version |

Despite the filename, **`agent_bangla.py` is the one to build on** — the English file is
older and lacks the audio-master playback work below. Switching language is small:
set `INPUT_LANGUAGE=en-US` and rewrite `AGENT_INSTRUCTIONS` with the tutor persona.

---

## The hard-won parts (do not casually "simplify" these)

The file header and inline comments document real measurements. Worth reading before
changing anything:

- **Audio is the master clock; video slaves to it.** The GPU cannot always hold 25 FPS.
  If audio waits for video, every hiccup becomes an audible gap mid-sentence. Instead a
  late frame is skipped or the previous one held — a briefly frozen mouth beats broken
  speech.
- **Idle ↔ speech transitions share one base-frame walk.** The client tells the server
  where its idle loop is before an utterance; the server reports where the walk ended
  after it; the client resumes idle there, with a crossfade both ways. This is what stops
  the avatar visibly jumping when it starts or stops talking.
- **Model choice is deliberate:** the live-cascade line, *not* `gemini-2.5-flash-native-audio-*`.
  Native-audio reply latency grew 8s → 66s over five turns as session context accumulated.
- **Local Silero VAD, not Gemini server VAD.** Server VAD marked 1s utterances as speech
  for 8–11s and the delay compounded across turns; Silero commits in ~2s and stays flat.
  `LOCAL_VAD=0` falls back.
- **Transcription language is pinned.** Auto-detect garbled Bangla into Hindi or Roman
  script; comprehension was fine, the transcript was not.

---

## Running it

Needs the avatar service up first (see [../avatar-service](../avatar-service/README.md)).

```bash
cd agent && python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt
```

```bash
cp .env.example .env
```

Then, in three terminals:

```bash
cd avatar-service && ./run.ps1
```

```bash
cd agent && python token_server.py
```

```bash
cd agent && python agent_bangla.py dev
```

Open the token server's page to load `reference-client/playground.html`.

---

## Decision needed

LearnQuest currently scaffolds a **text** tutor: `POST /api/tutor/.../messages`, SSE
streaming, Tier A browser avatar. This agent is a **voice-first realtime** stack. They are
not the same architecture, and picking one changes plan.md §6.3.

**Recommended: keep both, text-first.**

- Text chat stays the default — it works with no GPU, no LiveKit, and no realtime API,
  which is what Members 2, 3 and 4 need to build against.
- Voice becomes a mode you switch into on the Tutor page, backed by this agent.
- The demo degrades cleanly: no GPU → Tier A text tutor; GPU up → voice avatar.

**What porting into LearnQuest actually requires:**

1. Move `token_server.py` into the FastAPI backend as `POST /api/livekit/token`,
   authenticated with the existing `CurrentUser` dependency. ~30 lines. Do not ship a
   separate unauthenticated Flask app — anyone could mint a room token.
2. Port `reference-client/playground.html` into a React component using
   `@livekit/components-react`. This is the bulk of the work.
3. Rewrite `AGENT_INSTRUCTIONS` as the LearnQuest tutor persona, and feed it lesson
   context and weak topics the same way `services/prompts.py` does for text.
4. Add LiveKit credentials to the team's account list.

**Not yet done** — none of the above is wired up. The code here runs standalone exactly
as it did in `Fydp_v2`.

---

## Not copied

`.env` files (secrets) and `venv/` were deliberately left behind. Get your own Gemini key
and LiveKit credentials, and build a fresh venv.
