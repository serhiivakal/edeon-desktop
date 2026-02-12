import React, { useState } from 'react';
import { AlertCircle, HelpCircle } from 'lucide-react';

interface TradeoffMatrixProps {
  tradeoffMatrix: {
    matrix: Record<string, Record<string, number>>;
    p_values: Record<string, Record<string, number>>;
    antagonistic_pairs: Array<[string, string, number, number]>;
    n: number;
  };
}

export const TradeoffMatrix: React.FC<TradeoffMatrixProps> = ({ tradeoffMatrix }) => {
  const [selectedPair, setSelectedPair] = useState<[string, string] | null>(null);

  const endpoints = Object.keys(tradeoffMatrix.matrix || {});

  if (endpoints.length === 0) {
    return null;
  }

  const getColor = (rho: number, p: number) => {
    if (p > 0.05) return 'bg-slate-800/40 text-slate-500';
    if (rho <= -0.5) return 'bg-rose-600/80 text-white font-bold';
    if (rho <= -0.3) return 'bg-rose-500/40 text-rose-200';
    if (rho >= 0.5) return 'bg-emerald-600/80 text-white font-bold';
    if (rho >= 0.3) return 'bg-emerald-500/40 text-emerald-200';
    return 'bg-slate-800/60 text-slate-400';
  };

  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
            Endpoint Trade-Off Surface (Spearman ρ)
          </h4>
          <p className="text-xs text-slate-400 mt-0.5">
            Identify antagonistic pairs where improving one endpoint deteriorates another
          </p>
        </div>
        <div className="flex items-center space-x-3 text-xs">
          <span className="flex items-center space-x-1">
            <span className="w-3 h-3 rounded bg-rose-500/40 border border-rose-500/50"></span>
            <span className="text-slate-400">Antagonistic (ρ &lt; -0.3)</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-3 h-3 rounded bg-emerald-500/40 border border-emerald-500/50"></span>
            <span className="text-slate-400">Synergistic (ρ &gt; 0.3)</span>
          </span>
        </div>
      </div>

      {tradeoffMatrix.antagonistic_pairs.length > 0 && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg space-y-1">
          <div className="flex items-center space-x-2 text-xs font-semibold text-rose-300">
            <AlertCircle className="w-4 h-4" />
            <span>Significant Trade-Offs Detected</span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {tradeoffMatrix.antagonistic_pairs.map(([ep1, ep2, rho]) => (
              <button
                key={`${ep1}-${ep2}`}
                onClick={() => setSelectedPair([ep1, ep2])}
                className="px-2 py-1 bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/30 rounded text-xs text-rose-200 font-mono transition-colors"
              >
                {ep1} ↔ {ep2} (ρ = {rho.toFixed(2)})
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Heatmap Grid */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr>
              <th className="p-2 text-left font-mono text-slate-500 border-b border-slate-800">Endpoint</th>
              {endpoints.map((ep) => (
                <th
                  key={ep}
                  className="p-2 text-center font-mono text-slate-400 border-b border-slate-800 max-w-[80px] truncate"
                  title={ep}
                >
                  {ep}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {endpoints.map((ep1) => (
              <tr key={ep1} className="hover:bg-slate-800/30">
                <td className="p-2 font-mono text-slate-300 font-medium border-b border-slate-800/50">{ep1}</td>
                {endpoints.map((ep2) => {
                  const rho = tradeoffMatrix.matrix[ep1]?.[ep2] ?? 0;
                  const p = tradeoffMatrix.p_values[ep1]?.[ep2] ?? 1;
                  const isSelf = ep1 === ep2;

                  return (
                    <td
                      key={ep2}
                      onClick={() => !isSelf && setSelectedPair([ep1, ep2])}
                      className={`p-2 text-center border border-slate-800/30 font-mono transition-colors ${
                        isSelf ? 'bg-slate-900 text-slate-600' : `${getColor(rho, p)} cursor-pointer hover:opacity-80`
                      }`}
                      title={isSelf ? ep1 : `${ep1} vs ${ep2}: ρ = ${rho.toFixed(3)}, p = ${p.toFixed(3)}`}
                    >
                      {isSelf ? '-' : rho.toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedPair && (
        <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs flex justify-between items-center">
          <div>
            <span className="text-slate-400">Inspecting Correlation: </span>
            <span className="font-mono text-indigo-300 font-semibold">{selectedPair[0]}</span>
            <span className="text-slate-500"> vs </span>
            <span className="font-mono text-indigo-300 font-semibold">{selectedPair[1]}</span>
            <span className="text-slate-400 ml-3">
              ρ = {tradeoffMatrix.matrix[selectedPair[0]]?.[selectedPair[1]]?.toFixed(3)} (p = {tradeoffMatrix.p_values[selectedPair[0]]?.[selectedPair[1]]?.toFixed(4)})
            </span>
          </div>
          <button
            onClick={() => setSelectedPair(null)}
            className="text-slate-500 hover:text-slate-300"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
};
