/**
 * Profile - OWNER: Member 3.
 *
 * Name, a learning summary, and the two preferences that actually change what
 * the app does:
 *
 *   daily goal        how many minutes `GET /api/recommendations/daily-plan`
 *                     fills with review, lessons and a quiz
 *   leaderboard       whether you appear on the public board. You always see
 *                     your own rank either way - opting out hides you from
 *                     others, not from yourself.
 *
 * Email is shown but not editable: it belongs to the sign-in provider, and
 * changing it here would desynchronise the account from Supabase Auth.
 */
import { useEffect, useMemo, useState } from 'react';
import { Award, Flame, Save, Target, Zap } from 'lucide-react';

import PageHeader from '../../components/layout/PageHeader';
import { Button, Card, CardHeader, EmptyState, Input, Spinner } from '../../components/ui';
import { getMe, updateMe } from '../../api/users';

const GOALS = [10, 20, 30, 45, 60];

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg border border-line bg-raised p-4">
      <div className="label mb-2 flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <p className="font-mono text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

export default function Profile() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [name, setName] = useState('');
  const [goal, setGoal] = useState(30);
  const [optOut, setOptOut] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const load = () => {
    setLoading(true);
    setError(null);
    getMe()
      .then((data) => {
        setProfile(data);
        const u = data?.user || {};
        const prefs = u.preferences || {};
        setName(u.full_name || '');
        setGoal(Number(prefs.daily_goal_minutes) || 30);
        setOptOut(Boolean(prefs.leaderboard_opt_out));
      })
      .catch((err) => setError(err?.detail || 'Could not load your profile.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const user = profile?.user;
  const stats = profile?.stats || {};

  const dirty = useMemo(() => {
    if (!user) return false;
    const prefs = user.preferences || {};
    return (
      name.trim() !== (user.full_name || '')
      || goal !== (Number(prefs.daily_goal_minutes) || 30)
      || optOut !== Boolean(prefs.leaderboard_opt_out)
    );
  }, [user, name, goal, optOut]);

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const updated = await updateMe({
        full_name: name.trim() || null,
        // Merged with existing preferences so saving here never wipes a
        // setting some other screen stored.
        preferences: {
          ...(user?.preferences || {}),
          daily_goal_minutes: goal,
          leaderboard_opt_out: optOut,
        },
      });
      setProfile(updated);
      setSaved(true);
    } catch (err) {
      setSaveError(err?.detail || 'Could not save your changes.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (error || !user) {
    return (
      <div>
        <PageHeader title="Profile" />
        <EmptyState
          title="Profile unavailable"
          description={error || 'Your profile could not be found.'}
          action={<Button variant="secondary" size="sm" onClick={load}>Try again</Button>}
        />
      </div>
    );
  }

  const joined = user.created_at ? new Date(user.created_at).toLocaleDateString() : null;

  return (
    <div>
      <PageHeader
        eyebrow="Account"
        title={user.full_name || 'Your profile'}
        subtitle={joined ? `Learning since ${joined}.` : undefined}
      />

      <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={Zap} label="XP" value={(stats.xp ?? 0).toLocaleString()} />
        <Stat icon={Award} label="Level" value={stats.level ?? 1} />
        <Stat icon={Flame} label="Streak" value={`${stats.current_streak ?? 0}d`} />
        <Stat icon={Target} label="Best streak" value={`${stats.longest_streak ?? 0}d`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Details" />
          <div className="space-y-5">
            <Input
              label="Name"
              name="full_name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
            />
            <Input
              label="Email"
              name="email"
              value={user.email}
              disabled
              hint="Managed by your sign-in provider, so it can't be changed here."
            />
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Learning preferences"
            subtitle="These change what the app plans for you."
          />

          <div className="space-y-6">
            <div>
              <p className="mb-2 text-sm font-medium text-ink">Daily goal</p>
              <div className="flex flex-wrap gap-2">
                {GOALS.map((minutes) => (
                  <button
                    key={minutes}
                    type="button"
                    onClick={() => setGoal(minutes)}
                    className={`h-10 rounded border px-4 text-sm font-medium transition-colors ${
                      goal === minutes
                        ? 'border-primary-500 bg-primary-500/15 text-primary-300'
                        : 'border-line-strong bg-raised text-body hover:border-muted'
                    }`}
                  >
                    {minutes} min
                  </button>
                ))}
              </div>
              <p className="mt-2 text-sm text-muted">
                Your daily plan fills this much time with review first, then lessons, then a quiz.
              </p>
            </div>

            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={!optOut}
                onChange={(e) => setOptOut(!e.target.checked)}
                className="mt-1 h-4 w-4 accent-primary-600"
              />
              <span>
                <span className="block text-sm font-medium text-ink">Show me on the leaderboard</span>
                <span className="block text-sm text-muted">
                  Turn this off to hide your name and XP from other learners. You'll still see
                  your own rank.
                </span>
              </span>
            </label>
          </div>
        </Card>
      </div>

      <div className="mt-6 flex items-center justify-end gap-3">
        {saveError && <p className="text-sm text-hard">{saveError}</p>}
        {saved && !dirty && <p className="text-sm text-easy-fg">Saved.</p>}
        <Button onClick={save} disabled={!dirty || saving} loading={saving}>
          <Save className="h-4 w-4" />
          Save changes
        </Button>
      </div>
    </div>
  );
}
