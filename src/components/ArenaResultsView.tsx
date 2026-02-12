import React, { useState, useMemo } from 'react';
import { useModelStore } from '../store/modelStore';
import { CvStabilityTable } from './CvStabilityTable';
import { YScramblingCard } from './YScramblingCard';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ResponsiveContainer,
} from 'recharts';

interface ArenaResultsViewProps {
  results: any; // Arena results object
  onClose: () => void;
}

export const ArenaResultsView: React.FC<ArenaResultsViewProps> = ({ results, onClose }) => {
  const { saveArenaRun, promoteArenaModel } = useModelStore();
  const [selectedAlgo, setSelectedAlgo] = useState<string | null>(null);
  const [saveName, setSaveName] = useState('');
  const [isSaved, setIsSaved] = useState(false);
  const [showShared, setShowShared] = useState(false);
  const [promotedAlgos, setPromotedAlgos] = useState<Record<string, boolean>>({});

  const modelType = results.shared?.model_type || 'regression';
  const primaryMetric = modelType === 'regression' ? 'r2_val' : 'accuracy_val';
  const primaryLabel = modelType === 'regression' ? 'R²' : 'Accuracy';

  // Sort models by primary metric descending
  const rankedModels = useMemo(() => {
    const models = [...(results.models || [])];
    return models.sort((a, b) => {
      if (a.error) return 1;
      if (b.error) return -1;
      return (b.metrics?.[primaryMetric] || 0) - (a.metrics?.[primaryMetric] || 0);
    });
  }, [results.models, primaryMetric]);

  // Find currently selected model details
  const activeModelDetail = useMemo(() => {
    if (!selectedAlgo) return null;
    return results.models.find((m: any) => m.algorithm === selectedAlgo) || null;
  }, [selectedAlgo, results.models]);

  const handleSaveRun = async () => {
    if (!saveName.trim()) return;
    try {
      await saveArenaRun(saveName);
      setIsSaved(true);
    } catch (e) {
      console.error('Failed to save arena run:', e);
    }
  };

  const handlePromote = async (algo: string) => {
    try {
      await promoteArenaModel(results.id || 'arena_temp_id', algo);
      setPromotedAlgos((prev) => ({ ...prev, [algo]: true }));
      alert(`Successfully promoted ${algo.toUpperCase()} model to your Custom Models Library!`);
    } catch (e) {
      console.error('Failed to promote model:', e);
      alert('Promotion failed: ' + String(e));
    }
  };

  const handleExportCSV = () => {
    const headers = ['Rank', 'Algorithm', primaryLabel, 'RMSE/F1', 'CV Score', 'Scramble Verdict', 'Duration (s)'];
    const rows = rankedModels.map((m, idx) => {
      const cvSummary = m.cv_results?.find((r: any) => r.fold === 'summary');
      const cvStr = cvSummary ? `${cvSummary.mean.toFixed(3)} ± ${cvSummary.std.toFixed(3)}` : '—';
      const scrambleVer = m.y_scramble?.verdict || '—';
      const secondaryVal = modelType === 'regression' ? m.metrics?.rmse_val?.toFixed(3) : m.metrics?.f1_score?.toFixed(3);
      return [
        idx + 1,
        m.algorithm.toUpperCase(),
        m.metrics?.[primaryMetric]?.toFixed(4) || '—',
        secondaryVal || '—',
        cvStr,
        scrambleVer,
        m.duration_s?.toFixed(2) || '0.00'
      ];
    });

    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `arena_results_${results.shared?.split_mode}_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="arena-results-dashboard animate-fadeIn">
      {/* Top Toolbar */}
      <div className="flex items-center justify-between border-b border-gray-800/60 pb-4 mb-6">
        <div>
          <h2 className="text-lg font-bold text-gray-100 flex items-center gap-2">
            🛡️ QSAR Model Arena Leaderboard
          </h2>
          <p className="text-xs text-gray-400 mt-1">
            Parallel training performance results across {results.models?.length} candidate QSAR architectures
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button className="inspector-btn text-xs" onClick={handleExportCSV}>
            📥 Export CSV
          </button>
          {!isSaved ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Enter Run Name..."
                className="config-input w-40 text-xs py-1"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
              />
              <button
                className="inspector-btn-primary text-xs py-1 px-3"
                onClick={handleSaveRun}
                disabled={!saveName.trim()}
              >
                💾 Save Run
              </button>
            </div>
          ) : (
            <span className="badge badge-success text-xs py-1 px-2.5">
              ✓ Run Saved
            </span>
          )}
          <button className="inspector-btn text-xs border-red-500/30 text-red-400 hover:bg-red-500/5" onClick={onClose}>
            Close Dashboard
          </button>
        </div>
      </div>

      {/* Shared Config Accordion */}
      <div className="glass-card mb-6 p-4">
        <div
          className="flex cursor-pointer items-center justify-between text-xs font-semibold text-gray-400"
          onClick={() => setShowShared(!showShared)}
        >
          <div className="flex items-center gap-2">
            <span>⚙️ SHARED TRAINING CONFIGURATION & CURATION FUNNEL</span>
          </div>
          <span className="text-[11px] hover:text-gray-200">
            {showShared ? 'Hide Details ▲' : 'Show Details ▼'}
          </span>
        </div>
        {showShared && (
          <div className="mt-4 border-t border-gray-800/40 pt-4 grid grid-cols-2 gap-6 text-xs text-gray-400">
            <div>
              <h4 className="font-bold text-gray-300 mb-2 uppercase tracking-wider text-[10px]">Data Curation Funnel</h4>
              <div className="bg-gray-950/40 p-3 rounded font-mono text-[10px] leading-relaxed">
                <div>Total compounds: {results.shared?.curation_report?.activity_stats?.n_total || '—'}</div>
                <div>Parsed successfully: {results.shared?.curation_report?.canonicalization?.n_valid || '—'}</div>
                <div>Duplicates merged: {results.shared?.curation_report?.canonicalization?.n_duplicates_merged || '—'}</div>
                <div>Salts stripped: {results.shared?.curation_report?.canonicalization?.n_salts_stripped || '—'}</div>
              </div>
            </div>
            <div>
              <h4 className="font-bold text-gray-300 mb-2 uppercase tracking-wider text-[10px]">Shared Strategy</h4>
              <div className="bg-gray-950/40 p-3 rounded font-mono text-[10px] grid grid-cols-2 gap-2">
                <div>Split Mode: <span className="text-emerald-400 font-semibold">{results.shared?.split_mode}</span></div>
                <div>CV Folds: <span className="text-emerald-400 font-semibold">{results.shared?.cv_k}</span></div>
                <div>Hold-out test count: <span className="text-emerald-400 font-semibold">{results.shared?.test_indices?.length}</span></div>
                <div>Descriptors dimension: <span className="text-emerald-400 font-semibold">{results.shared?.feature_names?.length}</span></div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Main Leaderboard Table */}
      <div className="glass-card mb-6 overflow-hidden">
        <table className="edeon-table w-full text-left text-xs">
          <thead>
            <tr className="bg-gray-900/40 border-b border-gray-800/80">
              <th className="py-3 pl-4">Rank</th>
              <th className="py-3">Algorithm</th>
              <th className="py-3">{primaryLabel} Validation</th>
              <th className="py-3">{modelType === 'regression' ? 'RMSE' : 'F1-Score'}</th>
              <th className="py-3">CV Stability (mean ± sd)</th>
              <th className="py-3 text-center">Y-Scrambling</th>
              <th className="py-3 text-center">Sparkline</th>
              <th className="py-3 text-right pr-4">Promote</th>
            </tr>
          </thead>
          <tbody>
            {rankedModels.map((m, idx) => {
              const hasError = !!m.error;
              const isSelected = selectedAlgo === m.algorithm;
              
              const cvSummary = m.cv_results?.find((r: any) => r.fold === 'summary');
              const cvStr = cvSummary ? `${cvSummary.mean.toFixed(3)} ± ${cvSummary.std.toFixed(3)}` : '—';
              const scrambleVer = m.y_scramble?.verdict || '—';
              
              const sparklinePoints = useMemo(() => {
                if (hasError || !m.plot_data?.points) return [];
                return m.plot_data.points.slice(0, 10).map((pt: any, i: number) => ({
                  idx: i,
                  x: pt.true_value || 0,
                  y: pt.pred_value || 0
                }));
              }, [m.plot_data, hasError]);

              return (
                <tr
                  key={m.algorithm}
                  onClick={() => !hasError && setSelectedAlgo(isSelected ? null : m.algorithm)}
                  className={`border-b border-gray-800/40 cursor-pointer transition-colors ${
                    hasError ? 'opacity-50 cursor-not-allowed hover:bg-red-950/5' : 'hover:bg-gray-800/20'
                  } ${isSelected ? 'bg-brand-900/10 border-l-2 border-l-emerald-500' : ''}`}
                >
                  <td className="py-3 pl-4 font-semibold text-gray-400">
                    {hasError ? '—' : `#${idx + 1}`}
                  </td>
                  <td className="py-3 font-semibold text-gray-200">
                    {m.algorithm.toUpperCase()}
                  </td>
                  <td className="py-3">
                    {hasError ? (
                      <span className="text-red-400 font-semibold">Error</span>
                    ) : (
                      <span className="text-emerald-400 font-semibold">{m.metrics?.[primaryMetric]?.toFixed(4)}</span>
                    )}
                  </td>
                  <td className="py-3 text-gray-300">
                    {hasError ? '—' : modelType === 'regression' ? m.metrics?.rmse_val?.toFixed(3) : m.metrics?.f1_score?.toFixed(3)}
                  </td>
                  <td className="py-3 text-gray-400">
                    {hasError ? '—' : cvStr}
                  </td>
                  <td className="py-3 text-center">
                    {hasError ? '—' : (
                      <span className={`badge ${
                        scrambleVer === 'robust' ? 'badge-success' : scrambleVer === 'marginal' ? 'badge-warning' : 'badge-danger'
                      } text-[10px]`}>
                        {scrambleVer.toUpperCase()}
                      </span>
                    )}
                  </td>
                  <td className="py-3 flex justify-center items-center">
                    {hasError || sparklinePoints.length === 0 ? '—' : (
                      <div className="h-[24px] w-[50px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <ScatterChart margin={{ top: 2, bottom: 2, left: 2, right: 2 }}>
                            <XAxis dataKey="x" type="number" hide domain={['auto', 'auto']} />
                            <YAxis dataKey="y" type="number" hide domain={['auto', 'auto']} />
                             <Scatter data={sparklinePoints} fill="#10b981" line={{ stroke: '#10b981', strokeWidth: 1 }} shape="circle" />
                          </ScatterChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </td>
                  <td className="py-3 text-right pr-4" onClick={(e) => e.stopPropagation()}>
                    {hasError ? '—' : promotedAlgos[m.algorithm] ? (
                      <span className="text-[10px] text-emerald-400 font-semibold">✓ Promoted</span>
                    ) : (
                      <button
                        className="inspector-btn text-[10px] py-0.5 px-2 bg-emerald-500/10 text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20"
                        onClick={() => handlePromote(m.algorithm)}
                      >
                        Promote 🚀
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Drill-down Detail Panel */}
      {selectedAlgo && activeModelDetail && (
        <div className="glass-card p-6 border-l-4 border-l-emerald-500 animate-slideDown">
          <div className="flex items-center justify-between mb-4 border-b border-gray-800/40 pb-3">
            <h3 className="font-bold text-gray-200 flex items-center gap-2">
              🔬 Concurrently Trained {selectedAlgo.toUpperCase()} Deep Dive
            </h3>
            <span className="badge badge-success text-xs">
              Primary {primaryLabel}: {activeModelDetail.metrics?.[primaryMetric]?.toFixed(4)}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="flex flex-col gap-6">
              {/* CV Stability Table */}
              {activeModelDetail.cv_results && (
                <CvStabilityTable cvResults={activeModelDetail.cv_results} modelType={modelType} />
              )}
            </div>

            <div className="flex flex-col gap-6">
              {/* Y-Scrambling Permutations Card */}
              {activeModelDetail.y_scramble && (
                <YScramblingCard yScramble={activeModelDetail.y_scramble} />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
