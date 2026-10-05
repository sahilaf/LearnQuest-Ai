/**
 * PracticeList - OWNER: Member 2 (Learning Management).
 * See CHECKLIST.md Week 3 Slot 10 & docs/DESIGN_GUIDELINES.md.
 *
 * Information-dense HackerRank-style practice problem list with:
 * - Skill verification tracker
 * - Filterable table by skill, difficulty, search
 * - Pass / Attempt status indicators
 * - Loading, empty, and mobile responsive states
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Circle } from 'lucide-react';

import PageHeader from '../../components/layout/PageHeader';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  ProgressBar,
  Select,
  Skeleton,
  Spinner,
} from '../../components/ui';
import { getSkillStatus, listProblems } from '../../api/practice';

const DIFFICULTY_OPTIONS = [
  { value: '', label: 'All Difficulties' },
  { value: 'easy', label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard', label: 'Hard' },
];

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

export default function PracticeList({ embedded = false }) {
  const [problems, setProblems] = useState([]);
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [search, setSearch] = useState('');
  const [selectedSkill, setSelectedSkill] = useState('');
  const [selectedDifficulty, setSelectedDifficulty] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [probRes, skillRes] = await Promise.all([
        listProblems({
          search,
          skill: selectedSkill,
          difficulty: selectedDifficulty,
        }),
        getSkillStatus(),
      ]);

      const items = probRes?.items || (Array.isArray(probRes) ? probRes : []);
      setProblems(items);

      const skillItems = skillRes?.items || (Array.isArray(skillRes) ? skillRes : []);
      setSkills(skillItems);
    } catch (err) {
      console.error('Failed to load practice problems:', err);
      setError(err?.detail || 'Unable to load practice problems. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [search, selectedSkill, selectedDifficulty]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const skillOptions = [
    { value: '', label: 'All Skills' },
    ...skills.map((s) => ({ value: s.id, label: s.name })),
  ];

  return (
    <div className="space-y-8 pb-12">
      {!embedded && (
        <PageHeader
          title="SQL Challenges"
          subtitle="Work through hands-on technical problems with automated test case evaluation to verify core skills."
        />
      )}

      {/* 1. Skill Verification Tracker Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-ink">Skill Verification</h2>
            <p className="text-xs text-muted">
              Solve required problems in a skill domain to unlock official verification.
            </p>
          </div>
          <Link to="/review" className="text-xs font-semibold text-primary-600 hover:text-primary-700">
            Due for Review? Open Queue →
          </Link>
        </div>

        {loading && skills.length === 0 ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <Card key={i} className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1.5 w-2/3">
                    <Skeleton className="h-3 w-16" />
                    <Skeleton className="h-4 w-32" />
                  </div>
                  <Skeleton className="h-5 w-16 rounded-full" />
                </div>
                <Skeleton className="h-2 w-full rounded" />
              </Card>
            ))}
          </div>
        ) : skills.length === 0 ? (
          <EmptyState
            title="No skills registered"
            description="Complete learning tracks or take quizzes to initialize skill verification tracks."
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {skills.map((skill) => {
              const isVerified = skill.verified || (skill.passed_count >= skill.required_to_verify);
              const pct = Math.min(
                100,
                Math.round((skill.passed_count / Math.max(1, skill.required_to_verify)) * 100)
              );

              return (
                <Card key={skill.id} className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <span className="label">Domain Skill</span>
                      <h3 className="mt-0.5 truncate text-sm font-bold text-ink">
                        {skill.name}
                      </h3>
                    </div>
                    {isVerified ? (
                      <Badge tone="easy" className="shrink-0 text-xs">
                        Skill verified ✓
                      </Badge>
                    ) : (
                      <Badge tone="neutral" className="shrink-0 text-xs">
                        {skill.passed_count} / {skill.required_to_verify} passed
                      </Badge>
                    )}
                  </div>

                  <div className="space-y-1">
                    <ProgressBar
                      value={pct}
                      tone={isVerified ? 'easy' : 'default'}
                      size="sm"
                    />
                    <div className="flex justify-between text-[11px] text-muted">
                      <span>{pct}% complete</span>
                      <span>{isVerified ? 'Verified' : `${skill.required_to_verify - skill.passed_count} remaining`}</span>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* 2. Search and Filters */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <Input
            id="practice-search"
            type="search"
            placeholder="Search problems by title, keywords..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div>
          <Select
            id="skill-filter"
            value={selectedSkill}
            onChange={(e) => setSelectedSkill(e.target.value)}
            options={skillOptions}
          />
        </div>
        <div>
          <Select
            id="difficulty-filter"
            value={selectedDifficulty}
            onChange={(e) => setSelectedDifficulty(e.target.value)}
            options={DIFFICULTY_OPTIONS}
          />
        </div>
      </div>

      {/* 3. Problems List Table */}
      {loading ? (
        <Card className="overflow-hidden p-0">
          <div className="p-4 flex items-center gap-2 text-xs text-muted border-b border-line">
            <Spinner size="sm" label="Loading problems" />
            <span>Loading practice problems...</span>
          </div>
          <div className="divide-y divide-line">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="p-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 w-1/2">
                  <Skeleton className="h-4 w-4 rounded-full shrink-0" />
                  <div className="space-y-1 w-full">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/3" />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Skeleton className="h-5 w-16 rounded-full" />
                  <Skeleton className="h-8 w-20 rounded-lg" />
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : error ? (
        <div className="rounded border border-hard/40 bg-hard-bg p-4 text-sm text-hard-fg flex items-center justify-between">
          <p>{error}</p>
          <Button variant="danger" size="sm" onClick={loadData}>
            Retry
          </Button>
        </div>
      ) : problems.length === 0 ? (
        <EmptyState
          title="No problems found"
          description="Try broadening your search query or selecting a different skill filter."
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setSearch('');
                setSelectedSkill('');
                setSelectedDifficulty('');
              }}
            >
              Clear Filters
            </Button>
          }
        />
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="table-dense w-full">
              <thead>
                <tr>
                  <th className="w-12 text-center">Status</th>
                  <th>Problem Title</th>
                  <th className="hidden sm:table-cell">Skill / Topic</th>
                  <th>Difficulty</th>
                  <th className="hidden md:table-cell">Submissions</th>
                  <th className="w-28 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {problems.map((prob) => {
                  const isSolved = prob.status === 'solved';

                  return (
                    <tr key={prob.id} className="transition-colors hover:bg-canvas">
                      {/* Status */}
                      <td className="text-center">
                        {isSolved ? (
                          <span title="Solved" className="inline-flex text-easy">
                            <CheckCircle2 className="h-4 w-4" />
                          </span>
                        ) : (
                          <span title="Unsolved" className="inline-flex text-muted">
                            <Circle className="h-3.5 w-3.5" />
                          </span>
                        )}
                      </td>

                      {/* Title */}
                      <td>
                        <Link
                          to={`/practice/${prob.id}`}
                          className="font-semibold text-ink transition-colors hover:text-primary-600 block py-1"
                        >
                          {prob.title}
                        </Link>
                        <span className="sm:hidden text-2xs text-muted block mt-0.5">
                          {prob.skill_name || prob.topic_tag}
                        </span>
                      </td>

                      {/* Skill / Topic */}
                      <td className="hidden sm:table-cell">
                        <span className="font-mono text-2xs text-muted">
                          {prob.skill_name || prob.topic_tag}
                        </span>
                      </td>

                      {/* Difficulty */}
                      <td>
                        <Badge tone={getDifficultyTone(prob.difficulty)} className="text-2xs">
                          {prob.difficulty}
                        </Badge>
                      </td>

                      {/* Submissions & Rate */}
                      <td className="hidden md:table-cell text-xs text-muted">
                        {prob.acceptance_rate} ({prob.total_submissions})
                      </td>

                      {/* Action */}
                      <td className="text-right">
                        <Link to={`/practice/${prob.id}`}>
                          <Button
                            variant={isSolved ? 'secondary' : 'primary'}
                            size="sm"
                            className="text-xs"
                          >
                            {isSolved ? 'Review' : 'Solve'}
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
