import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import type { WorkflowResultRecord, Prediction } from '../../types';

interface CompoundDetailModalProps {
  compound: WorkflowResultRecord;
  onClose: () => void;
}

const PREDICTION_ENDPOINTS = [
  { key: 'bee_acute_oral_ld50', label: 'Honeybee Oral LD50', icon: '🐝', category: 'ecotox' },
  { key: 'bee_acute_contact_ld50', label: 'Honeybee Contact LD50', icon: '🐝', category: 'ecotox' },
  { key: 'earthworm_acute_lc50', label: 'Earthworm LC50', icon: '🪱', category: 'ecotox' },
  { key: 'algae_growth_ec50', label: 'Algae EC50', icon: '🌱', category: 'ecotox' },
  { key: 'daphnia_acute_ec50', label: 'Daphnia EC50', icon: '🦐', category: 'ecotox' },
  { key: 'fish_acute_lc50', label: 'Fish LC50', icon: '🐟', category: 'ecotox' },
  { key: 'bird_acute_oral_ld50', label: 'Bird Oral LD50', icon: '🦆', category: 'ecotox' },
  { key: 'rat_acute_oral_ld50', label: 'Rat Oral LD50', icon: '🐀', category: 'tox' },
  { key: 'soil_koc', label: 'Soil Koc', icon: '🌍', category: 'env' },
  { key: 'soil_dt50', label: 'Soil DT50', icon: '⏱', category: 'env' },
  { key: 'gus_index', label: 'GUS Index', icon: '💧', category: 'env' },
];

function formatPredValue(pred: Prediction): string {
  if (pred.value.kind === 'numeric') {
    return `${pred.value.numeric.toFixed(2)} ${pred.units}`;
  }
  if (pred.value.kind === 'categorical') {
    return pred.value.categorical;
  }
  if (pred.value.kind === 'binary') {
    return pred.value.binary ? 'Positive' : 'Negative';
  }
  return '—';
}

function adStatusColor(status: string): string {
  if (status === 'in') return 'var(--color-brand-700)';
  if (status === 'borderline') return 'var(--color-amber-700)';
  if (status === 'out') return 'var(--color-red-700)';
  return 'var(--color-text-400)';
}

