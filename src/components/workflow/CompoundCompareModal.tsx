import { useState, useEffect, useMemo } from 'react';
import { invoke } from '@tauri-apps/api/core';
import type { WorkflowResultRecord, Prediction } from '../../types';

interface CompoundCompareModalProps {
  compounds: WorkflowResultRecord[];
  allResults: WorkflowResultRecord[];
  onClose: () => void;
}

const PREDICTION_ENDPOINTS = [
  { key: 'bee_acute_oral_ld50', label: 'Honeybee Oral LD50', icon: '🐝' },
  { key: 'bee_acute_contact_ld50', label: 'Honeybee Contact LD50', icon: '🐝' },
  { key: 'earthworm_acute_lc50', label: 'Earthworm LC50', icon: '🪱' },
  { key: 'daphnia_acute_ec50', label: 'Daphnia EC50', icon: '🦐' },
  { key: 'fish_acute_lc50', label: 'Fish LC50', icon: '🐟' },
  { key: 'bird_acute_oral_ld50', label: 'Bird Oral LD50', icon: '🦆' },
  { key: 'rat_acute_oral_ld50', label: 'Rat Oral LD50', icon: '🐀' },
  { key: 'soil_koc', label: 'Soil Koc', icon: '🌍' },
  { key: 'soil_dt50', label: 'Soil DT50', icon: '⏱' },
  { key: 'gus_index', label: 'GUS Index', icon: '💧' },
];

function formatPredValue(pred: Prediction): string {
  if (pred.value.kind === 'numeric') return `${pred.value.numeric.toFixed(2)} ${pred.units}`;
  if (pred.value.kind === 'categorical') return pred.value.categorical;
  if (pred.value.kind === 'binary') return pred.value.binary ? 'Positive' : 'Negative';
  return '—';
}

function numericPredValue(pred: Prediction | null | undefined): number | null {
  if (!pred) return null;
  if (pred.value.kind === 'numeric') return pred.value.numeric;
  return null;
}

function riskColor(level: string | null | undefined) {
  if (!level) return 'var(--color-text-400)';
  const l = level.toLowerCase();
  if (l === 'low' || l === 'safe' || l === 'lead') return 'var(--color-brand-700)';
  if (l === 'med' || l === 'moderate' || l === 'candidate') return 'var(--color-amber-700)';
  if (l === 'high' || l === 'danger' || l === 'deprioritize') return 'var(--color-red-700)';
  return 'var(--color-text-600)';
}

/** Determines which value index is "best" (highest) and "worst" (lowest) among non-null values. */
function rankValues(values: (number | null)[]): { bestIdx: number; worstIdx: number } | null {
  let bestIdx = -1, worstIdx = -1;
  let best = -Infinity, worst = Infinity;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v == null) continue;
    if (v > best) { best = v; bestIdx = i; }
    if (v < worst) { worst = v; worstIdx = i; }
  }
  if (bestIdx === -1) return null;
  if (bestIdx === worstIdx) return null; // all equal
  return { bestIdx, worstIdx };
}

