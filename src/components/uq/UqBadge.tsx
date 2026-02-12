import { useState } from 'react';

export type AdStatus = 'in_domain' | 'borderline' | 'out_of_domain' | 'unknown';

interface UqBadgeProps {
  status: AdStatus;
  score?: number | null; // e.g. Tanimoto similarity (0..1)
  coverage?: number; // e.g. 0.90
  modelId?: string;
  tooltipAlign?: 'left' | 'right' | 'center';
}

export function UqBadge({ status, score, coverage = 0.90, modelId, tooltipAlign = 'center' }: UqBadgeProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  const getStatusStyles = () => {
    switch (status) {
      case 'in_domain':
        return {
          bg: 'bg-emerald-500/10 dark:bg-emerald-400/10',
          text: 'text-emerald-700 dark:text-emerald-400',
          border: 'border-emerald-500/20 dark:border-emerald-400/20',
          label: 'In Domain',
          dot: 'bg-emerald-500'
        };
      case 'borderline':
        return {
          bg: 'bg-amber-500/10 dark:bg-amber-400/10',
          text: 'text-amber-700 dark:text-amber-400',
          border: 'border-amber-500/20 dark:border-amber-400/20',
          label: 'Borderline',
          dot: 'bg-amber-500'
        };
      case 'out_of_domain':
        return {
          bg: 'bg-rose-500/10 dark:bg-rose-400/10',
          text: 'text-rose-700 dark:text-rose-400',
          border: 'border-rose-500/20 dark:border-rose-400/20',
          label: 'Out of Domain',
          dot: 'bg-rose-500'
        };
      default:
        return {
          bg: 'bg-slate-500/10 dark:bg-slate-400/10',
          text: 'text-slate-700 dark:text-slate-400',
          border: 'border-slate-500/20 dark:border-slate-400/20',
          label: 'Unknown',
          dot: 'bg-slate-500'
        };
    }
  };

  const styles = getStatusStyles();

  const getAlignClass = () => {
    if (tooltipAlign === 'left') return 'left-0 origin-top-left';
    if (tooltipAlign === 'right') return 'right-0 origin-top-right';
    return 'left-1/2 -translate-x-1/2 origin-top';
  };

  return (
    <div
      className="relative inline-block cursor-help select-none"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <span
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium border uppercase tracking-wider transition-all duration-200 ${styles.bg} ${styles.text} ${styles.border}`}
      >
        <span className={`w-1 h-1 rounded-full ${styles.dot} animate-pulse`} />
        {styles.label}
      </span>

      {showTooltip && (
        <div
          className={`absolute top-full mt-2 z-50 w-72 p-3 bg-slate-900 border border-slate-700/50 rounded-lg shadow-xl text-slate-200 text-xs font-normal leading-relaxed backdrop-blur-md animate-fade-in ${getAlignClass()}`}
        >
          <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-slate-800">
            <span className="font-semibold text-slate-100 uppercase text-[10px] tracking-wider">
              Applicability Domain Check
            </span>
            {modelId && (
              <span className="text-[10px] text-slate-500 font-mono">{modelId}</span>
            )}
          </div>

          <div className="space-y-1.5 mb-2.5">
            <div className="flex justify-between">
              <span className="text-slate-400">Status:</span>
              <span className={`font-semibold capitalize ${styles.text}`}>{styles.label}</span>
            </div>
            {score !== undefined && score !== null && (
              <div className="flex justify-between">
                <span className="text-slate-400">Tanimoto Similarity (k=5):</span>
                <span className="font-mono text-slate-100 font-medium">
                  {score.toFixed(3)}
                </span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-slate-400">Conformal Coverage:</span>
              <span className="font-mono text-slate-100 font-medium">
                {(coverage * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div className="p-2 rounded bg-amber-500/5 border border-amber-500/10 text-[10px] text-amber-500 leading-normal">
            <strong>⚠️ Disclaimer:</strong> In-silico screening flag, not an official regulatory determination.
          </div>
        </div>
      )}
    </div>
  );
}
