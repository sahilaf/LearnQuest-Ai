/**
 * Teach-Back on screen - OWNER: Member 1. See plan.md §6.10, services/teachback.py.
 *
 * The protege effect: Redwan holds a false belief this student actually had,
 * argues from it, then re-takes the question they got wrong. His score is
 * their grade. State lives in useTeachBack; this file draws it in two parts:
 *
 *   TeachChallenge     beside the tutor - what he believes, the question he
 *                      will re-take (with its options), attempts left
 *   TeachConversation  the main panel - choosing a belief, the conversation,
 *                      the retake result and the outcome
 *
 * The correct answer is never shown while the session is winnable (the
 * backend withholds it too). Asking for a retake stays available even when
 * Redwan is not convinced: being convinced is his opinion, the retake is the
 * measurement.
 */
import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, Lightbulb, RotateCcw, Send, Trophy, XCircle } from 'lucide-react';

import { Badge, Button, EmptyState, Spinner, buttonClasses } from '../../components/ui';
import { ThinkingDots } from './LiveStatus';
import { TEACH_PHASE } from './useTeachBack';

const STATUS_TONE = { active: 'hard', fading: 'medium', cleared: 'success' };

/** "You believe X" reads as Redwan's belief once he has taken it on. */
const asHisBelief = (text = '') => text.replace(/^You believe\b/i, 'He believes');

/* ------------------------------------------------------------------------ */
/* Beside the tutor                                                          */
/* ------------------------------------------------------------------------ */

