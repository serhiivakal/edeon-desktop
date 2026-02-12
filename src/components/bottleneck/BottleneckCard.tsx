import React from 'react';
import { BottleneckAnalysis, BottleneckKind, RecommendedAction, Reliability } from '../../store/bottleneckStore';
import { AlertTriangle, AlertCircle, CheckCircle, HelpCircle, ArrowUpRight } from 'lucide-react';

interface BottleneckCardProps {
  analysis: BottleneckAnalysis;
  onSelectEndpoint?: (endpoint: string) => void;
}

const KIND_COLORS: Record<BottleneckKind, { bg: string; text: string; border: string }> = {
  chemical: { bg: 'bg-rose-500/10', text: 'text-rose-400', border: 'border-rose-500/30' },
  epistemic: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30' },
  distractor: { bg: 'bg-slate-500/10', text: 'text-slate-400', border: 'border-slate-500/30' },
};

const ACTION_LABELS: Record<RecommendedAction, string> = {
  redesign_structure: 'Redesign Core Structure',
  measure_endpoint: 'Measure Endpoint In-Vitro',
  improve_model: 'Collect Training Data for AD',
  deprioritize_weight: 'Lower Weight in Scoring',
  no_action: 'No Action Needed',
};

const RELIABILITY_BADGES: Record<Reliability, { label: string; color: string }> = {
  ok: { label: 'High Reliability', color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' },
  low: { label: 'Low Reliability (Small N)', color: 'text-amber-400 border-amber-500/30 bg-amber-500/10' },
  insufficient_data: { label: 'Insufficient In-AD Data', color: 'text-rose-400 border-rose-500/30 bg-rose-500/10' },
};

export const BottleneckCard: React.FC<BottleneckCardProps> = ({ analysis, onSelectEndpoint }) => {
  const topEp = analysis.endpoints.length > 0 ? analysis.endpoints[0] : null;

  if (!topEp) {
    return null;
  }

  const kindStyle = KIND_COLORS[topEp.kind] || KIND_COLORS.distractor;
  const relStyle = RELIABILITY_BADGES[topEp.reliability] || RELIABILITY_BADGES.ok;

  return (
    <div className={`rounded-xl border ${kindStyle.border} bg-slate-900/60 p-5 backdrop-blur-md shadow-lg space-y-4`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <AlertCircle className={`w-5 h-5 ${kindStyle.text}`} />
          <h3 className="text-sm font-semibold tracking-wide uppercase text-slate-300">
            Primary Bottleneck Identified
          </h3>
        </div>
        <div className="flex items-center space-x-2">
          <span className={`px-2.5 py-1 text-xs rounded-full border font-medium ${relStyle.color}`}>
            {relStyle.label}
          </span>
          {analysis.bottleneck_ambiguous && (
            <span className="px-2.5 py-1 text-xs rounded-full border border-amber-500/40 bg-amber-500/10 text-amber-300 font-medium flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5" /> Ambiguous Top-2
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
        <div className="md:col-span-2 space-y-2">
          <div className="flex items-baseline space-x-3">
            <span className="text-xl font-bold text-slate-100">{topEp.display_name}</span>
            <span className={`px-2.5 py-0.5 text-xs rounded-md border font-semibold uppercase tracking-wider ${kindStyle.bg} ${kindStyle.text} ${kindStyle.border}`}>
              {topEp.kind} constraint
            </span>
          </div>

          <p className="text-sm text-slate-400">{topEp.reason}</p>

          <div className="pt-2 flex items-center space-x-4 text-xs text-slate-400">
            <div>
              <span className="text-slate-500">Leverage: </span>
              <span className="font-mono font-medium text-slate-200">+{topEp.leverage.toFixed(4)}</span>
              <span className="text-slate-500 font-mono text-[10px] ml-1">
                [{topEp.leverage_ci[0].toFixed(3)}, {topEp.leverage_ci[1].toFixed(3)}]
              </span>
            </div>
            <div>
              <span className="text-slate-500">Headroom: </span>
              <span className="font-mono font-medium text-slate-200">{topEp.headroom.toFixed(3)}</span>
            </div>
            <div>
              <span className="text-slate-500">Rank Stability: </span>
              <span className="font-mono font-medium text-slate-200">{(topEp.rank_stability * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        <div className="bg-slate-950/50 p-4 rounded-lg border border-slate-800/80 space-y-2 flex flex-col justify-between">
          <span className="text-xs uppercase font-semibold text-slate-400 tracking-wider">Recommended Action</span>
          <div className="text-sm font-semibold text-slate-200 flex items-center space-x-1.5">
            <span>{ACTION_LABELS[topEp.recommended_action] || topEp.recommended_action}</span>
          </div>
          {onSelectEndpoint && (
            <button
              onClick={() => onSelectEndpoint(topEp.endpoint)}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center space-x-1 pt-1 self-start transition-colors"
            >
              <span>Inspect Endpoint Details</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