export function CompoundDetailModal({ compound, onClose }: CompoundDetailModalProps) {
  const [svg, setSvg] = useState<string | null>(null);
  const [predictions, setPredictions] = useState<Record<string, Prediction | null>>({});
  const [loadingPreds, setLoadingPreds] = useState(true);

  // Fetch structure SVG
  useEffect(() => {
    if (!compound.smiles) return;
    invoke<string>('depict_compound', { smiles: compound.smiles })
      .then(setSvg)
      .catch(() => setSvg(null));
  }, [compound.smiles]);

  // Fetch all predictions
  useEffect(() => {
    if (!compound.smiles) return;
    let active = true;
    setLoadingPreds(true);

    const fetchAll = async () => {
      const results: Record<string, Prediction | null> = {};
      await Promise.all(
        PREDICTION_ENDPOINTS.map(async (ep) => {
          try {
            const response = await invoke<Prediction[]>('model_predict', {
              endpoint: ep.key,
              smiles: [compound.smiles],
              preferredTier: null,
            });
            results[ep.key] = response?.[0] ?? null;
          } catch {
            results[ep.key] = null;
          }
        })
      );
      if (active) {
        setPredictions(results);
        setLoadingPreds(false);
      }
    };

    fetchAll();
    return () => { active = false; };
  }, [compound.smiles]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const riskColor = (level: string | null | undefined) => {
    if (!level) return 'var(--color-text-400)';
    const l = level.toLowerCase();
    if (l === 'low' || l === 'safe') return 'var(--color-brand-700)';
    if (l === 'med' || l === 'moderate') return 'var(--color-amber-700)';
    if (l === 'high' || l === 'danger') return 'var(--color-red-700)';
    return 'var(--color-text-600)';
  };

  const ecotoxPreds = PREDICTION_ENDPOINTS.filter(e => e.category === 'ecotox');
  const envPreds = PREDICTION_ENDPOINTS.filter(e => e.category === 'env');
  const toxPreds = PREDICTION_ENDPOINTS.filter(e => e.category === 'tox');

  return (
    <div className="detail-modal-overlay" onClick={onClose}>
      <div className="detail-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header Bar */}
        <div className="detail-modal-header">
          <div className="detail-modal-header-left">
            <span className="detail-modal-label">COMPOUND DETAIL</span>
            <h2 className="detail-modal-name">{compound.name}</h2>
            <span className="detail-modal-smiles selectable">{compound.smiles}</span>
          </div>
          <div className="detail-modal-header-right">
            {compound.mpo && (
              <div className={`detail-modal-rank rank-${compound.mpo.rank_category.toLowerCase()}`}>
                {compound.mpo.rank_category}
                <span className="detail-modal-rank-score">{compound.score?.toFixed(1)}</span>
              </div>
            )}
            <button className="detail-modal-close" onClick={onClose} title="Close (Esc)">✕</button>
          </div>
        </div>

        {/* Content Grid */}
        <div className="detail-modal-body">
          {/* Left Column: Structure + Properties */}
          <div className="detail-modal-col">
            {/* Structure */}
            <div className="detail-card">
              <div className="detail-card-title">2D Structure</div>
              <div className="detail-card-structure">
                {svg ? (
                  <div dangerouslySetInnerHTML={{ __html: svg }} />
                ) : (
                  <div className="detail-card-placeholder">Loading structure...</div>
                )}
              </div>
            </div>

            {/* Key Properties */}
            <div className="detail-card">
              <div className="detail-card-title">Physicochemical Properties</div>
              <div className="detail-props-grid">
                {[
                  { label: 'Molecular Weight', value: compound.mol_weight?.toFixed(2), unit: 'g/mol' },
                  { label: 'LogP', value: compound.logp?.toFixed(2), unit: '' },
                  { label: 'TPSA', value: compound.tpsa?.toFixed(1), unit: 'Å²' },
                  { label: 'H-Bond Donors', value: compound.hbd?.toString(), unit: '' },
                  { label: 'H-Bond Acceptors', value: compound.hba?.toString(), unit: '' },
                  { label: 'Rotatable Bonds', value: compound.rotatable_bonds?.toString(), unit: '' },
                ].map(p => (
                  <div key={p.label} className="detail-prop-item">
                    <span className="detail-prop-label">{p.label}</span>
                    <span className="detail-prop-value">{p.value ?? '—'} <span className="detail-prop-unit">{p.unit}</span></span>
                  </div>
                ))}
              </div>
            </div>

            {/* Pesticide-Likeness */}
            <div className="detail-card">
              <div className="detail-card-title">Pesticide-Likeness (Tice Rules)</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                <span className="detail-badge" style={{ color: riskColor(compound.pesticide_likeness), borderColor: riskColor(compound.pesticide_likeness) }}>
                  {compound.pesticide_likeness_disabled ? 'Excluded' : compound.pesticide_likeness ?? '—'}
                </span>
              </div>
              {compound.tice_violations && compound.tice_violations.length > 0 && (
                <div className="detail-violations">
                  <div className="detail-violations-title">Violations:</div>
                  {compound.tice_violations.map((v, i) => (
                    <div key={i} className="detail-violation-item">• {v}</div>
                  ))}
                </div>
              )}
            </div>

            {/* Structural Alerts (PAINS/Reactive) */}
            {(((compound as any).pains_alerts && (compound as any).pains_alerts.length > 0) || ((compound as any).reactive_alerts && (compound as any).reactive_alerts.length > 0)) && (
              <div className="detail-card" style={{ borderColor: 'var(--color-red-200)', background: 'rgba(239, 68, 68, 0.02)' }}>
                <div className="detail-card-title" style={{ color: 'var(--color-red-700)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  ⚠️ Structural Alerts Detected
                </div>
                {(compound as any).pains_alerts && (compound as any).pains_alerts.length > 0 && (
                  <div style={{ marginBottom: '8px' }}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-red-700)' }}>PAINS Alerts:</div>
                    {(compound as any).pains_alerts.map((a: string, i: number) => (
                      <div key={i} style={{ fontSize: '10px', color: 'var(--color-red-600)', marginLeft: '8px', marginTop: '2px' }}>• {a}</div>
                    ))}
                  </div>
                )}
                {(compound as any).reactive_alerts && (compound as any).reactive_alerts.length > 0 && (
                  <div>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-red-700)' }}>Reactive Alerts:</div>
                    {(compound as any).reactive_alerts.map((a: string, i: number) => (
                      <div key={i} style={{ fontSize: '10px', color: 'var(--color-red-600)', marginLeft: '8px', marginTop: '2px' }}>• {a}</div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* MPO Breakdown */}
            {compound.mpo && (
              <div className="detail-card">
                <div className="detail-card-title">MPO Scoring Breakdown</div>
                <div className="detail-mpo-grid">
                  {Object.entries(compound.mpo.breakdown).map(([key, val]) => {
                    const pct = Math.min(100, Math.max(0, (val as number) * 10));
                    return (
                      <div key={key} className="detail-mpo-row">
                        <span className="detail-mpo-label">{key.replace(/_/g, ' ')}</span>
                        <div className="detail-mpo-bar-bg">
                          <div
                            className="detail-mpo-bar-fill"
                            style={{
                              width: `${pct}%`,
                              background: pct >= 70 ? 'var(--color-brand-600)' : pct >= 40 ? 'var(--color-amber-500)' : 'var(--color-red-500)',
                            }}
                          />
                        </div>
                        <span className="detail-mpo-value">{(val as number).toFixed(1)}</span>
                      </div>
                    );
                  })}
                  <div className="detail-mpo-total">
                    <span>Composite Score</span>
                    <span style={{ fontWeight: 700, fontSize: '16px', color: 'var(--color-brand-700)' }}>
                      {compound.score?.toFixed(1)}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Predictions */}
          <div className="detail-modal-col">
            {/* Toxicity Profile */}
            {compound.toxicity && !compound.toxicity.disabled && (
              <div className="detail-card">
                <div className="detail-card-title">
                  Toxicity Profile
                  <span className="detail-badge-inline" style={{ color: riskColor(compound.toxicity.overall_level), borderColor: riskColor(compound.toxicity.overall_level) }}>
                    {compound.toxicity.overall_level}
                  </span>
                </div>
                <div className="detail-prediction-table">
                  <div className="detail-pred-header">
                    <span>Organism</span>
                    <span>Level</span>
                    <span>Detail</span>
                  </div>
                  {compound.toxicity.predictions.map((tox) => (
                    <div key={tox.organism} className="detail-pred-row">
                      <span className="detail-pred-organism">{tox.organism} {tox.organism_latin ? <em>({tox.organism_latin})</em> : ''}</span>
                      <span style={{ color: riskColor(tox.level), fontWeight: 600 }}>{tox.level}</span>
                      <span className="detail-pred-detail">{tox.detail}</span>
                    </div>
                  ))}
                </div>
                {compound.toxicity.applicability_domain && compound.toxicity.applicability_domain.status !== 'in_domain' && (
                  <div className="detail-ad-warning">
                    ⚠ {compound.toxicity.applicability_domain.status === 'out_of_domain' ? 'Outside' : 'Borderline'} Applicability Domain
                    · Confidence: {(compound.toxicity.applicability_domain.confidence * 100).toFixed(0)}%
                  </div>
                )}
              </div>
            )}

            {/* Selectivity Profile */}
            {compound.selectivity && !compound.selectivity.disabled && (
              <div className="detail-card">
                <div className="detail-card-title">
                  Off-Target Selectivity
                  <span className="detail-badge-inline" style={{ color: riskColor(compound.selectivity.overall_level), borderColor: riskColor(compound.selectivity.overall_level) }}>
                    {compound.selectivity.min_selectivity}× min
                  </span>
                </div>
                <div className="detail-selectivity-grid">
                  {compound.selectivity.profiles.map((sel) => (
                    <div key={sel.organism} className={`detail-sel-card detail-sel-${sel.level}`}>
                      <div className="detail-sel-organism">{sel.organism}</div>
                      <div className="detail-sel-value">{sel.selectivity_index}×</div>
                      <div className="detail-sel-detail">{sel.detail}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Resistance Risk */}
            {compound.resistance && !compound.resistance.disabled && (
              <div className="detail-card">
                <div className="detail-card-title">
                  Resistance Risk
                  <span className="detail-badge-inline" style={{ color: riskColor(compound.resistance.level), borderColor: riskColor(compound.resistance.level) }}>
                    {compound.resistance.level} ({compound.resistance.risk_score}/10)
                  </span>
                </div>
                <div className="detail-prediction-table">
                  <div className="detail-pred-header">
                    <span>Factor</span>
                    <span>Assessment</span>
                  </div>
                  {compound.resistance.factors.map((f, i) => (
                    <div key={i} className="detail-pred-row">
                      <span style={{ fontWeight: 500 }}>{f.factor}</span>
                      <span className="detail-pred-detail">{f.assessment}</span>
                    </div>
                  ))}
                </div>
                {compound.resistance.moa_classification && (
                  <div className="detail-moa-badge">
                    <span className="detail-moa-tag">{compound.resistance.moa_classification.classification}</span>
                    <span className="detail-moa-group">Group {compound.resistance.moa_classification.group}</span>
                    <span className="detail-moa-name">{compound.resistance.moa_classification.group_name}</span>
                  </div>
                )}
                {compound.resistance.cross_resistance && (
                  <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--color-text-600)' }}>
                    Cross-resistance: <strong style={{ color: riskColor(compound.resistance.cross_resistance.level) }}>{compound.resistance.cross_resistance.level}</strong>
                    {compound.resistance.cross_resistance.detail && ` — ${compound.resistance.cross_resistance.detail}`}
                  </div>
                )}
              </div>
            )}

            {/* Ecotoxicological Predictions */}
            <div className="detail-card">
              <div className="detail-card-title">
                Ecotoxicological Predictions (QSAR)
                {loadingPreds && <span className="detail-loading-dot">⏳</span>}
              </div>
              <div className="detail-prediction-table">
                <div className="detail-pred-header">
                  <span>Endpoint</span>
                  <span>Prediction</span>
                  <span>CI (95%)</span>
                  <span>AD</span>
                </div>
                {ecotoxPreds.map((ep) => {
                  const pred = predictions[ep.key];
                  return (
                    <div key={ep.key} className="detail-pred-row">
                      <span>{ep.icon} {ep.label}</span>
                      <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                        {pred ? formatPredValue(pred) : '—'}
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-text-400)' }}>
                        {pred?.ci_lower != null && pred?.ci_upper != null
                          ? `[${pred.ci_lower.toFixed(2)}, ${pred.ci_upper.toFixed(2)}]`
                          : '—'}
                      </span>
                      <span style={{ fontWeight: 600, fontSize: '10px', color: pred ? adStatusColor(pred.ad_status) : 'var(--color-text-400)' }}>
                        {pred ? pred.ad_status.toUpperCase() : '—'}
                      </span>
                    </div>
                  );
                })}
                {toxPreds.map((ep) => {
                  const pred = predictions[ep.key];
                  return (
                    <div key={ep.key} className="detail-pred-row">
                      <span>{ep.icon} {ep.label}</span>
                      <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                        {pred ? formatPredValue(pred) : '—'}
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-text-400)' }}>
                        {pred?.ci_lower != null && pred?.ci_upper != null
                          ? `[${pred.ci_lower.toFixed(2)}, ${pred.ci_upper.toFixed(2)}]`
                          : '—'}
                      </span>
                      <span style={{ fontWeight: 600, fontSize: '10px', color: pred ? adStatusColor(pred.ad_status) : 'var(--color-text-400)' }}>
                        {pred ? pred.ad_status.toUpperCase() : '—'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Environmental Fate Predictions */}
            <div className="detail-card">
              <div className="detail-card-title">
                Environmental Fate Predictions
                {loadingPreds && <span className="detail-loading-dot">⏳</span>}
              </div>
              <div className="detail-prediction-table">
                <div className="detail-pred-header">
                  <span>Endpoint</span>
                  <span>Prediction</span>
                  <span>CI (95%)</span>
                  <span>AD</span>
                </div>
                {envPreds.map((ep) => {
                  const pred = predictions[ep.key];
                  return (
                    <div key={ep.key} className="detail-pred-row">
                      <span>{ep.icon} {ep.label}</span>
                      <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                        {pred ? formatPredValue(pred) : '—'}
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-text-400)' }}>
                        {pred?.ci_lower != null && pred?.ci_upper != null
                          ? `[${pred.ci_lower.toFixed(2)}, ${pred.ci_upper.toFixed(2)}]`
                          : '—'}
                      </span>
                      <span style={{ fontWeight: 600, fontSize: '10px', color: pred ? adStatusColor(pred.ad_status) : 'var(--color-text-400)' }}>
                        {pred ? pred.ad_status.toUpperCase() : '—'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
