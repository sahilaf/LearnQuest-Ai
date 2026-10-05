/**
 * useTeachBack - OWNER: Member 1. See services/teachback.py.
 *
 * Teach-Back state, shared by the two halves of the Teach tab: the challenge
 * (what Redwan believes, the question, attempts) beside the tutor, and the
 * conversation on the right.
 *
 * Rules this hook keeps:
 * - Redwan speaks each line once. Lines are keyed by their timestamp, so a
 *   retake or a reload never makes him repeat himself.
 * - Arriving from a quiz link auto-starts that topic once, not again after
 *   "Teach something else".
 * - Pass and fail are distinct outcomes; nothing here guesses one from the other.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { novaRetake, startTeachBack, teachBackAvailable, teachNova } from '../../api/tutor';

export const TEACH_PHASE = {
  IDLE: null,
  STARTING: 'starting',
  REPLYING: 'replying',
  RETAKING: 'retaking',
};

export default function useTeachBack({ initialTopic = null, speak = null }) {
  const [available, setAvailable] = useState([]);
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState(null);
  const [draft, setDraft] = useState('');
  const [phase, setPhase] = useState(TEACH_PHASE.IDLE);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const speakRef = useRef(speak);
  speakRef.current = speak;
  const spokenRef = useRef(new Set());
  const autoStartedRef = useRef(false);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    teachBackAvailable()
      .then((data) => setAvailable(data.items || []))
      .catch((err) => setError(err?.detail || 'Could not load what you can teach.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(refresh, [refresh]);

  /** Say Redwan's lines that have not been said yet - never one twice. */
  const speakNewLines = useCallback((nextSession, { silently = false } = {}) => {
    const fresh = (nextSession?.turns || []).filter(
      (t) => t.role === 'nova' && !spokenRef.current.has(t.at),
    );
    fresh.forEach((t) => spokenRef.current.add(t.at));
    const last = fresh[fresh.length - 1];
    if (last && !silently) speakRef.current?.(last.content);
  }, []);

  const begin = useCallback((topicTag) => {
    setPhase(TEACH_PHASE.STARTING);
    setError(null);
    setResult(null);
    startTeachBack(topicTag)
      .then((s) => {
        // A resumed session's opening was already heard; a new one is spoken.
        const resumed = (s.turns || []).length > 1;
        speakNewLines(s, { silently: resumed });
        setSession(s);
      })
      .catch((err) => setError(err?.detail || 'Could not start Teach-Back.'))
      .finally(() => setPhase(TEACH_PHASE.IDLE));
  }, [speakNewLines]);

  useEffect(() => {
    if (!initialTopic || autoStartedRef.current || loading) return;
    if (available.some((item) => item.topic_tag === initialTopic)) {
      autoStartedRef.current = true;
      begin(initialTopic);
    }
  }, [initialTopic, loading, available, begin]);

  const send = useCallback(() => {
    const message = draft.trim();
    if (!message || !session || phase) return;
    setPhase(TEACH_PHASE.REPLYING);
    setError(null);
    setDraft('');
    teachNova(session.id, message)
      .then((data) => {
        speakNewLines(data.session);
        setSession(data.session);
      })
      .catch((err) => {
        setError(err?.detail || 'Redwan could not reply. Try again.');
        setDraft(message); // never silently eat what they typed
      })
      .finally(() => setPhase(TEACH_PHASE.IDLE));
  }, [draft, session, phase, speakNewLines]);

  const retake = useCallback(() => {
    if (!session || phase) return;
    setPhase(TEACH_PHASE.RETAKING);
    setError(null);
    novaRetake(session.id)
      .then((data) => {
        setResult(data);
        // The retake adds no new line to the conversation, so nothing is
        // re-spoken; Redwan says his answer instead.
        speakNewLines(data.session, { silently: true });
        setSession(data.session);
        if (data.nova_answer) speakRef.current?.(`My answer is: ${data.nova_answer}`);
        if (data.passed) refresh();
      })
      .catch((err) => setError(err?.detail || 'Redwan could not take the question. Try again.'))
      .finally(() => setPhase(TEACH_PHASE.IDLE));
  }, [session, phase, refresh, speakNewLines]);

  /** Back to the list of things to teach. */
  const leave = useCallback(() => {
    setSession(null);
    setResult(null);
    setError(null);
    setDraft('');
    refresh();
  }, [refresh]);

  /** After running out of attempts: a fresh session on the same belief. */
  const tryAgain = useCallback(() => {
    if (!session) return;
    begin(session.topic_tag);
  }, [session, begin]);

  const turns = session?.turns || [];
  const maxRetakes = session?.max_retakes ?? 3;
  return {
    available,
    loading,
    session,
    draft,
    setDraft,
    phase,
    busy: Boolean(phase),
    result,
    error,
    hasTaught: turns.some((t) => t.role === 'student'),
    passed: session?.status === 'passed',
    failed: session?.status === 'failed',
    attemptsUsed: session?.retakes ?? 0,
    maxRetakes,
    refresh,
    begin,
    send,
    retake,
    leave,
    tryAgain,
  };
}