export function TeachChallenge({ teach }) {
  const { session, attemptsUsed, maxRetakes, passed, failed } = teach;

  if (!session) {
    return (
      <div className="card p-4">
        <span className="label">How it works</span>
        <ol className="mt-3 space-y-2.5 text-sm text-body">
          {[
            'Redwan takes on a belief behind one of your wrong answers.',
            'Explain why it is wrong - he pushes back on vague answers.',
            'He re-takes your question. His score is your grade.',
          ].map((line, i) => (
            <li key={line} className="flex gap-2.5">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-pill bg-raised text-2xs font-semibold text-muted">
                {i + 1}
              </span>
              {line}
            </li>
          ))}
        </ol>
      </div>
    );
  }

  const options = Array.isArray(session.question_options) ? session.question_options : [];
  const left = Math.max(0, maxRetakes - attemptsUsed);
  return (
    <div className="card divide-y divide-line">
      <div className="p-4">
        <span className="label">What he believes</span>
        <p className="mt-1.5 text-base font-medium leading-snug text-ink">
          {asHisBelief(session.misconception)}
        </p>
        <p className="mt-1 text-2xs text-faint">{session.topic_tag}</p>
      </div>
      <div className="p-4">
        <span className="label">The question he will re-take</span>
        <p className="mt-1.5 text-sm leading-relaxed text-body">{session.question_prompt}</p>
        {options.length > 0 && (
          <ul className="mt-2.5 space-y-1.5">
            {options.map((option) => (
              <li key={option} className="rounded border border-line bg-raised px-2.5 py-1.5 text-sm text-body">
                {option}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex items-center justify-between gap-3 p-4">
        <span className="label">Attempts</span>
        <span className="flex items-center gap-2 text-sm text-muted">
          <span className="flex gap-1" aria-hidden>
            {Array.from({ length: maxRetakes }, (_, i) => (
              <span
                key={i}
                className={`h-2 w-5 rounded-pill ${i < attemptsUsed ? 'bg-muted' : 'bg-line-strong'}`}
              />
            ))}
          </span>
          {passed && 'Passed'}
          {failed && 'None left'}
          {!passed && !failed && `${left} of ${maxRetakes} left`}
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------ */
/* The main panel                                                            */
/* ------------------------------------------------------------------------ */

function Bubble({ role, children }) {
  const mine = role === 'student';
  return (
    <div className={`flex flex-col ${mine ? 'items-end' : 'items-start'}`}>
      <span className="mb-1 px-1 text-2xs font-medium text-faint">{mine ? 'You' : 'Redwan'}</span>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3.5 py-2.5 text-sm leading-relaxed ${
          mine ? 'rounded-tr-sm bg-primary-600 text-white' : 'rounded-tl-sm border border-line bg-raised text-body'
        }`}
      >
        {children}
      </div>
    </div>
  );
}

/** One retake, drawn where it happened in the conversation. */
function RetakeResult({ result }) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        result.passed ? 'border-easy/40 bg-easy-bg' : 'border-hard/40 bg-hard-bg'
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        {result.passed ? <CheckCircle2 className="h-4 w-4 text-easy-fg" /> : <XCircle className="h-4 w-4 text-hard-fg" />}
        <span className={`text-sm font-semibold ${result.passed ? 'text-easy-fg' : 'text-hard-fg'}`}>
          {result.passed ? 'Redwan got it right' : 'Redwan still got it wrong'}
        </span>
        <Badge tone={result.passed ? 'success' : 'hard'}>{result.score}/100</Badge>
        {result.xp_awarded > 0 && <Badge tone="primary">+{result.xp_awarded} XP</Badge>}
      </div>
      <p className="mt-2 text-sm text-body">
        <span className="text-muted">He answered: </span>{result.nova_answer || 'nothing'}
      </p>
      {result.why && <p className="mt-0.5 text-sm text-muted">{result.why}</p>}
    </div>
  );
}

function Outcome({ teach }) {
  const { passed, result, session } = teach;
  const correct = result?.correct_answer || session?.question_correct_answer;

  if (passed) {
    return (
      <div className="space-y-3 p-4">
        <div className="flex items-start gap-3 rounded-lg border border-easy/40 bg-easy-bg p-4">
          <Trophy className="mt-0.5 h-5 w-5 shrink-0 text-easy-fg" />
          <div>
            <p className="font-semibold text-easy-fg">You taught him - misconception fixed</p>
            <p className="mt-0.5 text-sm text-body">
              It moves to fading, and comes back for review so it stays fixed.
            </p>
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button variant="secondary" className="flex-1" onClick={teach.leave}>Teach something else</Button>
          <Link to="/dashboard" className={buttonClasses('primary', 'md', 'flex-1')}>Continue learning</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-start gap-3 rounded-lg border border-hard/40 bg-hard-bg p-4">
        <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-hard-fg" />
        <div>
          <p className="font-semibold text-hard-fg">Out of attempts - the belief is still there</p>
          {correct && (
            <p className="mt-1 text-sm text-body">
              <span className="text-muted">The correct answer: </span>{correct}
            </p>
          )}
          <p className="mt-1 text-sm text-muted">
            Explain the mechanism - why his belief leads to the wrong answer - not just what the
            right answer is.
          </p>
        </div>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button variant="secondary" className="flex-1" onClick={teach.leave}>Teach something else</Button>
        <Button className="flex-1" onClick={teach.tryAgain} loading={teach.phase === TEACH_PHASE.STARTING}>
          <RotateCcw className="h-4 w-4" />
          Try again
        </Button>
      </div>
    </div>
  );
}

function ChooseBelief({ teach }) {
  const { available, loading, error, busy } = teach;

  if (loading) {
    return <div className="flex h-full items-center justify-center"><Spinner /></div>;
  }
  if (available.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState
          icon={<Lightbulb className="h-5 w-5" />}
          title="Nothing to teach yet"
          description="Teach-Back starts from a mistake. Take a quiz - when you get something wrong, the belief behind it shows up here."
          action={<Button variant="secondary" size="sm" onClick={teach.refresh}>Check again</Button>}
        />
        {error && <p className="mt-3 text-center text-sm text-hard-fg">{error}</p>}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-5 py-4">
        <h2 className="text-base font-semibold text-ink">Choose a belief to teach</h2>
        <p className="mt-0.5 text-sm text-muted">Each one came from a wrong answer of yours.</p>
      </div>
      <ul className="min-h-0 flex-1 space-y-3 overflow-y-auto p-5">
        {available.map((item) => (
          <li key={item.topic_tag} className="card flex items-start justify-between gap-4 p-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-2xs text-faint">{item.topic_tag}</span>
                <Badge tone={STATUS_TONE[item.status] || 'default'}>{item.status}</Badge>
              </div>
              <p className="mt-1.5 text-sm text-body">{item.misconception}</p>
            </div>
            <Button size="sm" onClick={() => teach.begin(item.topic_tag)} disabled={busy}>
              Teach
            </Button>
          </li>
        ))}
      </ul>
      {error && <p className="px-5 pb-3 text-sm text-hard-fg">{error}</p>}
    </div>
  );
}

export function TeachConversation({ teach }) {
  const endRef = useRef(null);
  const { session, phase, result, error, hasTaught, draft } = teach;
  const turns = session?.turns || [];

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns.length, phase, result]);

  if (!session) {
    if (phase === TEACH_PHASE.STARTING) {
      return (
        <div className="flex h-full items-center justify-center gap-2 text-sm text-muted">
          <ThinkingDots /> Redwan is getting ready
        </div>
      );
    }
    return <ChooseBelief teach={teach} />;
  }

  const closed = teach.passed || teach.failed;
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <button
          type="button"
          onClick={teach.leave}
          className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-ink"
        >
          <ArrowLeft className="h-4 w-4" />
          All beliefs
        </button>
        <span className="text-sm font-medium text-ink">Teaching Redwan</span>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
        {turns.map((turn, index) => (
          <Bubble key={`${turn.at}-${index}`} role={turn.role}>{turn.content}</Bubble>
        ))}
        {phase === TEACH_PHASE.REPLYING && (
          <Bubble role="nova"><span className="flex items-center gap-2 text-muted"><ThinkingDots /> thinking</span></Bubble>
        )}
        {phase === TEACH_PHASE.RETAKING && (
          <div className="flex items-center justify-center gap-2 py-2 text-sm text-muted">
            <ThinkingDots /> Redwan is re-taking the question
          </div>
        )}
        {result && <RetakeResult result={result} />}
        <div ref={endRef} />
      </div>

      {error && <p className="px-4 pb-2 text-sm text-hard-fg">{error}</p>}

      <div className="border-t border-line">
        {closed ? (
          <Outcome teach={teach} />
        ) : (
          <div className="space-y-2.5 p-4">
            <div className="flex items-end gap-2">
              <textarea
                value={draft}
                onChange={(e) => teach.setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    teach.send();
                  }
                }}
                rows={2}
                disabled={teach.busy}
                placeholder="Explain why what he believes is wrong..."
                className="field min-h-[60px] flex-1 resize-none"
                aria-label="Your explanation"
              />
              <Button onClick={teach.send} disabled={teach.busy || !draft.trim()} aria-label="Send explanation">
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted">
                {hasTaught
                  ? 'When you think he understands, ask him to re-take the question.'
                  : 'Teach him something first - his score is your grade.'}
              </p>
              <Button
                variant="secondary"
                size="sm"
                onClick={teach.retake}
                disabled={teach.busy || !hasTaught}
              >
                Ask Redwan to re-take the question
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
