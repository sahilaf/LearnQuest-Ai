/**
 * ProgressHub - Unified learner progress & analytics.
 * Combines Stats & Misconception Map, Achievements, Leaderboard, and Activity History as tabs on one page.
 */
import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { BarChart3, Trophy, Medal, History } from 'lucide-react';

import Stats from '../Stats/Stats';
import Achievements from '../Achievements/Achievements';
import Leaderboard from '../Leaderboard/Leaderboard';
import HistoryPage from '../History/History';

export default function ProgressHub() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab') || 'stats';

  const activeTab = useMemo(() => {
    if (['stats', 'achievements', 'leaderboard', 'history'].includes(tabParam)) {
      return tabParam;
    }
    return 'stats';
  }, [tabParam]);

  const setActiveTab = (tab) => {
    setSearchParams({ tab });
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="border-b border-line pb-5">
        <h1 className="text-2xl font-bold tracking-tight text-ink">Progress</h1>
        <p className="mt-1 text-sm text-muted">
          Your learning statistics, mastery milestones, badges, leaderboard standing, and activity history.
        </p>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-1 border-b border-line pb-px overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab('stats')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
            activeTab === 'stats'
              ? 'border-primary-500 text-ink'
              : 'border-transparent text-muted hover:text-body'
          }`}
        >
          <BarChart3 className="h-4 w-4" />
          Stats & Misconceptions
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('achievements')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
            activeTab === 'achievements'
              ? 'border-primary-500 text-ink'
              : 'border-transparent text-muted hover:text-body'
          }`}
        >
          <Trophy className="h-4 w-4" />
          Achievements & Badges
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('leaderboard')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
            activeTab === 'leaderboard'
              ? 'border-primary-500 text-ink'
              : 'border-transparent text-muted hover:text-body'
          }`}
        >
          <Medal className="h-4 w-4" />
          Leaderboard
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('history')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
            activeTab === 'history'
              ? 'border-primary-500 text-ink'
              : 'border-transparent text-muted hover:text-body'
          }`}
        >
          <History className="h-4 w-4" />
          History
        </button>
      </div>

      {/* Tab Contents */}
      {activeTab === 'stats' && <Stats embedded={true} />}
      {activeTab === 'achievements' && <Achievements embedded={true} />}
      {activeTab === 'leaderboard' && <Leaderboard embedded={true} />}
      {activeTab === 'history' && <HistoryPage embedded={true} />}
    </div>
  );
}
