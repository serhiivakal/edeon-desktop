import React, { useEffect } from 'react';
import { useJournalStore } from '../../store/journalStore';
import { ShieldAlert, BarChart3, TrendingUp, AlertTriangle } from 'lucide-react';

interface OverrideAnalyticsPanelProps {
  projectId: string;
}

export const OverrideAnalyticsPanel: React.FC<OverrideAnalyticsPanelProps> = ({ projectId }) => {
  const fetchOverrideAnalytics = useJournalStore((s) => s.fetchOverrideAnalytics);
  const analytics = useJournalStore((s) => s.overrideAnalytics);

  useEffect(() => {
    fetchOverrideAnalytics(projectId);
  }, [projectId, fetchOverrideAnalytics]);

  if (!analytics) return null;

  const overridePercent = (analytics.overall_override_rate * 100).toFixed(1);

  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <BarChart3 className="w-5 h-5 text-pink-400" />
          <h4 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
            User Override Analytics & Outcome Calibration
          </h4>
        </div>
        <div className="flex items-center space-x-2">
          <span className="px-3 py-1 rounded-full border border-pink-500/30 bg-pink-500/10 text-pink-300 text-xs font-mono font-semibold">
            Overall Override Rate: {overridePercent}%
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-slate-950/60 p-3.5 rounded-lg border border-slate-800">
          <span className="text-xs text-slate-400 uppercase font-semibold">Total System Decisions</span>
          <div className="text-xl font-bold text-slate-100 font-mono mt-1">{analytics.total_decisions}</div>
        </div>
        <div className="bg-slate-950/60 p-3.5 rounded-lg border border-slate-800">
          <span className="text-xs text-slate-400 uppercase font-semibold">Recorded User Overrides</span>
          <div className="text-xl font-bold text-pink-400 font-mono mt-1">{analytics.total_overrides}</div>
        </div>
        <div className="bg-slate-950/60 p-3.5 rounded-lg border border-slate-800">
          <span className="text-xs text-slate-400 uppercase font-semibold">Model Calibration Metric</span>
          <div className="text-xs text-slate-300 mt-1 font-mono">
            {analytics.overall_override_rate > 0.3 ? 'High Human Interventions (Calibrate Models)' : 'High Alignment'}
          </div>
        </div>
      </div>

      {/* Override rates by decision kind */}
      <div className="space-y-2 pt-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Override Frequency by Decision Type
        </span>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
          {Object.entries(analytics.by_kind).map(([kind, stats]) => (
            <div key={kind} className="p-2.5 bg-slate-950/40 rounded border border-slate-800 flex justify-between items-center">
              <span className="font-medium text-slate-300 font-mono">{kind}</span>
              <div className="text-right font-mono">
                <span className="text-slate-400">{stats.overridden}/{stats.total} </span>
                <span className="text-pink-400 font-semibold">({(stats.rate * 100).toFixed(0)}%)</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
