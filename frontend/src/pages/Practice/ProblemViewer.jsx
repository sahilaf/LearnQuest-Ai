/**
 * ProblemViewer - OWNER: Member 2 (Learning Management).
 * See CHECKLIST.md Week 3 Slot 10 & docs/DESIGN_GUIDELINES.md.
 *
 * Information-dense problem solving interface:
 * - Markdown problem statement, constraints, input/output specifications
 * - Code/query editor with monospaced styling
 * - Automated test case runner with per-case pass/fail feedback
 * - "Skill verified" indicator upon meeting domain threshold
 * - Clean mobile responsive single-column layout on small screens
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  Code2,
  RotateCcw,
  Trophy,
  XCircle,
} from 'lucide-react';

import {
  Badge,
  Button,
  Card,
  EmptyState,
  Spinner,
} from '../../components/ui';
import { getProblem, submitProblem } from '../../api/practice';

function getDifficultyTone(difficulty) {
  switch (difficulty?.toLowerCase()) {
    case 'easy':
      return 'easy';
    case 'medium':
      return 'warning';
    case 'hard':
      return 'danger';
    default:
      return 'default';
  }
}

export default function ProblemViewer() {
  const { problemId } = useParams();

  const [problem, setProblem] = useState(null);
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Result of latest submission
  const [attemptResult, setAttemptResult] = useState(null);
  const [activeTestCaseTab, setActiveTestCaseTab] = useState(0);

  const loadProblemData = useCallback(async () => {
    if (!problemId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getProblem(problemId);
      setProblem(data);
      setCode(data.starter_code || '');
    } catch (err) {
      console.error('Failed to load problem:', err);
      setError(err?.detail || 'Problem could not be loaded. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [problemId]);

  useEffect(() => {
    loadProblemData();
  }, [loadProblemData]);

  const handleSubmit = async () => {
    if (!problemId || submitting) return;
    setSubmitting(true);
    setError(null);

    try {
      const res = await submitProblem(problemId, { code });
      setAttemptResult(res);
      // Auto-switch to test case tab 0
      setActiveTestCaseTab(0);
    } catch (err) {
      console.error('Submission failed:', err);
      setError(err?.detail || 'Submission evaluation failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <p className="text-sm text-muted">Loading problem statement and test cases...</p>
      </div>
    );
  }

  if (error && !problem) {
    return (
      <div className="space-y-4">
        <Link to="/practice" className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-ink">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Practice Problems
        </Link>
        <EmptyState
          title="Problem Not Found"
          description={error}
          action={
            <Button variant="secondary" onClick={loadProblemData}>
              Retry
            </Button>
          }
        />
      </div>
    );
  }

  const allPassed = attemptResult?.all_passed;
  const isSkillVerified = attemptResult?.skill_verified;

  return (
    <div className="space-y-6 pb-12">
      {/* Top Breadcrumb & Metadata Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
        <div className="space-y-1">
          <Link
            to="/practice"
            className="inline-flex items-center gap-1 text-xs text-muted transition-colors hover:text-body"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Practice
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-ink sm:text-2xl">
              {problem.title}
            </h1>
            <Badge tone={getDifficultyTone(problem.difficulty)} className="text-xs">
              {problem.difficulty}
            </Badge>
            {problem.skill_name && (
              <Badge tone="default" className="text-xs">
                {problem.skill_name}
              </Badge>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {attemptResult && (
            <Badge tone={allPassed ? 'easy' : 'danger'}>
              {allPassed ? 'Accepted' : 'Failed Tests'}
            </Badge>
          )}
        </div>
      </div>

      {/* Skill Verified Celebration Banner */}
      {isSkillVerified && (
        <div className="animate-fade-in rounded-lg border border-easy/40 bg-easy-bg p-4 text-easy-fg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-easy text-canvas">
              <Trophy className="h-5 w-5" />
            </span>
            <div>
              <h3 className="text-sm font-bold">Skill Verified!</h3>
              <p className="text-xs">
                You have passed the required problems to verify your competence in <strong>{problem.skill_name}</strong>.
              </p>
            </div>
          </div>
          <Link to="/practice">
            <Button variant="secondary" size="sm" className="whitespace-nowrap">
              Explore More Skills →
            </Button>
          </Link>
        </div>
      )}

      {/* 2-Column Split: Statement (Left) vs Solution/Test Runner (Right) */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Column: Problem Statement & Specs (7 cols) */}
        <div className="space-y-6 lg:col-span-7">
          <Card className="p-5 sm:p-6 space-y-5">
            {/* Description */}
            <div>
              <span className="label text-muted">Problem Statement</span>
              <div className="mt-2 text-sm leading-relaxed text-body prose max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {problem.statement_md}
                </ReactMarkdown>
              </div>
            </div>

            {/* Input & Output Format */}
            {problem.input_format && (
              <div className="border-t border-line pt-4">
                <span className="label text-muted">Input Format</span>
                <p className="mt-1 text-xs text-body whitespace-pre-line font-mono bg-canvas p-2.5 rounded border border-line">
                  {problem.input_format}
                </p>
              </div>
            )}

            {problem.output_format && (
              <div className="border-t border-line pt-4">
                <span className="label text-muted">Output Format</span>
                <p className="mt-1 text-xs text-body whitespace-pre-line font-mono bg-canvas p-2.5 rounded border border-line">
                  {problem.output_format}
                </p>
              </div>
            )}

            {/* Constraints */}
            {problem.constraints && problem.constraints.length > 0 && (
              <div className="border-t border-line pt-4">
                <span className="label text-muted">Constraints</span>
                <ul className="mt-1.5 list-disc list-inside space-y-1 text-xs text-muted font-mono">
                  {problem.constraints.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Examples */}
            {problem.examples && problem.examples.length > 0 && (
              <div className="border-t border-line pt-4 space-y-3">
                <span className="label text-muted">Examples</span>
                {problem.examples.map((ex, idx) => (
                  <div key={idx} className="rounded border border-line bg-canvas p-3 text-xs space-y-2">
                    <div>
                      <span className="text-2xs uppercase tracking-wide font-semibold text-muted">Sample Input</span>
                      <pre className="mt-1 font-mono text-body overflow-x-auto whitespace-pre p-2 bg-raised rounded">
                        {ex.input}
                      </pre>
                    </div>
                    <div>
                      <span className="text-2xs uppercase tracking-wide font-semibold text-muted">Sample Output</span>
                      <pre className="mt-1 font-mono text-body overflow-x-auto whitespace-pre p-2 bg-raised rounded">
                        {ex.output}
                      </pre>
                    </div>
                    {ex.explanation && (
                      <p className="text-2xs text-muted italic">
                        <strong>Explanation:</strong> {ex.explanation}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right Column: Code Editor & Test Case Evaluation (5 cols) */}
        <div className="space-y-6 lg:col-span-5">
          {/* Solution Editor Card */}
          <Card className="p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-line pb-2.5">
              <div className="flex items-center gap-1.5">
                <Code2 className="h-4 w-4 text-primary-600" />
                <span className="text-xs font-bold text-ink">Solution Editor</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCode(problem.starter_code || '')}
                className="text-2xs text-muted hover:text-body h-7 px-2"
                title="Reset starter template"
              >
                <RotateCcw className="h-3 w-3 mr-1" /> Reset
              </Button>
            </div>

            <div>
              <textarea
                rows={12}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Write your code or query here..."
                className="field w-full font-mono text-xs leading-relaxed resize-y bg-canvas text-ink p-3"
                spellCheck="false"
              />
            </div>

            {error && (
              <div className="rounded border border-hard/40 bg-hard-bg p-2.5 text-xs text-hard-fg flex items-center justify-between">
                <span>{error}</span>
                <Button variant="ghost" size="sm" onClick={() => setError(null)} className="h-6 text-2xs">
                  Dismiss
                </Button>
              </div>
            )}

            <div className="flex items-center justify-between pt-1">
              <span className="text-2xs text-muted">
                {code.split('\n').length} lines · {code.length} characters
              </span>

              <Button
                variant="primary"
                size="md"
                loading={submitting}
                disabled={submitting || !code.trim()}
                onClick={handleSubmit}
              >
                {submitting ? 'Running Tests...' : 'Submit Code →'}
              </Button>
            </div>
          </Card>

          {/* Test Case Evaluation Results Card */}
          <Card className="p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-line pb-2.5">
              <span className="text-xs font-bold text-ink">Test Case Evaluation</span>
              {attemptResult && (
                <span className="text-xs font-mono font-semibold text-muted">
                  {attemptResult.passed_test_cases} / {attemptResult.total_test_cases} Passed
                </span>
              )}
            </div>

            {!attemptResult ? (
              <div className="py-8 text-center text-xs text-muted">
                Click <strong>Submit Code</strong> above to run your solution against the automated test cases.
              </div>
            ) : (
              <div className="space-y-3">
                {/* Test case tabs */}
                <div className="flex flex-wrap gap-1.5 border-b border-line pb-2">
                  {attemptResult.test_case_results.map((tc, idx) => {
                    const isPassed = tc.status === 'passed';
                    const isActive = activeTestCaseTab === idx;

                    return (
                      <button
                        key={tc.test_case_id}
                        type="button"
                        onClick={() => setActiveTestCaseTab(idx)}
                        className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                          isActive
                            ? 'bg-raised font-bold text-ink border border-line-strong'
                            : 'text-muted hover:text-body hover:bg-canvas'
                        }`}
                      >
                        {isPassed ? (
                          <CheckCircle2 className="h-3.5 w-3.5 text-easy" />
                        ) : (
                          <XCircle className="h-3.5 w-3.5 text-hard" />
                        )}
                        <span>Case {idx + 1}</span>
                      </button>
                    );
                  })}
                </div>

                {/* Selected Test Case Detail */}
                {attemptResult.test_case_results[activeTestCaseTab] && (
                  <div className="space-y-2 rounded border border-line bg-canvas p-3 text-xs">
                    {(() => {
                      const cur = attemptResult.test_case_results[activeTestCaseTab];
                      const isPassed = cur.status === 'passed';

                      return (
                        <>
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-ink">{cur.title}</span>
                            <div className="flex items-center gap-2">
                              {cur.execution_ms && (
                                <span className="text-2xs font-mono text-muted flex items-center gap-1">
                                  <Clock className="h-3 w-3" /> {cur.execution_ms}ms
                                </span>
                              )}
                              <Badge tone={isPassed ? 'easy' : 'danger'} className="text-2xs">
                                {isPassed ? 'Passed' : 'Failed'}
                              </Badge>
                            </div>
                          </div>

                          <div className="space-y-1.5 pt-1">
                            <div>
                              <span className="text-2xs uppercase tracking-wide font-semibold text-muted">
                                Expected Output
                              </span>
                              <pre className="mt-0.5 font-mono text-xs text-body bg-surface p-2 rounded border border-line whitespace-pre overflow-x-auto">
                                {cur.expected_output}
                              </pre>
                            </div>

                            <div>
                              <span className="text-2xs uppercase tracking-wide font-semibold text-muted">
                                Your Output
                              </span>
                              <pre
                                className={`mt-0.5 font-mono text-xs p-2 rounded border whitespace-pre overflow-x-auto ${
                                  isPassed
                                    ? 'bg-surface text-easy-fg border-easy/30'
                                    : 'bg-hard-bg text-hard-fg border-hard/30'
                                }`}
                              >
                                {cur.actual_output}
                              </pre>
                            </div>
                          </div>
                        </>
                      );
                    })()}
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
