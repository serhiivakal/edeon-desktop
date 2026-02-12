import React, { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';

interface CliffsPanelProps {
  modelId: string;
  modelType: 'regression' | 'classification';
  cliffs: any[];
  onHighlightPoints: (indices: number[]) => void;
  onRecompute: (newCliffs: any[]) => void;
}

export default function CliffsPanel({
  modelId,
  modelType,
  cliffs,
  onHighlightPoints,
  onRecompute
}: CliffsPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showPopover, setShowPopover] = useState(false);
  const [simThreshold, setSimThreshold] = useState(0.85);
  const [actGap, setActGap] = useState(1.0);
  const [isRecomputing, setIsRecomputing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedPairIndex, setSelectedPairIndex] = useState<number | null>(null);

  const activeCliffs = Array.isArray(cliffs) ? cliffs : [];

  const handleRecompute = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsRecomputing(true);
    setErrorMsg(null);
    try {
      const result = await invoke<any[]>('recompute_cliffs', {
        modelId,
        similarityThreshold: simThreshold,
        activityGap: actGap
      });
      onRecompute(result);
      setShowPopover(false);
    } catch (err) {
      console.error(err);
      setErrorMsg(typeof err === 'string' ? err : 'Recomputation failed.');
    } finally {
      setIsRecomputing(false);
    }
  };

  const handleCardClick = (pair: any, index: number) => {
    setSelectedPairIndex(index);
    onHighlightPoints([pair.i, pair.j]);
    
    // Smooth scroll to the parity plot
    const element = document.querySelector('.plot-container-card');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  if (activeCliffs.length === 0) {
    return (
      <div className="relative p-4 border rounded-xl bg-[var(--color-bg)] border-[var(--color-border)] text-xs text-[var(--color-text-300)] flex flex-wrap items-center justify-between gap-4 transition-all duration-200">
        <div className="flex items-center gap-2">
          <span className="text-amber-500 font-bold text-sm">⚠</span>
          <span>
            No activity cliffs detected at the current thresholds (Tanimoto &gt; 0.85, gap &gt; 1).
          </span>
        </div>
        {modelId && (
          <>
            <button
              onClick={() => setShowPopover(!showPopover)}
              className="text-[var(--color-brand-600)] hover:text-[var(--color-brand-700)] font-semibold underline focus:outline-none transition-colors"
            >
              Adjust thresholds
            </button>

            {showPopover && (
              <div className="absolute right-4 top-12 z-20 w-80 p-4 rounded-xl border bg(--color-surface)] border-[var(--color-border)] shadow-2xl animate-fade-in space-y-4">
                <h4 className="font-bold text-[var(--color-text-100)] text-sm">Cliffs Detection Thresholds</h4>
                <form onSubmit={handleRecompute} className="space-y-4">
                  <div className="space-y-1">
                    <label className="flex justify-between font-semibold text-[10px] text-[var(--color-text-300)] uppercase tracking-wider">
                      <span>Similarity (Tanimoto)</span>
                      <span className="text-[var(--color-brand-600)] font-bold">{simThreshold.toFixed(2)}</span>
                    </label>
                    <input
                      type="range"
                      min="0.50"
                      max="0.99"
                      step="0.01"
                      value={simThreshold}
                      onChange={(e) => setSimThreshold(parseFloat(e.target.value))}
                      className="w-full accent-[var(--color-brand-600)]"
                    />
                  </div>

                  {modelType === 'regression' && (
                    <div className="space-y-1">
                      <label className="flex justify-between font-semibold text-[10px] text-[var(--color-text-300)] uppercase tracking-wider">
                        <span>Activity Gap (Δy)</span>
                        <span className="text-[var(--color-brand-600)] font-bold">{actGap.toFixed(1)}</span>
                      </label>
                      <input
                        type="range"
                        min="0.1"
                        max="5.0"
                        step="0.1"
                        value={actGap}
                        onChange={(e) => setActGap(parseFloat(e.target.value))}
                        className="w-full accent-[var(--color-brand-600)]"
                      />
                    </div>
                  )}

                  {errorMsg && (
                    <p className="text-red-500 font-medium text-[10px] bg-red-50 p-2 rounded border border-red-100">{errorMsg}</p>
                  )}

                  <div className="flex gap-2 justify-end text-xs">
                    <button
                      type="button"
                      onClick={() => setShowPopover(false)}
                      className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] font-semibold transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isRecomputing}
                      className="px-3 py-1.5 rounded-lg bg-[var(--color-brand-600)] hover:bg-[var(--color-brand-700)] text-white font-semibold transition-colors flex items-center gap-1 disabled:opacity-50"
                    >
                      {isRecomputing ? (
                        <>
                          <span className="animate-spin h-3.5 w-3.5 border-2 border-white border-t-transparent rounded-full"></span>
                          Updating...
                        </>
                      ) : (
                        'Recompute'
                      )}
                    </button>
                  </div>
                </form>
              </div>
            )}
          </>
        )}
      </div>
    );
  }

  return (
    <div className="border rounded-xl border-amber-200 bg-amber-50/20 overflow-hidden transition-all duration-300 shadow-sm hover:shadow">
      {/* Warning Header Card */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-amber-50/40 select-none transition-colors border-b border-amber-100"
      >
        <div className="flex items-center gap-2.5">
          <span className="text-amber-500 font-bold text-base animate-pulse">⚠</span>
          <span className="text-sm font-bold text-amber-900">
            Activity Cliffs Detected ({activeCliffs.length} pairs)
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-semibold border border-amber-200">
            High Severity Risk
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-amber-800 hover:underline">
            {isExpanded ? '[Click to collapse]' : '[Click to expand]'}
          </span>
          <span className={`text-amber-600 transform transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
            ▼
          </span>
        </div>
      </div>

      {isExpanded && (
        <div className="p-4 space-y-4 bg-[var(--color-surface)] border-t border-[var(--color-border)]">
          {/* Controls Bar */}
          <div className="flex items-center justify-between gap-4">
            <p className="text-xs text-[var(--color-text-400)] max-w-xl">
              Pairs of structurally highly similar compounds (Tanimoto &gt; 0.85) displaying massive differences in activity. Hover cards for full details, click cards to highlight coordinates in the Parity plot.
            </p>
            {modelId && (
              <div className="relative">
                <button
                  onClick={() => setShowPopover(!showPopover)}
                  className="px-3 py-1.5 text-xs rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] hover:bg-[var(--color-surface-hover)] font-semibold text-[var(--color-text-200)] transition-all flex items-center gap-1.5 focus:outline-none"
                >
                  <span>⚙</span> Adjust thresholds
                </button>

                {showPopover && (
                  <div className="absolute right-0 top-10 z-20 w-80 p-4 rounded-xl border bg-[var(--color-surface)] border-[var(--color-border)] shadow-2xl animate-fade-in space-y-4">
                    <h4 className="font-bold text-[var(--color-text-100)] text-sm">Cliffs Detection Thresholds</h4>
                    <form onSubmit={handleRecompute} className="space-y-4">
                      <div className="space-y-1">
                        <label className="flex justify-between font-semibold text-[10px] text-[var(--color-text-300)] uppercase tracking-wider">
                          <span>Similarity (Tanimoto)</span>
                          <span className="text-[var(--color-brand-600)] font-bold">{simThreshold.toFixed(2)}</span>
                        </label>
                        <input
                          type="range"
                          min="0.50"
                          max="0.99"
                          step="0.01"
                          value={simThreshold}
                          onChange={(e) => setSimThreshold(parseFloat(e.target.value))}
                          className="w-full accent-[var(--color-brand-600)]"
                        />
                      </div>

                      {modelType === 'regression' && (
                        <div className="space-y-1">
                          <label className="flex justify-between font-semibold text-[10px] text-[var(--color-text-300)] uppercase tracking-wider">
                            <span>Activity Gap (Δy)</span>
                            <span className="text-[var(--color-brand-600)] font-bold">{actGap.toFixed(1)}</span>
                          </label>
                          <input
                            type="range"
                            min="0.1"
                            max="5.0"
                            step="0.1"
                            value={actGap}
                            onChange={(e) => setActGap(parseFloat(e.target.value))}
                            className="w-full accent-[var(--color-brand-600)]"
                          />
                        </div>
                      )}

                      {errorMsg && (
                        <p className="text-red-500 font-medium text-[10px] bg-red-50 p-2 rounded border border-red-100">{errorMsg}</p>
                      )}

                      <div className="flex gap-2 justify-end text-xs">
                        <button
                          type="button"
                          onClick={() => setShowPopover(false)}
                          className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] font-semibold transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={isRecomputing}
                          className="px-3 py-1.5 rounded-lg bg-[var(--color-brand-600)] hover:bg-[var(--color-brand-700)] text-white font-semibold transition-colors flex items-center gap-1 disabled:opacity-50"
                        >
                          {isRecomputing ? (
                            <>
                              <span className="animate-spin h-3.5 w-3.5 border-2 border-white border-t-transparent rounded-full"></span>
                              Updating...
                            </>
                          ) : (
                            'Recompute'
                          )}
                        </button>
                      </div>
                    </form>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Horizontally Scrolling Card Row */}
          <div className="flex overflow-x-auto gap-4 py-2 px-1 scrollbar-thin scrollbar-thumb-rounded scrollbar-thumb-[var(--color-border)]">
            {activeCliffs.map((pair, idx) => {
              const label = modelType === 'regression' ? 'Δy' : 'Class Diff';
              const gapVal = modelType === 'regression' ? pair.gap.toFixed(2) : 'Different';
              const isSelected = selectedPairIndex === idx;

              return (
                <div
                  key={`${pair.i}-${pair.j}-${idx}`}
                  onClick={() => handleCardClick(pair, idx)}
                  className={`flex-shrink-0 w-64 p-3.5 border rounded-xl bg-[var(--color-bg)] transition-all duration-200 cursor-pointer select-none hover:-translate-y-0.5 hover:shadow-md flex flex-col justify-between space-y-3 ${
                    isSelected
                      ? 'border-[var(--color-brand-600)] ring-2 ring-[var(--color-brand-500)]/20 shadow-sm'
                      : 'border-[var(--color-border)] hover:border-[var(--color-text-400)]'
                  }`}
                  title={`Compound A (index ${pair.i}):\nSMILES: ${pair.smiles_i}\nActivity: ${pair.activity_i.toFixed(3)}\n\nCompound B (index ${pair.j}):\nSMILES: ${pair.smiles_j}\nActivity: ${pair.activity_j.toFixed(3)}\n\nSimilarity: ${pair.similarity.toFixed(4)}\nSeverity: ${pair.severity.toFixed(4)}`}
                >
                  {/* Thumbnails Row */}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="relative border rounded-lg bg-white p-1 flex items-center justify-center h-24 shadow-sm overflow-hidden group">
                      {pair.thumb_i ? (
                        <img
                          src={pair.thumb_i}
                          alt={`Compound ${pair.i}`}
                          className="max-h-full max-w-full object-contain"
                        />
                      ) : (
                        <span className="text-[10px] text-gray-400">No image</span>
                      )}
                      <div className="absolute bottom-0.5 left-0.5 bg-black/60 text-white font-extrabold text-[8px] px-1 rounded">
                        A ({pair.i})
                      </div>
                    </div>

                    <div className="relative border rounded-lg bg-white p-1 flex items-center justify-center h-24 shadow-sm overflow-hidden group">
                      {pair.thumb_j ? (
                        <img
                          src={pair.thumb_j}
                          alt={`Compound ${pair.j}`}
                          className="max-h-full max-w-full object-contain"
                        />
                      ) : (
                        <span className="text-[10px] text-gray-400">No image</span>
                      )}
                      <div className="absolute bottom-0.5 left-0.5 bg-black/60 text-white font-extrabold text-[8px] px-1 rounded">
                        B ({pair.j})
                      </div>
                    </div>
                  </div>

                  {/* Card Info Section */}
                  <div className="text-[11px] space-y-1 text-[var(--color-text-200)]">
                    <div className="flex justify-between font-semibold">
                      <span>Sim: <span className="text-[var(--color-brand-600)] font-bold">{pair.similarity.toFixed(2)}</span></span>
                      <span>{label}: <span className="text-amber-600 font-bold">{gapVal}</span></span>
                    </div>
                    <div className="flex justify-between text-[10px] text-[var(--color-text-400)]">
                      <span>A: <span className="font-semibold">{pair.activity_i.toFixed(2)}</span></span>
                      <span>B: <span className="font-semibold">{pair.activity_j.toFixed(2)}</span></span>
                    </div>
                    <div className="text-[9px] text-[var(--color-text-400)] pt-1 border-t border-[var(--color-border)] truncate">
                      {pair.smiles_i}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
