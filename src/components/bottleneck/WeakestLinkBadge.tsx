import React from 'react';
import { CompoundBottleneck, BottleneckKind } from '../../store/bottleneckStore';
import { AlertCircle, ShieldAlert, Zap } from 'lucide-react';

interface WeakestLinkBadgeProps {
  bottleneck: CompoundBottleneck;
  compact?: boolean;
}

const KIND_STYLES: Record<BottleneckKind, { bg: string; text: string; border: string; icon: React.ComponentType<{ className?: string }> }> = {
  chemical: {
    bg: 'bg-rose-500/10',
    text: 'text-rose-400',
    border: 'border-rose-500/30',
    icon: ShieldAlert,
  },
  epistemic: {
    bg: 'bg-amber-500/10',
    text: 'text-amber-400',
    border: 'border-amber-500/30',
    icon: AlertCircle,
  },
  distractor: {
    bg: 'bg-slate-500/10',
    text: 'text-slate-400',
    border: 'border-slate-500/30',
    icon: Zap,
  },
};

export const WeakestLinkBadge: React.FC<WeakestLinkBadgeProps> = ({ bottleneck, compact = false }) => {
  const style = KIND_STYLES[bottleneck.kind] || KIND_STYLES.distractor;
  const Icon = style.icon;

  if (compact) {
    return (
      <span
        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium border ${style.bg} ${style.text} ${style.border}`}
        title={`Weakest Link: ${bottleneck.weakest_endpoint} (d=${bottleneck.weakest_desirability.toFixed(2)}) — ${bottleneck.reason}`}
      >
        <Icon className="w-3 h-3" />
        <span className="font-mono">{bottleneck.weakest_endpoint}</span>
      </span>
    );
  }

  return (
    <div className={`p-3 rounded-lg border ${style.border} ${style.bg} space-y-1.5`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-1.5">
          <Icon className={`w-4 h-4 ${style.text}`} />
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">Weakest Link Endpoint</span>
        </div>
        <span className={`px-2 py-0.5 text-[10px] rounded border uppercase font-semibold ${style.text} ${style.border}`}>
          {bottleneck.kind}
        </span>
      </div>

      <div className="flex items-baseline justify-between pt-1">
        <span className="text-sm font-bold text-slate-100 font-mono">{bottleneck.weakest_endpoint}</span>
        <span className="text-xs font-mono text-slate-400">
          Desirability: <strong className="text-slate-200">{bottleneck.weakest_desirability.toFixed(3)}</strong>
        </span>
      </div>

      <p className="text-xs text-slate-400 pt-0.5">{bottleneck.reason}</p>
    </div>
  );
};
