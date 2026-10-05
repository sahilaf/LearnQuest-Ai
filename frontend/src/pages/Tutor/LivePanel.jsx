/**
 * LivePanel - OWNER: Member 1.
 *
 * The Live tab: talk to Redwan out loud. Nothing happens until the student
 * presses Start - no microphone prompt, no connection, no sound on page load.
 *
 * In a call the panel always answers "whose turn is it?": the status chip at
 * the top, a thinking bubble while the answer is coming, and the reply's text
 * filling in as Redwan says it.
 */
import { useEffect, useRef, useState } from 'react';
import { Hand, Mic, MicOff, PhoneOff, Radio, Send } from 'lucide-react';

import { LIVE_STATUS } from './useLiveConversation';
import { LiveStatusChip, TalkBars, ThinkingDots, liveStateOf } from './LiveStatus';

function Bubble({ role, children }) {
  const mine = role === 'user';
  return (
    <div className={`flex flex-col ${mine ? 'items-end' : 'items-start'}`}>
      <span className="mb-1 px-1 text-2xs font-medium text-faint">{mine ? 'You' : 'Redwan'}</span>
      <div
        className={`max-w-[85%] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed ${
          mine ? 'rounded-tr-sm bg-primary-600 text-white' : 'rounded-tl-sm border border-line bg-raised text-body'
        }`}
      >
        {children}
      </div>
    </div>
  );
}

export default function LivePanel({ live, conversationTitle, lessonTitle, avatarLive, onStart }) {
  const [draft, setDraft] = useState('');
  const endRef = useRef(null);
  const state = liveStateOf(live);

  const last = live.turns[live.turns.length - 1];
  // The answer is coming but has no words yet: show that rather than nothing.
  const showThinking = state === 'thinking' && last?.role !== 'tutor';
  const showVoicePlaceholder = state === 'speaking' && last?.role !== 'tutor';

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [live.turns, showThinking, showVoicePlaceholder]);

  const inCall = live.status === LIVE_STATUS.LIVE;
  const connecting = live.status === LIVE_STATUS.CONNECTING;

  /* ---- Not in a call: one clear action ---- */
  if (!inCall && !connecting) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-pill border border-primary-500/40 bg-primary-500/10 text-primary-300">
          <Radio className="h-6 w-6" />
        </span>
        <h2 className="mt-4 text-xl font-semibold text-ink">Talk with Redwan</h2>
        <p className="mt-1.5 max-w-sm text-sm text-muted">
          A spoken conversation, like a call. Ask anything about what you are
          learning - Redwan knows your lessons, what you find hard, and what you
          have already talked about.
        </p>

        <ol className="mt-5 grid max-w-md gap-2 text-left text-sm text-body sm:grid-cols-3">
          {[
            ['1', 'Press Start', 'Allow the microphone once.'],
            ['2', 'Talk', 'When it says "Your turn".'],
            ['3', 'Listen', 'Your words and his reply appear as text.'],
          ].map(([n, title, text]) => (
            <li key={n} className="rounded border border-line bg-raised/60 p-2.5">
              <span className="text-2xs font-semibold text-primary-300">{n}</span>
              <p className="font-medium text-ink">{title}</p>
              <p className="text-xs text-muted">{text}</p>
            </li>
          ))}
        </ol>

        <p className="mt-4 text-xs text-faint">
          Continues: <span className="text-body">{conversationTitle || 'a new conversation'}</span>
          {lessonTitle && <> · Lesson: <span className="text-body">{lessonTitle}</span></>}
          {' · '}
          {avatarLive ? 'speaks through the avatar' : 'voice only'}
        </p>

        {live.status === LIVE_STATUS.ERROR && live.error && (
          <p className="mt-4 max-w-sm rounded border border-hard/40 bg-hard/10 px-3 py-2 text-sm text-hard-fg">
            {live.error}
          </p>
        )}

        <button
          type="button"
          onClick={onStart}
          className="mt-6 inline-flex items-center gap-2 rounded bg-primary-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-500"
        >
          <Mic className="h-4 w-4" />
          {live.status === LIVE_STATUS.ERROR ? 'Try again' : 'Start conversation'}
        </button>
        <p className="mt-2 text-2xs text-faint">Headphones work best.</p>
        <p className="mt-3 max-w-sm text-2xs leading-relaxed text-faint">
          Privacy: while the call is on, your voice is sent to Google Gemini to be
          understood and answered. The text of the conversation is saved to this
          chat so Redwan remembers it; delete the conversation in Chat to remove it.
          LearnQuest does not keep the audio.
        </p>
      </div>
    );
  }

  /* ---- In a call ---- */
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3" role="status">
        <LiveStatusChip state={state} level={live.level} withHint />
        <span className="min-w-0 truncate text-2xs text-faint">{conversationTitle}</span>
      </div>

      {/* aria-live: a screen reader announces each new line as it arrives,
          so the conversation is followable without seeing it. */}
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite" aria-label="Conversation transcript">
        {live.turns.length === 0 && !connecting && !showThinking && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <p className="text-sm font-medium text-ink">Redwan is listening.</p>
            <p className="mt-1 text-sm text-muted">Say hello, or ask about something you are working on.</p>
          </div>
        )}
        {connecting && (
          <div className="flex h-full items-center justify-center gap-2 text-sm text-muted">
            <ThinkingDots className="bg-muted" /> Connecting to Redwan
          </div>
        )}

        {live.turns.map((turn) => (
          <Bubble key={turn.id} role={turn.role}>{turn.text}</Bubble>
        ))}

        {showThinking && (
          <Bubble role="tutor">
            <span className="flex items-center gap-2 text-muted"><ThinkingDots /> thinking</span>
          </Bubble>
        )}
        {showVoicePlaceholder && (
          <Bubble role="tutor">
            <span className="flex items-center gap-2 text-muted"><TalkBars /> speaking</span>
          </Bubble>
        )}
        <div ref={endRef} />
      </div>

      <div className="space-y-2.5 border-t border-line p-3">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            live.sendText(draft);
            setDraft('');
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Prefer typing? Write here and press Enter"
            disabled={!inCall}
            className="min-w-0 flex-1 rounded border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-faint focus:border-primary-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!inCall || !draft.trim()}
            className="rounded border border-line px-3 text-muted transition-colors hover:text-ink disabled:opacity-40"
            title="Send"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => live.setMicMuted(!live.micMuted)}
            disabled={!inCall}
            className={`inline-flex items-center gap-1.5 rounded border px-3 py-2 text-sm transition-colors disabled:opacity-40 ${
              live.micMuted ? 'border-hard/50 text-hard-fg' : 'border-line text-body hover:text-ink'
            }`}
          >
            {live.micMuted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            {live.micMuted ? 'Unmute mic' : 'Mute mic'}
          </button>
          <button
            type="button"
            onClick={live.interrupt}
            disabled={state !== 'speaking'}
            className="inline-flex items-center gap-1.5 rounded border border-line px-3 py-2 text-sm text-body transition-colors hover:text-ink disabled:opacity-40"
            title="Stop Redwan and take your turn"
          >
            <Hand className="h-4 w-4" />
            Stop talking
          </button>
          <button
            type="button"
            onClick={live.stop}
            className="ml-auto inline-flex items-center gap-1.5 rounded bg-hard/90 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-hard"
          >
            <PhoneOff className="h-4 w-4" />
            End call
          </button>
        </div>
      </div>
    </div>
  );
}
