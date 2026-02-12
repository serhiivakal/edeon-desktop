import React from 'react';
import { AttritionResult } from '../../store/bottleneckStore';
import { Filter, AlertTriangle } from 'lucide-react';

interface AttritionBottleneckProps {
  attrition: AttritionResult;
}

export const AttritionBottleneck: React.FC<AttritionBottleneckProps> = ({ attrition }) => {
  if (!attrition || attrition.gates.length === 0) {
    return null;
  }

  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-amber-400" />
          <h4 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
            Workflow Attrition Bottleneck
          </h4>
        </div>
        {attrition.dominant_gate && (
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-medium">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Dominant Bottleneck: <strong>{attrition.dominant_gate}</strong> ({(attrition.dominant_attrition * 100).toFixed(0)}% drop)</span>
          </div>
        )}
      </div>

      <div className="space-y-2">
        {attrition.gates.map((gate) => {
          const isDominant = gate.gate_name === attrition.dominant_gate;
          const failPercent = gate.attrition_rate * 100;

          return (
            <div
              key={gate.gate_name}
              className={`p-3 rounded-lg border transition-all ${
                isDominant
                  ? 'bg-rose-950/20 border-rose-500/40'
                  : 'bg-slate-950/40 border-slate-800/80'
              }`}
            >
              <div className="flex justify-between items-center text-xs mb-1.5">
                <span className={`font-semibold ${isDominant ? 'text-rose-300' : 'text-slate-200'}`}>
                  {gate.gate_name}
                </span>
                <span className="font-mono text-slate-400">
                  Passed: {gate.n_passed}/{gate.n_input} ({failPercent.toFixed(1)}% failed)
                </span>
              </div>

              {/* Waterfall progress bar */}
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden flex">
                <div
                  className="h-full bg-emerald-500 transition-all duration-300"
                  style={{ width: `${(100 - failPercent)}%` }}
                  title={`Passed: ${gate.n_passed}`}
                />
                <div
                  className={`h-full ${isDominant ? 'bg-rose-500 animate-pulse' : 'bg-rose-900/60'}`}
                  style={{ width: `${failPercent}%` }}
                  title={`Failed: ${gate.n_failed}`}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex justify-between items-center text-xs text-slate-400 border-t border-slate-800/80 pt-3">
        <span>Initial Portfolio: <strong>{attrition.total_input}</strong> compounds</span>
        <span>Surviving Leads: <strong>{attrition.total_output}</strong></span>
        <span>Overall Attrition: <strong>{(attrition.overall_attrition * 100).toFixed(1)}%</strong></span>
      </div>
    </div>
  );
};
