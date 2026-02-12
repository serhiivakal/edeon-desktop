import { useState } from 'react';
import { ActivityDistribution } from './ActivityDistribution';

export interface Warning {
  level: 'info' | 'warn' | 'error';
  message: string;
  smiles: string | null;
}

export interface DuplicateConflict {
  canonical_smiles: string;
  values: number[];
  resolution: string;
  resolved_value: number;
  spread: number;
}

export interface CurationReport {
  n_input: number;
  n_invalid: number;
  n_salts_stripped: number;
  n_neutralised: number;
  n_disallowed_atoms: number;
  n_duplicates_merged: number;
  n_final: number;
  warnings: Warning[];
  duplicate_conflicts: DuplicateConflict[];
  activity_stats?: any;
}

interface CurationReportPanelProps {
  report: CurationReport;
  modelType: 'regression' | 'classification';
  onBack: () => void;
  onAccept: () => void;
}

export function CurationReportPanel({
  report,
  modelType,
  onBack,
  onAccept,
}: CurationReportPanelProps) {
  const [activeTab, setActiveTab] = useState<'funnel' | 'warnings' | 'duplicates'>('funnel');
  const [duplicatesExpanded, setDuplicatesExpanded] = useState(false);

  // Group warnings by level
  const errors = report.warnings.filter((w) => w.level === 'error');
  const warns = report.warnings.filter((w) => w.level === 'warn');
  const infos = report.warnings.filter((w) => w.level === 'info');

  const hasWarnings = report.warnings.length > 0;
  const topDuplicates = report.duplicate_conflicts.slice(0, 10);



  return (
    <div className="curation-panel">
      {/* Wizard Header */}
      <div className="wizard-step-header" style={{ marginBottom: '20px' }}>
        <span className="wizard-step-title">🧪 Dataset Curation Quality Report</span>
        <span className="wizard-step-indicator" style={{ background: report.n_final >= 10 ? 'var(--color-brand-100)' : 'var(--color-red-100)', color: report.n_final >= 10 ? 'var(--color-brand-900)' : 'var(--color-red-900)' }}>
          {report.n_final} / {report.n_input} Retained
        </span>
      </div>

      {report.n_final < 10 && (
        <div className="workflow-error" style={{ marginBottom: '16px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>⚠</span>
          <div>
            <strong>Insufficient Compounds Remaining:</strong> After running the chemoinformatics curation pipeline, only {report.n_final} compounds are retained. A minimum of <strong>10 valid compounds</strong> is required to train a QSAR machine learning model. Please go back and load a larger dataset.
          </div>
        </div>
      )}

      {/* Tabs Menu */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', marginBottom: '16px', gap: '4px' }}>
        <button
          className={`inspector-tab-btn${activeTab === 'funnel' ? ' active' : ''}`}
          onClick={() => setActiveTab('funnel')}
          style={{ padding: '8px 16px', fontSize: '11px', fontWeight: 600 }}
        >
          📊 Filtering Funnel
        </button>
        <button
          className={`inspector-tab-btn${activeTab === 'warnings' ? ' active' : ''}`}
          onClick={() => setActiveTab('warnings')}
          style={{ padding: '8px 16px', fontSize: '11px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          ⚠ Warnings & Errors
          {hasWarnings && (
            <span style={{
              background: errors.length > 0 ? 'var(--color-red-500)' : 'var(--color-amber-500)',
              color: '#ffffff',
              borderRadius: '10px',
              padding: '1px 6px',
              fontSize: '9px'
            }}>
              {report.warnings.length}
            </span>
          )}
        </button>
        {report.duplicate_conflicts.length > 0 && (
          <button
            className={`inspector-tab-btn${activeTab === 'duplicates' ? ' active' : ''}`}
            onClick={() => setActiveTab('duplicates')}
            style={{ padding: '8px 16px', fontSize: '11px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            👥 Duplicates
            <span style={{ background: 'var(--color-brand-600)', color: '#ffffff', borderRadius: '10px', padding: '1px 6px', fontSize: '9px' }}>
              {report.duplicate_conflicts.length}
            </span>
          </button>
        )}
      </div>

      {/* Panel Content */}
      <div style={{ minHeight: '320px' }}>
        
        {/* Tab 1: Funnel Chart */}
        {activeTab === 'funnel' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div className="config-section-title" style={{ margin: 0 }}>Chemoinformatics Filtering Flow</div>
            
            {/* Visual Funnel Row Blocks */}
            <div className="funnel-container" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              
              {/* Row 1: Inputs */}
              <div className="funnel-row" style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', background: 'var(--color-bg-dark)', borderRadius: '6px', border: '0.5px solid var(--color-border-subtle)' }}>
                <span style={{ fontSize: '18px', width: '32px' }}>📥</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '11px', fontWeight: 600 }}>Raw Input Compounds</div>
                  <div style={{ fontSize: '9px', color: 'var(--color-text-400)' }}>Total rows parsed from raw CSV file / presets</div>
                </div>
                <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-text-200)' }}>{report.n_input}</div>
              </div>

              {/* Row 2: Invalid SMILES */}
              {report.n_invalid > 0 && (
                <div className="funnel-row dropped" style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', background: 'rgba(239, 68, 68, 0.08)', borderRadius: '6px', border: '0.5px solid rgba(239, 68, 68, 0.3)' }}>
                  <span style={{ fontSize: '18px', width: '32px' }}>❌</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-red-700)' }}>Invalid SMILES Dropped</div>
                    <div style={{ fontSize: '9px', color: 'var(--color-text-400)' }} title="Valence, bad syntax, or unparsable chemical symbols">
                      Dropped structures failing basic chemical valence or RDKit SMILES parser rules (?)
                    </div>
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-red-700)' }}>-{report.n_invalid}</div>
                </div>
              )}

              {/* Row 3: Salt Stripped (Cleaned, not dropped) */}
              {report.n_salts_stripped > 0 && (
                <div className="funnel-row cleaned" style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', background: 'rgba(59, 130, 246, 0.08)', borderRadius: '6px', border: '0.5px solid rgba(59, 130, 246, 0.3)' }}>
                  <span style={{ fontSize: '18px', width: '32px' }}>🧂</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-blue-600)' }}>Salts & Counter-ions Stripped</div>
                    <div style={{ fontSize: '9px', color: 'var(--color-text-400)' }} title="Stripped HCl, Sodium, and solvent elements from mixture structures">
                      Active organic fragments isolated by stripping inorganic salts / counter-ions (?)
                    </div>
                  </div>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-blue-600)', background: 'var(--color-blue-100)', padding: '2px 8px', borderRadius: '10px' }}>
                    {report.n_salts_stripped} cleaned
                  </div>
                </div>
              )}

              {/* Row 4: Neutralized Charges (Cleaned, not dropped) */}
              {report.n_neutralised > 0 && (
                <div className="funnel-row neutralized" style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', background: 'rgba(16, 185, 129, 0.08)', borderRadius: '6px', border: '0.5px solid rgba(16, 185, 129, 0.3)' }}>
                  <span style={{ fontSize: '18px', width: '32px' }}>⚡</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-brand-700)' }}>Neutralized Zwitterions</div>
                    <div style={{ fontSize: '9px', color: 'var(--color-text-400)' }} title="Neutralized acid/base charges to compute clean parameters">
                      Uncharged acids/bases to ensure consistent physiological descriptor computation (?)
                    </div>
                  </div>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-brand-700)', background: 'var(--color-brand-100)', padding: '2px 8px', borderRadius: '10px' }}>
                    {report.n_neutralised} uncharged
                  </div>
                </div>
              )}

              {/* Row 5: Disallowed Atoms */}
              {report.n_disallowed_atoms > 0 && (
                <div className="funnel-row dropped" style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', background: 'rgba(245, 158, 11, 0.08)', borderRadius: '6px', border: '0.5px solid rgba(245, 158, 11, 0.3)' }}>
                  <span style={{ fontSize: '18px', width: '32px' }}>☢</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-amber-700)' }}>Disallowed Elements Dropped</div>
                    <div style={{ fontSize: '9px', color: 'var(--color-text-400)' }} title="Keeps standard organic atoms only: H, B, C, N, O, F, Si, P, S, Cl, Br, I">
                      Dropped structures containing metals, transition elements, or heavy isotopes (?)
                    </div>
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-amber-700)' }}>-{report.n_disallowed_atoms}</div>
                </div>
              )}

              {/* Row 6: Duplicates Merged */}
              {report.n_duplicates_merged > 0 && (
                <div className="funnel-row duplicate" style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', background: 'rgba(99, 102, 241, 0.08)', borderRadius: '6px', border: '0.5px solid rgba(99, 102, 241, 0.3)' }}>
                  <span style={{ fontSize: '18px', width: '32px' }}>👥</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-indigo-600)' }}>Duplicate Compounds Merged</div>
                    <div style={{ fontSize: '9px', color: 'var(--color-text-400)' }} title="Identified multiple rows of identical structures; aggregated activities. For classification, tie-vote groups are dropped entirely.">
                      Identical canonical graphs deduplicated (averages / majority voted) (?)
                    </div>
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-indigo-600)' }}>-{report.n_duplicates_merged}</div>
                </div>
              )}

              {/* Row 7: Final Retained */}
              <div className="funnel-row final" style={{ display: 'flex', alignItems: 'center', padding: '10px 12px', background: 'var(--color-brand-100)', borderRadius: '6px', border: '1px solid var(--color-brand-600)' }}>
                <span style={{ fontSize: '20px', width: '32px' }}>🏆</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-brand-900)' }}>Curated Final Dataset</div>
                  <div style={{ fontSize: '9px', color: 'var(--color-brand-800)' }}>100% clean, standardized, aligned compounds ready for ML model training</div>
                </div>
                <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--color-brand-900)' }}>{report.n_final}</div>
              </div>

            </div>

            {/* Activity Distribution stats block (Task 2) */}
            {report.activity_stats && (
              <ActivityDistribution stats={report.activity_stats} />
            )}

          </div>
        )}

        {/* Tab 2: Warnings Panel */}
        {activeTab === 'warnings' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div className="config-section-title" style={{ margin: 0 }}>Curation Diagnostics & Log Warnings</div>
            
            {!hasWarnings ? (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--color-brand-700)', background: 'rgba(16, 185, 129, 0.05)', border: '0.5px dashed var(--color-brand-500)', borderRadius: '6px', fontSize: '11px' }}>
                🎉 Excellent Quality! 0 warnings, duplicates conflicts, or structure errors detected.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto', paddingRight: '4px' }}>
                
                {/* Errors Group (Drops) */}
                {errors.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-red-700)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      🚫 Dropped Compounds ({errors.length})
                    </div>
                    {errors.map((err, i) => (
                      <div key={i} className="warning-card error" style={{ background: 'rgba(239, 68, 68, 0.03)', borderLeft: '3px solid var(--color-red-500)', padding: '6px 10px', borderRadius: '0 4px 4px 0', fontSize: '10px' }}>
                        <div style={{ color: 'var(--color-text-100)', fontWeight: 500 }}>{err.message}</div>
                        {err.smiles && <code style={{ fontSize: '9px', background: 'var(--color-bg-dark)', padding: '2px 4px', borderRadius: '3px', marginTop: '2px', display: 'inline-block', color: 'var(--color-text-400)', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{err.smiles}</code>}
                      </div>
                    ))}
                  </div>
                )}

                {/* Warnings Group (High-spreads) */}
                {warns.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '8px' }}>
                    <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-amber-700)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      ⚠ High Activity Spreads ({warns.length})
                    </div>
                    {warns.map((w, i) => (
                      <div key={i} className="warning-card warn" style={{ background: 'rgba(245, 158, 11, 0.03)', borderLeft: '3px solid var(--color-amber-500)', padding: '6px 10px', borderRadius: '0 4px 4px 0', fontSize: '10px' }}>
                        <div style={{ color: 'var(--color-text-100)', fontWeight: 500 }}>{w.message}</div>
                        {w.smiles && <code style={{ fontSize: '9px', background: 'var(--color-bg-dark)', padding: '2px 4px', borderRadius: '3px', marginTop: '2px', display: 'inline-block', color: 'var(--color-text-400)', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.smiles}</code>}
                      </div>
                    ))}
                  </div>
                )}

                {/* Infos Group (Salts / uncharged) */}
                {infos.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '8px' }}>
                    <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-blue-600)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      ℹ Minor Cleanups ({infos.length})
                    </div>
                    {infos.map((info, i) => (
                      <div key={i} className="warning-card info" style={{ background: 'rgba(59, 130, 246, 0.03)', borderLeft: '3px solid var(--color-blue-500)', padding: '6px 10px', borderRadius: '0 4px 4px 0', fontSize: '10px' }}>
                        <div style={{ color: 'var(--color-text-200)' }}>{info.message}</div>
                        {info.smiles && <code style={{ fontSize: '9px', background: 'var(--color-bg-dark)', padding: '2px 4px', borderRadius: '3px', marginTop: '2px', display: 'inline-block', color: 'var(--color-text-400)', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{info.smiles}</code>}
                      </div>
                    ))}
                  </div>
                )}

              </div>
            )}

          </div>
        )}

        {/* Tab 3: Duplicates conflicts list */}
        {activeTab === 'duplicates' && report.duplicate_conflicts.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="config-section-title" style={{ margin: 0 }}>Duplicate Record Consolidation</div>
              <button
                className="inspector-btn"
                style={{ fontSize: '9px', padding: '2px 6px' }}
                onClick={() => setDuplicatesExpanded(!duplicatesExpanded)}
              >
                {duplicatesExpanded ? 'Collapse All' : 'Expand All Values'}
              </button>
            </div>

            <div style={{ fontSize: '9px', color: 'var(--color-text-400)', marginBottom: '4px' }}>
              Showing top {topDuplicates.length} groups sorted by target spread descending. Multiple measurements for identical structures are automatically averaged or majority voted.
            </div>

            <div style={{ maxHeight: '280px', overflowY: 'auto', border: '0.5px solid var(--color-border)', borderRadius: '6px' }}>
              <table style={{ width: '100%', fontSize: '10px', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--color-border-subtle)', textAlign: 'left', borderBottom: '1px solid var(--color-border)' }}>
                    <th style={{ padding: '6px 8px' }}>Canonical Structure</th>
                    <th style={{ padding: '6px 8px', textAlign: 'center' }}>No. Rows</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>Spread</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>Resolved Value</th>
                  </tr>
                </thead>
                <tbody>
                  {topDuplicates.map((dup, idx) => (
                    <tr key={idx} style={{ borderBottom: '0.5px solid var(--color-border-subtle)' }}>
                      <td style={{ padding: '6px 8px' }}>
                        <code style={{ fontSize: '9px', display: 'block', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={dup.canonical_smiles}>
                          {dup.canonical_smiles}
                        </code>
                        {duplicatesExpanded && (
                          <div style={{ fontSize: '8px', color: 'var(--color-text-400)', marginTop: '3px' }}>
                            Original values: [{dup.values.map(v => v.toFixed(2)).join(', ')}]
                          </div>
                        )}
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'center', fontWeight: 600 }}>
                        {dup.values.length}
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600, color: dup.spread > 1.0 && modelType === 'regression' ? 'var(--color-red-700)' : 'var(--color-text-200)' }}>
                        {modelType === 'regression' ? `${dup.spread.toFixed(2)} log` : `${(dup.spread * 100).toFixed(0)}%`}
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, color: 'var(--color-brand-700)' }}>
                        {dup.resolved_value === -1.0 ? 'Dropped' : dup.resolved_value.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

          </div>
        )}

      </div>

      {/* Button Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '0.5px solid var(--color-border)', paddingTop: '16px', marginTop: '16px' }}>
        <button className="inspector-btn" onClick={onBack}>
          ← Back to Dataset
        </button>
        <button
          className="inspector-btn-primary"
          style={{ width: 'auto', padding: '6px 16px' }}
          disabled={report.n_final < 10}
          onClick={onAccept}
        >
          Accept & Configure →
        </button>
      </div>

    </div>
  );
}
