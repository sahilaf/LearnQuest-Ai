/**
 * TeachBackPanel - OWNER: Member 1. See plan.md §6.10 and services/teachback.py.
 *
 * The protege effect, on screen. Nova is seeded with a false belief this student
 * actually holds, argues from it, and then re-takes the question they got wrong.
 * Her score is their grade.
 *
 * Two deliberate interaction choices:
 *
 * - The correct answer is never shown while the session is winnable. The backend
 *   withholds it too; this component only renders what it is given. Showing it
 *   would turn teaching into copying.
 * - "Ask Nova to try again" stays enabled even when she is not convinced. Being
 *   convinced is her opinion; the retake is the measurement, and a student is
 *   allowed to disagree with her and be proved right.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { GraduationCap, Lightbulb, RotateCcw, Send, Trophy } from 'lucide-react';

import { Badge, Button, EmptyState, Spinner } from '../../components/ui';
import {
  novaRetake,
  startTeachBack,
  teachBackAvailable,
  teachNova,
} from '../../api/tutor';

const STATUS_TONE = { active: 'hard', fading: 'medium', cleared: 'success' };

function TurnBubble({ turn }) {
  const isNova = turn.role === 'nova';
  return (
    <div className={`flex ${isNova ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
          isNova
            ? 'bg-canvas text-body'
            : 'bg-primary-600 text-white'
        }`}
      >
        {isNova && (
          <span className="mb-0.5 block text-[11px] font-semibold uppercase tracking-wide text-muted">
            Nova
          </span>
        )}
        {turn.content}
      </div>
    </div>
  );
}

export default function TeachBackPanel({ onNovaSpeak = null }) {
  const [available, setAvailable] = useState([]);
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const turnsEndRef = useRef(null);
  // Held in a ref so a new callback identity from the parent cannot retrigger
  // the speak effect and make Nova repeat her last line.
  const onNovaSpeakRef = useRef(onNovaSpeak);
  useEffect(() => {
    onNovaSpeakRef.current = onNovaSpeak;
  }, [onNovaSpeak]);

  const loadAvailable = useCallback(() => {
    setLoading(true);
    teachBackAvailable()
      .then((data) => setAvailable(data.items || []))
      .catch((err) => setError(err?.detail || 'Could not load your misconceptions.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(loadAvailable, [loadAvailable]);

  useEffect(() => {
    turnsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.turns?.length]);

  // Speak whatever Nova said last, so the avatar says it too.
  useEffect(() => {
    const turns = session?.turns || [];
    const last = turns[turns.length - 1];
    if (last?.role === 'nova') onNovaSpeakRef.current?.(last.content);
  }, [session]);

  const begin = useCallback((topicTag) => {
    setBusy(true);
    setError(null);
    setResult(null);
    startTeachBack(topicTag)
      .then(setSession)
      .catch((err) => setError(err?.detail || 'Could not start a Teach-Back session.'))
      .finally(() => setBusy(false));
  }, []);

  const send = useCallback(() => {
    const message = draft.trim();
    if (!message || !session || busy) return;
    setBusy(true);
    setError(null);
    setDraft('');
    teachNova(session.id, message)
      .then((data) => setSession(data.session))
      .catch((err) => {
        setError(err?.detail || 'Nova could not reply.');
        setDraft(message); // never silently eat what they typed
      })
      .finally(() => setBusy(false));
  }, [draft, session, busy]);

  const retake = useCallback(() => {
    if (!session || busy) return;
    setBusy(true);
    setError(null);
    novaRetake(session.id)
      .then((data) => {
        setResult(data);
        setSession(data.session);
        if (data.passed) loadAvailable();
      })
      .catch((err) => setError(err?.detail || 'Nova could not take the question.'))
      .finally(() => setBusy(false));
  }, [session, busy, loadAvailable]);

  const reset = useCallback(() => {
    setSession(null);
    setResult(null);
    setError(null);
    setDraft('');
    loadAvailable();
  }, [loadAvailable]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }

  /* ---- Nothing to teach yet ---- */
  if (!session && available.length === 0) {
    return (
      <div className="p-4">
        <EmptyState
          icon={<Lightbulb className="h-5 w-5" />}
          title="Nothing to teach yet"
          description={
            'Teach-Back starts from a misconception. Take a quiz and get something '
            + 'wrong, and the tutor will name the belief behind it - then you can '
            + 'teach Nova out of it.'
          }
          action={
            <Button variant="secondary" size="sm" onClick={loadAvailable}>
              Check again
            </Button>
          }
        />
        {error && <p className="mt-3 text-center text-sm text-hard">{error}</p>}
      </div>
    );
  }

  /* ---- Pick something to teach ---- */
  if (!session) {
    return (
      <div className="space-y-3 p-4">
        <div>
          <h3 className="text-sm font-semibold">Teach Nova</h3>
          <p className="mt-0.5 text-sm text-muted">
            She believes what you believed. Talk her out of it, then watch her
            re-take the question you got wrong.
          </p>
        </div>

        <ul className="space-y-2">
          {available.map((item) => (
            <li key={item.topic_tag} className="card p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-muted">{item.topic_tag}</span>
                    <Badge tone={STATUS_TONE[item.status] || 'default'}>{item.status}</Badge>
                  </div>
                  <p className="mt-1 text-sm">{item.misconception}</p>
                </div>
                <Button size="sm" onClick={() => begin(item.topic_tag)} disabled={busy}>
                  Teach
                </Button>
              </div>
            </li>
          ))}
        </ul>

        {error && <p className="text-sm text-hard">{error}</p>}
      </div>
    );
  }

  /* ---- In session ---- */
  const closed = session.status === 'passed' || session.status === 'failed';
  const hasTaught = (session.turns || []).some((t) => t.role === 'student');

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <GraduationCap className="h-4 w-4 text-primary-600" />
          <span className="text-sm font-semibold">Teaching Nova</span>
          <span className="font-mono text-xs text-muted">{session.topic_tag}</span>
        </div>
        <p className="mt-1.5 text-sm text-muted">
          <span className="font-medium text-body">She believes:</span>{' '}
          {session.misconception}
        </p>
        <p className="mt-1 text-sm text-muted">
          <span className="font-medium text-body">Her question:</span>{' '}
          {session.question_prompt}
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">
        {(session.turns || []).map((turn, index) => (
          <TurnBubble key={`${turn.at}-${index}`} turn={turn} />
        ))}
        <div ref={turnsEndRef} />
      </div>

      {result && (
        <div
          className={`border-t px-4 py-3 text-sm ${
            result.passed
              ? 'border-easy/30 bg-easy-bg'
              : 'border-hard/30 bg-hard-bg'
          }`}
        >
          <div className="flex items-center gap-2 font-semibold">
            {result.passed ? <Trophy className="h-4 w-4" /> : <RotateCcw className="h-4 w-4" />}
            {result.passed ? 'Nova got it right' : 'Nova still got it wrong'}
            <Badge tone={result.passed ? 'success' : 'hard'}>{result.score}/100</Badge>
            {result.xp_awarded > 0 && <Badge tone="primary">+{result.xp_awarded} XP</Badge>}
          </div>
          <p className="mt-1.5">
            <span className="text-muted">She answered:</span> {result.nova_answer}
          </p>
          {result.why && <p className="mt-0.5 text-muted">{result.why}</p>}
          {result.correct_answer && (
            <p className="mt-0.5">
              <span className="text-muted">Correct answer:</span> {result.correct_answer}
            </p>
          )}
          {!result.passed && !closed && (
            <p className="mt-1 text-muted">
              {result.retakes_left} attempt{result.retakes_left === 1 ? '' : 's'} left - explain
              the part she is still missing.
            </p>
          )}
        </div>
      )}

      {error && <p className="px-4 pb-2 text-sm text-hard">{error}</p>}

      <div className="border-t border-line p-3">
        {closed ? (
          <Button variant="secondary" size="sm" onClick={reset} className="w-full">
            Teach something else
          </Button>
        ) : (
          <>
            <div className="flex items-end gap-2">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    send();
                  }
                }}
                rows={2}
                disabled={busy}
                placeholder="Explain why what she believes is wrong..."
                className="field min-h-[56px] flex-1 resize-none"
              />
              <Button size="sm" onClick={send} disabled={busy || !draft.trim()}>
                <Send className="h-3.5 w-3.5" />
              </Button>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={retake}
              disabled={busy || !hasTaught}
              loading={busy}
              className="mt-2 w-full"
            >
              Ask Nova to re-take the question
            </Button>
            {!hasTaught && (
              <p className="mt-1.5 text-center text-xs text-muted">
                Teach her something first - her score is your grade.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