export function CompoundCompareModal({ compounds: initialCompounds, allResults, onClose }: CompoundCompareModalProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set(initialCompounds.map(c => c.id)));
  const [svgs, setSvgs] = useState<Record<string, string>>({});
  const [predictions, setPredictions] = useState<Record<string, Record<string, Prediction | null>>>({});
  const [loadingPreds, setLoadingPreds] = useState(true);
  const [showPicker, setShowPicker] = useState(false);

  const compounds = useMemo(() => {
    return allResults.filter(r => selectedIds.has(r.id));
  }, [selectedIds, allResults]);

  // Fetch SVGs
  useEffect(() => {
    compounds.forEach(c => {
      if (svgs[c.id] || !c.smiles) return;
      invoke<string>('depict_compound', { smiles: c.smiles })
        .then(svg => setSvgs(prev => ({ ...prev, [c.id]: svg })))
        .catch(() => {});
    });
  }, [compounds]);

  // Fetch predictions for all compounds
  useEffect(() => {
    let active = true;
    setLoadingPreds(true);

    const fetchAll = async () => {
      const allPreds: Record<string, Record<string, Prediction | null>> = {};

      for (const compound of compounds) {
        if (!compound.smiles) continue;
        const compPreds: Record<string, Prediction | null> = {};

        await Promise.all(
          PREDICTION_ENDPOINTS.map(async (ep) => {
            try {
              const response = await invoke<Prediction[]>('model_predict', {
                endpoint: ep.key,
                smiles: [compound.smiles],
                preferredTier: null,
              });
              compPreds[ep.key] = response?.[0] ?? null;
            } catch {
              compPreds[ep.key] = null;
            }
          })
        );

        allPreds[compound.id] = compPreds;
      }

      if (active) {
        setPredictions(allPreds);
        setLoadingPreds(false);
      }
    };

    fetchAll();
    return () => { active = false; };
  }, [compounds.map(c => c.id).join(',')]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showPicker) setShowPicker(false);
        else onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, showPicker]);

  const toggleCompound = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        if (next.size <= 2) return prev; // minimum 2
        next.delete(id);
      } else {
        if (next.size >= 8) return prev; // max 8
        next.add(id);
      }
      return next;
    });
  };

  /** Helper: render property row with delta highlighting */
  const PropertyRow = ({ label, getValue, higherIsBetter = true }: {
    label: string;
    getValue: (c: WorkflowResultRecord) => number | null | undefined;
    higherIsBetter?: boolean;
  }) => {
    const values = compounds.map(c => getValue(c) ?? null);
    const ranking = rankValues(values);
    return (
      <div className="compare-row">
        <div className="compare-row-label">{label}</div>
        {compounds.map((c, i) => {
          const val = values[i];
          let bg = 'transparent';
          if (ranking && val != null) {
            if (higherIsBetter) {
              if (i === ranking.bestIdx) bg = 'rgba(16, 185, 129, 0.12)';
              if (i === ranking.worstIdx) bg = 'rgba(239, 68, 68, 0.08)';
            } else {
              if (i === ranking.worstIdx) bg = 'rgba(16, 185, 129, 0.12)';
              if (i === ranking.bestIdx) bg = 'rgba(239, 68, 68, 0.08)';
            }
          }
          return (
            <div key={c.id} className="compare-cell" style={{ background: bg }}>
              <span className="compare-cell-value">{val != null ? (typeof val === 'number' ? val.toFixed(2) : val) : '—'}</span>
            </div>
          );
        })}
      </div>
    );
  };

  const PredRow = ({ endpoint }: { endpoint: typeof PREDICTION_ENDPOINTS[0] }) => {
    const values = compounds.map(c => numericPredValue(predictions[c.id]?.[endpoint.key]));
    const ranking = rankValues(values);
    return (
      <div className="compare-row">
        <div className="compare-row-label">{endpoint.icon} {endpoint.label}</div>
        {compounds.map((c, i) => {
          const pred = predictions[c.id]?.[endpoint.key];
          const val = values[i];
          let bg = 'transparent';
          // For toxicological endpoints, higher LD50/LC50/EC50 is better (less toxic)
          if (ranking && val != null) {
            if (i === ranking.bestIdx) bg = 'rgba(16, 185, 129, 0.12)';
            if (i === ranking.worstIdx) bg = 'rgba(239, 68, 68, 0.08)';
          }
          return (
            <div key={c.id} className="compare-cell" style={{ background: bg }}>
              <span className="compare-cell-value" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                {pred ? formatPredValue(pred) : '—'}
              </span>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="detail-modal-overlay" onClick={onClose}>
      <div className="detail-modal compare-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="detail-modal-header">
          <div className="detail-modal-header-left">
            <span className="detail-modal-label">COMPARE COMPOUNDS</span>
            <span style={{ fontSize: '12px', color: 'var(--color-text-400)' }}>
              {compounds.length} compounds selected
            </span>
          </div>
          <div className="detail-modal-header-right">
            <button
              className="compare-add-btn"
              onClick={() => setShowPicker(!showPicker)}
            >
              {showPicker ? '✕ Close' : '+ Add / Remove'}
            </button>
            <button className="detail-modal-close" onClick={onClose} title="Close (Esc)">✕</button>
          </div>
        </div>

        {/* Compound Picker Dropdown */}
        {showPicker && (
          <div className="compare-picker">
            <div className="compare-picker-title">Select compounds to compare (2–8):</div>
            <div className="compare-picker-list">
              {allResults.map(r => (
                <label key={r.id} className="compare-picker-item">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(r.id)}
                    onChange={() => toggleCompound(r.id)}
                  />
                  <span className="compare-picker-name">{r.name}</span>
                  <span className="compare-picker-smiles">{r.smiles?.slice(0, 40)}{(r.smiles?.length ?? 0) > 40 ? '...' : ''}</span>
                  {r.score != null && <span className="compare-picker-score">{r.score.toFixed(1)}</span>}
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Comparison Table */}
        <div className="compare-body">
          {/* Sticky header row with structures */}
          <div className="compare-row compare-header-row">
            <div className="compare-row-label"></div>
            {compounds.map(c => (
              <div key={c.id} className="compare-cell compare-header-cell">
                <div className="compare-header-structure">
                  {svgs[c.id] ? (
                    <div dangerouslySetInnerHTML={{ __html: svgs[c.id] }} />
                  ) : (
                    <div className="compare-structure-placeholder">⏳</div>
                  )}
                </div>
                <div className="compare-header-name">{c.name}</div>
                <div className="compare-header-smiles selectable">{c.smiles?.slice(0, 30)}{(c.smiles?.length ?? 0) > 30 ? '...' : ''}</div>
                {c.mpo && (
                  <div className={`compare-rank rank-${c.mpo.rank_category.toLowerCase()}`}>
                    {c.mpo.rank_category} · {c.score?.toFixed(1)}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Section: Properties */}
          <div className="compare-section-title">Physicochemical Properties</div>
          <PropertyRow label="MW (g/mol)" getValue={c => c.mol_weight} higherIsBetter={false} />
          <PropertyRow label="LogP" getValue={c => c.logp} />
          <PropertyRow label="TPSA (Å²)" getValue={c => c.tpsa} />
          <PropertyRow label="HBD" getValue={c => c.hbd} higherIsBetter={false} />
          <PropertyRow label="HBA" getValue={c => c.hba} higherIsBetter={false} />
          <PropertyRow label="Rotatable Bonds" getValue={c => c.rotatable_bonds} higherIsBetter={false} />

          {/* Section: Workflow Scores */}
          <div className="compare-section-title">Workflow Assessment</div>
          <div className="compare-row">
            <div className="compare-row-label">Pesticide-Likeness</div>
            {compounds.map(c => (
              <div key={c.id} className="compare-cell">
                <span style={{ color: riskColor(c.pesticide_likeness), fontWeight: 600 }}>
                  {c.pesticide_likeness_disabled ? 'Excluded' : c.pesticide_likeness ?? '—'}
                </span>
              </div>
            ))}
          </div>
          <div className="compare-row">
            <div className="compare-row-label">Toxicity Level</div>
            {compounds.map(c => (
              <div key={c.id} className="compare-cell">
                <span style={{ color: riskColor(c.toxicity?.overall_level), fontWeight: 600 }}>
                  {c.toxicity?.disabled ? 'Excluded' : c.toxicity?.overall_level ?? '—'}
                </span>
              </div>
            ))}
          </div>
          <div className="compare-row">
            <div className="compare-row-label">Selectivity (min)</div>
            {compounds.map(c => (
              <div key={c.id} className="compare-cell">
                <span style={{ color: riskColor(c.selectivity?.overall_level), fontWeight: 600 }}>
                  {c.selectivity?.disabled ? 'Excluded' : c.selectivity ? `${c.selectivity.min_selectivity}×` : '—'}
                </span>
              </div>
            ))}
          </div>
          <div className="compare-row">
            <div className="compare-row-label">Resistance Risk</div>
            {compounds.map(c => (
              <div key={c.id} className="compare-cell">
                <span style={{ color: riskColor(c.resistance?.level), fontWeight: 600 }}>
                  {c.resistance?.disabled ? 'Excluded' : c.resistance ? `${c.resistance.level} (${c.resistance.risk_score}/10)` : '—'}
                </span>
              </div>
            ))}
          </div>
          <PropertyRow label="MPO Score" getValue={c => c.score} />

          {/* Section: Structural Alerts */}
          <div className="compare-section-title">Structural Alerts</div>
          <div className="compare-row">
            <div className="compare-row-label">PAINS Alerts</div>
            {compounds.map(c => {
              const alerts = (c as any).pains_alerts || [];
              return (
                <div key={c.id} className="compare-cell">
                  {alerts.length > 0 ? (
                    <span style={{ color: 'var(--color-red-700)', fontWeight: 600 }} title={alerts.join(', ')}>
                      ⚠️ {alerts.length} PAINS
                    </span>
                  ) : (
                    <span style={{ color: 'var(--color-brand-700)', fontSize: '11px' }}>None</span>
                  )}
                </div>
              );
            })}
          </div>
          <div className="compare-row">
            <div className="compare-row-label">Reactive Alerts</div>
            {compounds.map(c => {
              const alerts = (c as any).reactive_alerts || [];
              return (
                <div key={c.id} className="compare-cell">
                  {alerts.length > 0 ? (
                    <span style={{ color: 'var(--color-red-700)', fontWeight: 600 }} title={alerts.join(', ')}>
                      ⚡ {alerts.length} reactive
                    </span>
                  ) : (
                    <span style={{ color: 'var(--color-brand-700)', fontSize: '11px' }}>None</span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Section: QSAR Predictions */}
          <div className="compare-section-title">
            QSAR Predictions
            {loadingPreds && <span className="detail-loading-dot"> ⏳</span>}
          </div>
          {PREDICTION_ENDPOINTS.map(ep => (
            <PredRow key={ep.key} endpoint={ep} />
          ))}
        </div>
      </div>
    </div>
  );
}
