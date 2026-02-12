import React from 'react';
import { EndpointResult, BottleneckKind } from '../../store/bottleneckStore';

interface LeverageChartProps {
  endpoints: EndpointResult[];
  selectedEndpoint?: string | null;
  onSelectEndpoint?: (endpoint: string) => void;
}

const COLOR_MAP: Record<BottleneckKind, string> = {
  chemical: '#f43f5e',   // rose-500
  epistemic: '#f59e0b',  // amber-500
  distractor: '#64748b', // slate-500
};

export const LeverageChart: React.FC<LeverageChartProps> = ({
  endpoints,
  selectedEndpoint,
  onSelectEndpoint,
}) => {
  const maxLeverage = Math.max(...endpoints.map((e) => e.leverage_ci[1]), 0.01);

  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
          Endpoint Leverage Profile (Sensitivity Ranking)
        </h4>
        <div className="flex items-center space-x-4 text-xs">
          <span className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
            <span className="text-slate-400">Chemical</span>
          </span>
          <span className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
            <span className="text-slate-400">Epistemic</span>
          </span>
          <span className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-500"></span>
            <span className="text-slate-400">Distractor</span>
          </span>
        </div>
      </div>

      <div className="space-y-3">
        {endpoints.map((ep) => {
          const barWidthPercent = (ep.leverage / maxLeverage) * 100;
          const ciLeftPercent = (ep.leverage_ci[0] / maxLeverage) * 100;
          const ciRightPercent = (ep.leverage_ci[1] / maxLeverage) * 100;
          const isSelected = selectedEndpoint === ep.endpoint;

          return (
            <div
              key={ep.endpoint}
              onClick={() => onSelectEndpoint && onSelectEndpoint(ep.endpoint)}
              className={`p-2.5 rounded-lg border transition-all cursor-pointer ${
                isSelected
                  ? 'border-indigo-500 bg-indigo-500/10'
                  : 'border-slate-800/80 bg-slate-950/40 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between text-xs mb-1.5">
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-slate-500 w-5">#{ep.rank}</span>
                  <span className="font-medium text-slate-200">{ep.display_name}</span>
                  <span className="text-[10px] text-slate-500 font-mono">({ep.reliability})</span>
                </div>
                <div className="flex items-center space-x-3 font-mono">
                  <span className="text-slate-400">d={ep.mean_desirability.toFixed(2)}</span>
                  <span className="font-semibold text-slate-100">+{ep.leverage.toFixed(4)}</span>
                </div>
              </div>

              {/* Custom Bar with CI error bar overlay */}
              <div className="relative h-4 bg-slate-800/60 rounded overflow-hidden">
                {/* Main bar */}
                <div
                  className="h-full rounded transition-all duration-300"
                  style={{
                    width: `${Math.max(barWidthPercent, 2)}%`,
                    backgroundColor: COLOR_MAP[ep.kind],
                    opacity: 0.85,
                  }}
                />

                {/* CI Error bar overlay */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 h-1 bg-slate-100/70"
                  style={{
                    left: `${Math.max(ciLeftPercent, 0)}%`,
                    width: `${Math.max(ciRightPercent - ciLeftPercent, 1)}%`,
                  }}
                >
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 h-2.5 w-0.5 bg-slate-100" />
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 h-2.5 w-0.5 bg-slate-100" />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
