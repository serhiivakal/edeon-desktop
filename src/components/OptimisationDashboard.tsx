import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useModelStore } from '../store/modelStore';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';

interface OptimisationDashboardProps {
  nTrials: number;
  mode: 'grid' | 'bayesian';
  algorithm: string;
}

export const OptimisationDashboard: React.FC<OptimisationDashboardProps> = ({
  nTrials,
  mode,
  algorithm,
}) => {
  const { trials, trainingLogs } = useModelStore();
  const [logsExpanded, setLogsExpanded] = useState(false);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Autoscroll terminal
  useEffect(() => {
    if (terminalEndRef.current && logsExpanded) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [trainingLogs, logsExpanded]);

  // Compute trial stats
  const trialsDone = trials.length;
  const avgDuration = useMemo(() => {
    if (trials.length === 0) return 0;
    const sum = trials.reduce((acc, t) => acc + (t.duration_s || 0), 0);
    return sum / trials.length;
  }, [trials]);

  const etaSeconds = useMemo(() => {
    if (trialsDone === 0) return 0;
    const remaining = nTrials - trialsDone;
    return remaining * avgDuration;
  }, [trialsDone, nTrials, avgDuration]);

  // Sort trials by score descending
  const sortedTrials = useMemo(() => {
    return [...trials].sort((a, b) => b.mean_score - a.mean_score);
  }, [trials]);

  // Find the running best score at each trial index for the convergence plot
  const convergenceData = useMemo(() => {
    let currentBest = -Infinity;
    return trials.map((t) => {
      if (t.mean_score > currentBest) {
        currentBest = t.mean_score;
      }
      return {
        trial: t.trial_id + 1,
        score: t.mean_score,
        best: currentBest,
      };
    });
  }, [trials]);

  const bestTrial = sortedTrials[0] || null;

  return (
    <div className="optimisation-dashboard">
      {/* Top Banner / Progress Cards */}
      <div className="dashboard-grid-3">
        <div className="glass-card stat-card relative overflow-hidden">
          <div className="stat-glow bg-emerald-500/10" />
          <div className="stat-label">Progress Check</div>
          <div className="stat-value text-emerald-400">
            {trialsDone} <span className="text-gray-500">/</span> {nTrials}
          </div>
          <div className="stat-desc">
            {trialsDone === nTrials ? 'Optimisation Complete' : `Running trial ${trialsDone + 1}...`}
          </div>
          <div className="progress-bar-track mt-4 h-1.5 w-full overflow-hidden rounded-full bg-gray-800">
            <div
              className="progress-bar-fill h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-300"
              style={{ width: `${(trialsDone / nTrials) * 100}%` }}
            />
          </div>
        </div>

        <div className="glass-card stat-card relative overflow-hidden">
          <div className="stat-glow bg-teal-500/10" />
          <div className="stat-label">Performance Metric</div>
          <div className="stat-value text-teal-400">
            {avgDuration > 0 ? `${avgDuration.toFixed(2)}s` : '—'}
          </div>
          <div className="stat-desc">Average Trial Compute Speed</div>
          <div className="mt-4 flex items-center gap-1.5 text-xs text-teal-500/70">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-teal-400" />
            Active Sweeps Streamed
          </div>
        </div>

        <div className="glass-card stat-card relative overflow-hidden">
          <div className="stat-glow bg-cyan-500/10" />
          <div className="stat-label">Estimated Time Remaining (ETA)</div>
          <div className="stat-value text-cyan-400">
            {trialsDone === nTrials
              ? 'Done'
              : etaSeconds > 0
              ? `${Math.ceil(etaSeconds)}s`
              : 'Calculating...'}
          </div>
          <div className="stat-desc">Active dynamic calculations</div>
          <div className="mt-4 text-xs text-gray-500">
            Algorithm strategy: <span className="font-semibold text-cyan-500/80">{algorithm.toUpperCase()}</span>
          </div>
        </div>
      </div>

      {/* Split Panels: Trials Leaderboard and Convergence Chart */}
      <div className="dashboard-split mt-6">
        {/* Left Side: Leaderboard */}
        <div className="glass-card split-panel scrollable-panel flex flex-col">
          <div className="panel-header mb-4 flex items-center justify-between">
            <h3 className="panel-title text-sm font-semibold uppercase tracking-wider text-gray-400">
              Trials Leaderboard
            </h3>
            {bestTrial && (
              <span className="badge badge-success text-[10px]">
                Best Score: {bestTrial.mean_score.toFixed(4)}
              </span>
            )}
          </div>
          <div className="panel-content overflow-y-auto flex-1 pr-1">
            <table className="edeon-table w-full text-left text-xs">
              <thead>
                <tr>
                  <th className="py-2 pl-3">Trial ID</th>
                  <th className="py-2">Score (Mean ± Std)</th>
                  <th className="py-2 pr-3">Parameters Checked</th>
                </tr>
              </thead>
              <tbody>
                {sortedTrials.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-gray-500">
                      Waiting for first trial results to stream...
                    </td>
                  </tr>
                ) : (
                  sortedTrials.map((t, idx) => (
                    <tr
                      key={t.trial_id}
                      className={`border-b border-gray-800/40 transition-colors hover:bg-gray-800/10 ${
                        idx === 0 ? 'bg-emerald-500/5 font-medium' : ''
                      }`}
                    >
                      <td className="py-2 pl-3 text-gray-400">
                        #{t.trial_id + 1}{' '}
                        {idx === 0 && <span className="text-[10px] text-emerald-400">(Best)</span>}
                      </td>
                      <td className="py-2">
                        <span className={idx === 0 ? 'text-emerald-400' : 'text-gray-200'}>
                          {t.mean_score.toFixed(4)}
                        </span>{' '}
                        <span className="text-[10px] text-gray-500">
                          ± {t.std_score.toFixed(4)}
                        </span>
                      </td>
                      <td className="py-2 pr-3 max-w-[200px] truncate text-gray-400 text-[11px]" title={JSON.stringify(t.params)}>
                        {Object.entries(t.params)
                          .map(([k, v]) => `${k}=${typeof v === 'number' ? v.toFixed(3).replace(/\.?0+$/, '') : v}`)
                          .join(', ')}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Side: Convergence Curve */}
        <div className="glass-card split-panel flex flex-col">
          <div className="panel-header mb-4 flex items-center justify-between">
            <h3 className="panel-title text-sm font-semibold uppercase tracking-wider text-gray-400">
              Parameter Convergence
            </h3>
            <span className="text-[11px] text-gray-500">
              {mode === 'bayesian' ? 'Bayesian study optimizer' : 'Discrete grids list'}
            </span>
          </div>
          <div className="panel-content flex-1 min-h-[220px]">
            {convergenceData.length === 0 ? (
              <div className="flex h-full items-center justify-center text-gray-500 text-xs">
                Plotting convergence curves in real time...
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={convergenceData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2e3440/30" />
                  <XAxis dataKey="trial" stroke="#4c566a" style={{ fontSize: 10 }} />
                  <YAxis stroke="#4c566a" style={{ fontSize: 10 }} domain={['auto', 'auto']} />
                  <RechartsTooltip
                    contentStyle={{
                      background: '#1e222b',
                      borderColor: '#3b4252',
                      borderRadius: 8,
                      color: '#d8dee9',
                      fontSize: 11,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#4c566a"
                    strokeWidth={1}
                    dot={{ r: 2, fill: '#4c566a' }}
                    name="Trial Score"
                  />
                  <Line
                    type="stepAfter"
                    dataKey="best"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#10b981' }}
                    name="Current Best"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Panel: Collapsible Raw Terminals */}
      <div className="glass-card mt-6 p-4">
        <div
          className="flex cursor-pointer items-center justify-between text-xs font-semibold text-gray-400"
          onClick={() => setLogsExpanded(!logsExpanded)}
        >
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 items-center justify-center">
              <span className={`h-1.5 w-1.5 rounded-full bg-emerald-400 ${trialsDone === nTrials ? '' : 'animate-ping'}`} />
            </span>
            <span>EDEON ENGINE LIVE TERMINAL CONSOLE LOGS</span>
          </div>
          <span className="text-[11px] hover:text-gray-200">
            {logsExpanded ? 'Collapse ▲' : 'Expand ▼'}
          </span>
        </div>

        {logsExpanded && (
          <div className="terminal-console mt-4 max-h-[180px] overflow-y-auto">
            <div className="terminal-body p-2 font-mono text-[11px] leading-relaxed">
              {trainingLogs.map((line, i) => {
                let typeClass = 'info';
                if (line.includes('[PROCESS]')) typeClass = 'process';
                if (line.includes('[SUCCESS]')) typeClass = 'success';
                if (line.includes('[ERROR]')) typeClass = 'error';
                return (
                  <div key={i} className={`terminal-log-line ${typeClass}`}>
                    {line}
                  </div>
                );
              })}
              <div ref={terminalEndRef} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
