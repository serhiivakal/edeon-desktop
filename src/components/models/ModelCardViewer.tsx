import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { ModelCard } from '../../types';
import { ModelTierBadge } from './ModelTierBadge';
import { VerificationBadge } from '../shared/VerificationBadge';
import { 
  X, 
  BookOpen, 
  AlertOctagon, 
  Terminal, 
  Users, 
  Shield, 
  Calendar,
  Activity,
  Layers,
  HelpCircle,
  BarChart2
} from 'lucide-react';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  LineChart,
  Line,
  BarChart,
  Bar,
  ReferenceLine,
  Legend
} from 'recharts';
const chartTooltipStyle = {
  backgroundColor: 'var(--color-surface, #ffffff)',
  border: '0.5px solid var(--color-border, #e5e5e0)',
  borderRadius: '6px',
  padding: '8px 12px',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
};

const CustomParityTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div style={chartTooltipStyle}>
        <div style={{ 
          fontSize: '10px', 
          color: 'var(--color-text-400, #888888)', 
          marginBottom: '4px', 
          fontFamily: 'var(--font-mono, monospace)', 
          maxWidth: '200px', 
          overflow: 'hidden', 
          textOverflow: 'ellipsis', 
          whiteSpace: 'nowrap' 
        }}>
          {data.smiles}
        </div>
        <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-900, #1a1a1a)' }}>
          Observed: {data.observed.toFixed(3)}
        </div>
        <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-900, #1a1a1a)' }}>
          Predicted: {data.predicted.toFixed(3)}
        </div>
        {data.ci_lower !== undefined && data.ci_upper !== undefined && (
          <div style={{ fontSize: '10px', color: 'var(--color-text-600, #5a5a5a)', marginTop: '2px' }}>
            95% CI: [{data.ci_lower.toFixed(3)}, {data.ci_upper.toFixed(3)}]
          </div>
        )}
        <div style={{ 
          fontSize: '9px', 
          fontWeight: 700, 
          textTransform: 'uppercase', 
          color: data.ad_status === 'in' ? '#16a34a' : data.ad_status === 'borderline' ? '#d97706' : '#dc2626', 
          marginTop: '4px' 
        }}>
          AD Status: {data.ad_status}
        </div>
      </div>
    );
  }
  return null;
};

export interface ModelCardViewerProps {
  modelId: string;
  onClose: () => void;
  queryDistance?: number;
  queryStatus?: string;
}

export function ModelCardViewer({ modelId, onClose, queryDistance, queryStatus }: ModelCardViewerProps) {
  const [card, setCard] = useState<ModelCard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [trainingDataOpen, setTrainingDataOpen] = useState(true);

  // Diagnostics & Tab states
  const [activeTab, setActiveTab] = useState<'metadata' | 'diagnostics'>('metadata');
  const [diagnostics, setDiagnostics] = useState<any | null>(null);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [diagnosticsError, setDiagnosticsError] = useState<string | null>(null);

  // Sorting state for chemical classes table
  const [classSortBy, setClassSortBy] = useState<'name' | 'count' | 'metric' | 'ad_coverage'>('count');
  const [classSortOrder, setClassSortOrder] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    setLoading(true);
    setError(null);
    invoke<ModelCard>('model_get_card', { modelId })
      .then((data) => {
        setCard(data);
      })
      .catch((err) => {
        console.error('Failed to fetch model card:', err);
        setError(String(err));
      })
      .finally(() => {
        setLoading(false);
      });
  }, [modelId]);

  useEffect(() => {
    setActiveTab('metadata');
    setDiagnostics(null);
    setDiagnosticsError(null);
  }, [modelId]);

  useEffect(() => {
    if (activeTab === 'diagnostics' && !diagnostics && !diagnosticsLoading) {
      setDiagnosticsLoading(true);
      setDiagnosticsError(null);
      invoke<any>('get_calibration_diagnostics', { modelId })
        .then((data) => {
          setDiagnostics(data);
        })
        .catch((err) => {
          console.error('Failed to fetch calibration diagnostics:', err);
          setDiagnosticsError(String(err));
        })
        .finally(() => {
          setDiagnosticsLoading(false);
        });
    }
  }, [modelId, activeTab, diagnostics, diagnosticsLoading]);


  if (loading) {
    return (
      <div style={overlayStyle} onClick={onClose}>
        <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '240px', gap: '12px' }}>
            <div className="spinning-loader" style={loaderStyle} />
            <span style={{ fontSize: '11px', color: 'var(--color-text-400, #888888)', fontWeight: 500 }}>
              Retrieving Model Card Metadata...
            </span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !card) {
    return (
      <div style={overlayStyle} onClick={onClose}>
        <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '260px', padding: '24px', textAlign: 'center', gap: '12px' }}>
            <AlertOctagon size={36} color="var(--color-red-700, #993c1d)" />
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900, #1a1a1a)' }}>
              Failed to Load Model Card
            </div>
            <div style={{ fontSize: '11px', color: 'var(--color-text-600, #5a5a5a)', lineHeight: '1.4' }}>
              {error || 'Model details are unavailable in the active predictability registries.'}
            </div>
            <button 
              onClick={onClose}
              className="inspector-btn-primary"
              style={{ padding: '0 16px', height: '28px', minHeight: 'unset', width: 'auto', marginTop: '8px' }}
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    );
  }

  const {
    name,
    version,
    tier,
    description,
    intended_use,
    not_intended_for,
    training_data,
    performance,
    applicability_domain,
    uncertainty_method,
    known_failure_modes,
    references,
    license,
    created,
    authors
  } = card;

  // Helper to bin distances for the AD histogram
  const getAdHistogramData = (trainDist: number[], testDist: number[]) => {
    const binsCount = 20;
    const binSize = 1.0 / binsCount;
    
    return Array.from({ length: binsCount }, (_, i) => {
      const start = i * binSize;
      const end = start + binSize;
      const center = start + binSize / 2;
      
      const train = trainDist ? trainDist.filter(d => d >= start && d < end).length : 0;
      const test = testDist ? testDist.filter(d => d >= start && d < end).length : 0;
      
      return {
        binStart: start,
        binEnd: end,
        name: center.toFixed(2),
        train,
        test,
      };
    });
  };

  const renderConfusionMatrix = (matrix: number[][]) => {
    if (!matrix || matrix.length < 2) return null;
    const tn = matrix[0][0];
    const fp = matrix[0][1];
    const fn = matrix[1][0];
    const tp = matrix[1][1];
    const total = tn + fp + fn + tp;
    
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-600)', marginBottom: '4px' }}>
          Confusion Matrix (N = {total})
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: '80px 1fr 1fr', 
          gap: '2px', 
          fontFamily: 'var(--font-mono, monospace)', 
          fontSize: '11px',
          background: 'var(--color-border-subtle, #f0f0eb)',
          padding: '2px',
          borderRadius: '6px'
        }}>
          {/* Header row */}
          <div style={{ background: 'var(--color-bg)', padding: '6px', fontWeight: 600 }}>Obs \ Pred</div>
          <div style={{ background: 'var(--color-bg)', padding: '6px', fontWeight: 600, textAlign: 'center' }}>Negative (0)</div>
          <div style={{ background: 'var(--color-bg)', padding: '6px', fontWeight: 600, textAlign: 'center' }}>Positive (1)</div>

          {/* Row 0 */}
          <div style={{ background: 'var(--color-bg)', padding: '8px 6px', fontWeight: 600 }}>Negative (0)</div>
          <div style={{ background: 'var(--color-surface, #ffffff)', padding: '8px', textAlign: 'center', fontWeight: 500, color: 'var(--color-brand-900)' }}>
            <div style={{ fontSize: '12px', fontWeight: 700 }}>{tn}</div>
            <div style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>TN ({total > 0 ? ((tn/total)*100).toFixed(0) : 0}%)</div>
          </div>
          <div style={{ background: 'var(--color-red-100, #fceae5)', padding: '8px', textAlign: 'center', fontWeight: 500, color: 'var(--color-red-700)' }}>
            <div style={{ fontSize: '12px', fontWeight: 700 }}>{fp}</div>
            <div style={{ fontSize: '8px', color: 'var(--color-red-700)' }}>FP ({total > 0 ? ((fp/total)*100).toFixed(0) : 0}%)</div>
          </div>

          {/* Row 1 */}
          <div style={{ background: 'var(--color-bg)', padding: '8px 6px', fontWeight: 600 }}>Positive (1)</div>
          <div style={{ background: 'var(--color-red-100, #fceae5)', padding: '8px', textAlign: 'center', fontWeight: 500, color: 'var(--color-red-700)' }}>
            <div style={{ fontSize: '12px', fontWeight: 700 }}>{fn}</div>
            <div style={{ fontSize: '8px', color: 'var(--color-red-700)' }}>FN ({total > 0 ? ((fn/total)*100).toFixed(0) : 0}%)</div>
          </div>
          <div style={{ background: 'var(--color-surface, #ffffff)', padding: '8px', textAlign: 'center', fontWeight: 500, color: 'var(--color-brand-900)' }}>
            <div style={{ fontSize: '12px', fontWeight: 700 }}>{tp}</div>
            <div style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>TP ({total > 0 ? ((tp/total)*100).toFixed(0) : 0}%)</div>
          </div>
        </div>
      </div>
    );
  };

  let queryDistanceBinName = '';
  if (queryDistance !== undefined && queryDistance !== null) {
    const binSize = 1.0 / 20;
    const queryBinIndex = Math.min(19, Math.max(0, Math.floor(queryDistance / binSize)));
    queryDistanceBinName = (queryBinIndex * binSize + binSize / 2).toFixed(2);
  }

  let queryLineColor = 'var(--color-blue-500, #3b82f6)';
  if (queryStatus === 'in') {
    queryLineColor = '#16a34a';
  } else if (queryStatus === 'borderline') {
    queryLineColor = '#d97706';
  } else if (queryStatus === 'out') {
    queryLineColor = '#dc2626';
  } else if (diagnostics?.ad_distance_histogram) {
    const { in_threshold, out_threshold } = diagnostics.ad_distance_histogram;
    if (queryDistance !== undefined && queryDistance !== null) {
      if (queryDistance <= in_threshold) {
        queryLineColor = '#16a34a';
      } else if (queryDistance <= out_threshold) {
        queryLineColor = '#d97706';
      } else {
        queryLineColor = '#dc2626';
      }
    }
  }

  const classData = diagnostics?.per_chemical_class_metrics 
    ? Object.entries(diagnostics.per_chemical_class_metrics).map(([name, metrics]: [string, any]) => ({
        name,
        count: metrics.count || 0,
        metric: metrics.rmse !== undefined ? metrics.rmse : (metrics.f1 !== undefined ? metrics.f1 : metrics.balanced_accuracy || 0),
        metricName: metrics.rmse !== undefined ? 'RMSE' : (metrics.f1 !== undefined ? 'F1' : 'Bal. Acc'),
        ad_coverage: metrics.ad_coverage || 0,
        coverage: metrics.coverage,
      }))
    : [];

  const sortedClassData = [...classData].sort((a, b) => {
    let valA: any = a[classSortBy];
    let valB: any = b[classSortBy];
    
    if (typeof valA === 'string') {
      return classSortOrder === 'asc' 
        ? valA.localeCompare(valB)
        : valB.localeCompare(valA);
    }
    
    return classSortOrder === 'asc' 
      ? valA - valB
      : valB - valA;
  });

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div 
        style={{
          ...modalStyle,
          width: activeTab === 'diagnostics' ? '820px' : '560px',
          transition: 'width 250ms cubic-bezier(0.4, 0, 0.2, 1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Section */}
        <div style={headerStyle}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <h2 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: 'var(--color-text-900, #1a1a1a)' }}>
                {name}
              </h2>
              <span style={{ fontSize: '10px', color: 'var(--color-text-400, #888888)', fontWeight: 600 }}>
                v{version}
              </span>
            </div>
            <div style={{ fontSize: '10px', color: 'var(--color-text-400, #888888)', fontFamily: 'var(--font-mono, monospace)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Terminal size={10} />
              ID: {modelId}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {tier === 1 && <VerificationBadge endpoint={modelId} verified={true} variant="expanded" />}
            <ModelTierBadge tier={tier} />
            <button style={closeBtnStyle} onClick={onClose} title="Close Modal">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div style={{ display: 'flex', borderBottom: '0.5px solid var(--color-border, #e5e5e0)', background: 'var(--color-bg, #f5f5f0)', padding: '0 20px' }}>
          <button 
            onClick={() => setActiveTab('metadata')}
            style={{
              padding: '10px 16px',
              fontSize: '11px',
              fontWeight: 600,
              color: activeTab === 'metadata' ? 'var(--color-brand-700, #3b6d11)' : 'var(--color-text-400, #888888)',
              borderBottom: activeTab === 'metadata' ? '2px solid var(--color-brand-700, #3b6d11)' : '2px solid transparent',
              background: 'transparent',
              borderLeft: 'none',
              borderRight: 'none',
              borderTop: 'none',
              cursor: 'pointer',
              outline: 'none',
              transition: 'all 150ms ease',
            }}
          >
            Model Metadata
          </button>
          <button 
            onClick={() => setActiveTab('diagnostics')}
            style={{
              padding: '10px 16px',
              fontSize: '11px',
              fontWeight: 600,
              color: activeTab === 'diagnostics' ? 'var(--color-brand-700, #3b6d11)' : 'var(--color-text-400, #888888)',
              borderBottom: activeTab === 'diagnostics' ? '2px solid var(--color-brand-700, #3b6d11)' : '2px solid transparent',
              background: 'transparent',
              borderLeft: 'none',
              borderRight: 'none',
              borderTop: 'none',
              cursor: 'pointer',
              outline: 'none',
              transition: 'all 150ms ease',
            }}
          >
            Calibration Diagnostics
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div style={bodyStyle}>
          {activeTab === 'metadata' && (
            <>
              {/* Section 1: Description & Intended Use */}
              <div style={sectionStyle}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                  <BookOpen size={13} color="var(--color-brand-600, #3b6d11)" />
                  <h3 style={sectionTitleStyle}>Description & Intended Use</h3>
                </div>
                <p style={paragraphStyle}>{description}</p>
                <div style={intendedUseBoxStyle}>
                  <span style={{ fontWeight: 600, color: 'var(--color-brand-900, #173404)' }}>Intended Use Case:</span>{' '}
                  {intended_use}
                </div>
              </div>

              {/* Section 2: Not Intended For Warnings */}
              {not_intended_for && not_intended_for.length > 0 && (
                <div style={warningBoxStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', color: 'var(--color-red-700, #993c1d)' }}>
                    <AlertOctagon size={13} />
                    <span style={{ fontWeight: 700, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Safety Warnings & Constraints
                    </span>
                  </div>
                  <ul style={bulletListStyle}>
                    {not_intended_for.map((item, idx) => (
                      <li key={idx} style={{ color: 'var(--color-red-700, #993c1d)', fontWeight: 500 }}>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Section 3: Training Data (collapsible) */}
              {training_data && (
                <div style={sectionStyle}>
                  <button 
                    style={collapsibleHeaderStyle}
                    onClick={() => setTrainingDataOpen(!trainingDataOpen)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Layers size={13} color="var(--color-brand-600, #3b6d11)" />
                      <h3 style={sectionTitleStyle}>Training Data Provenance</h3>
                    </div>
                    <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>
                      {trainingDataOpen ? 'Collapse ▲' : 'Expand ▼'}
                    </span>
                  </button>

                  {trainingDataOpen && (
                    <div style={collapsibleContentStyle}>
                      <div style={gridStyle}>
                        <div style={gridItemStyle}>
                          <span style={gridLabelStyle}>Compounds Count</span>
                          <span style={gridValueStyle}>{training_data.n_compounds} molecules</span>
                        </div>
                        {training_data.split_strategy && (
                          <div style={gridItemStyle}>
                            <span style={gridLabelStyle}>Validation Split</span>
                            <span style={gridValueStyle}>{training_data.split_strategy}</span>
                          </div>
                        )}
                        {training_data.sha256 && (
                          <div style={gridItemStyle}>
                            <span style={gridLabelStyle}>Dataset Hash Integrity</span>
                            <span style={{ ...gridValueStyle, fontFamily: 'var(--font-mono, monospace)', fontSize: '9px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={training_data.sha256}>
                              {training_data.sha256}
                            </span>
                          </div>
                        )}
                        {training_data.license && (
                          <div style={gridItemStyle}>
                            <span style={gridLabelStyle}>Data Source License</span>
                            <span style={gridValueStyle}>{training_data.license}</span>
                          </div>
                        )}
                      </div>
                      {training_data.sources && training_data.sources.length > 0 && (
                        <div style={{ marginTop: '8px' }}>
                          <span style={gridLabelStyle}>Origin Databases / References</span>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '3px' }}>
                            {training_data.sources.map((src, i) => (
                              <span key={i} style={tagStyle}>{src}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Section 4: Performance Metrics Table */}
              {performance && performance.metrics && Object.keys(performance.metrics).length > 0 && (
                <div style={sectionStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                    <Activity size={13} color="var(--color-brand-600, #3b6d11)" />
                    <h3 style={sectionTitleStyle}>Performance & Validation Metrics</h3>
                  </div>
                  
                  <table style={tableStyle}>
                    <thead>
                      <tr style={tableHeaderRowStyle}>
                        <th style={tableHeaderStyle}>Metric Parameter</th>
                        <th style={{ ...tableHeaderStyle, textAlign: 'right' }}>Reported Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(performance.metrics).map(([key, val]) => (
                        <tr key={key} style={tableBodyRowStyle}>
                          <td style={tableCellStyle}>{key.replace(/_/g, ' ').toUpperCase()}</td>
                          <td style={{ ...tableCellStyle, textAlign: 'right', fontWeight: 600, fontFamily: 'var(--font-mono, monospace)' }}>
                            {typeof val === 'number' ? val.toFixed(4) : val}
                          </td>
                        </tr>
                      ))}
                      {performance.test_set_n !== undefined && performance.test_set_n !== null && (
                        <tr style={tableBodyRowStyle}>
                          <td style={tableCellStyle}>TEST SET SIZE (N)</td>
                          <td style={{ ...tableCellStyle, textAlign: 'right', fontWeight: 600 }}>
                            {performance.test_set_n} compounds
                          </td>
                        </tr>
                      )}
                      {performance.cv_folds !== undefined && performance.cv_folds !== null && (
                        <tr style={tableBodyRowStyle}>
                          <td style={tableCellStyle}>CROSS-VALIDATION FOLDS (K)</td>
                          <td style={{ ...tableCellStyle, textAlign: 'right', fontWeight: 600 }}>
                            {performance.cv_folds} folds
                          </td>
                        </tr>
                      )}
                      {performance.calibration_coverage_95 !== undefined && performance.calibration_coverage_95 !== null && (
                        <tr style={tableBodyRowStyle}>
                          <td style={tableCellStyle}>CALIBRATION COVERAGE (95% CI target)</td>
                          <td style={{ ...tableCellStyle, textAlign: 'right', fontWeight: 600, fontFamily: 'var(--font-mono, monospace)' }}>
                            {(performance.calibration_coverage_95 * 100).toFixed(2)}%
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Section 5: Applicability Domain Details */}
              {applicability_domain && (
                <div style={sectionStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                    <Shield size={13} color="var(--color-brand-600, #3b6d11)" />
                    <h3 style={sectionTitleStyle}>Applicability Domain Criteria</h3>
                  </div>
                  <div style={calloutBoxStyle}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-900)' }}>
                        Method: <code style={{ background: 'rgba(0,0,0,0.05)', padding: '1px 4px', borderRadius: '3px' }}>{applicability_domain.method}</code>
                      </span>
                      {applicability_domain.training_set_size && (
                        <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>
                          Baseline size: {applicability_domain.training_set_size} compounds
                        </span>
                      )}
                    </div>
                    {applicability_domain.notes && (
                      <p style={{ ...paragraphStyle, margin: '4px 0 0 0', fontSize: '10px', color: 'var(--color-text-600)' }}>
                        {applicability_domain.notes}
                      </p>
                    )}
                    {uncertainty_method && (
                      <div style={{ fontSize: '10px', color: 'var(--color-text-600)', marginTop: '6px', fontWeight: 500 }}>
                        Uncertainty Method: <span style={{ fontWeight: 600 }}>{uncertainty_method}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Section 6: Known Failure Modes */}
              {known_failure_modes && known_failure_modes.length > 0 && (
                <div style={sectionStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                    <HelpCircle size={13} color="var(--color-brand-600, #3b6d11)" />
                    <h3 style={sectionTitleStyle}>Known Failure Modes / Out-of-Domain Scenarios</h3>
                  </div>
                  <ul style={bulletListStyle}>
                    {known_failure_modes.map((mode, i) => (
                      <li key={i}>{mode}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Section 7: References */}
              {references && references.length > 0 && (
                <div style={sectionStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                    <BookOpen size={13} color="var(--color-brand-600, #3b6d11)" />
                    <h3 style={sectionTitleStyle}>Scientific Literature & Dossier References</h3>
                  </div>
                  <ol style={{ paddingLeft: '16px', margin: 0, fontSize: '10px', color: 'var(--color-text-600)', lineHeight: '1.5' }}>
                    {references.map((ref, idx) => (
                      <li key={idx} style={{ marginBottom: '4px' }}>
                        {ref.startsWith('http') ? (
                          <a href={ref} target="_blank" rel="noopener noreferrer" style={linkStyle}>
                            {ref}
                          </a>
                        ) : (
                          ref
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </>
          )}

          {activeTab === 'diagnostics' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {diagnosticsLoading && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '280px', gap: '12px' }}>
                  <div className="spinning-loader" style={loaderStyle} />
                  <span style={{ fontSize: '11px', color: 'var(--color-text-400)', fontWeight: 500 }}>
                    Computing Calibration Diagnostics...
                  </span>
                </div>
              )}

              {diagnosticsError && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '240px', padding: '20px', textAlign: 'center', gap: '10px' }}>
                  <AlertOctagon size={28} color="var(--color-text-400, #888888)" />
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-900)' }}>
                    Calibration Diagnostics Unavailable
                  </div>
                  <p style={{ fontSize: '10.5px', color: 'var(--color-text-600)', maxWidth: '400px', margin: 0, lineHeight: '1.4' }}>
                    Diagnostics are not supported for legacy baseline (Tier-2) models. 
                    Switch to a reference (Tier-1) or user-trained (Tier-4) model card to view uncertainty metrics, parity plots, and applicability domain distributions.
                  </p>
                </div>
              )}

              {diagnostics && (
                <>
                  {/* Top Stats Cards & AD Query Indicator */}
                  <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: '140px', background: 'var(--color-bg, #f5f5f0)', border: '0.5px solid var(--color-border)', borderRadius: '6px', padding: '8px 10px' }}>
                      <div style={{ fontSize: '8px', color: 'var(--color-text-400)', fontWeight: 600, textTransform: 'uppercase' }}>Task Type</div>
                      <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)', textTransform: 'capitalize', marginTop: '2px' }}>
                        {diagnostics.task_kind} Model
                      </div>
                    </div>
                    
                    <div style={{ flex: 1, minWidth: '140px', background: 'var(--color-bg, #f5f5f0)', border: '0.5px solid var(--color-border)', borderRadius: '6px', padding: '8px 10px' }}>
                      <div style={{ fontSize: '8px', color: 'var(--color-text-400)', fontWeight: 600, textTransform: 'uppercase' }}>Test Set Size</div>
                      <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)', marginTop: '2px' }}>
                        N = {diagnostics.test_set_size} compounds
                      </div>
                    </div>

                    {queryDistance !== undefined && queryDistance !== null && (
                      <div style={{ 
                        flex: '2 1 260px', 
                        background: queryStatus === 'in' 
                          ? 'var(--color-brand-100, #eaf3de)' 
                          : queryStatus === 'borderline' 
                            ? 'var(--color-amber-100, #fef3c7)' 
                            : 'var(--color-red-100, #fceae5)',
                        border: '0.5px solid',
                        borderColor: queryStatus === 'in' 
                          ? 'var(--color-brand-600, #3b6d11)' 
                          : queryStatus === 'borderline' 
                            ? 'var(--color-amber-600, #d97706)' 
                            : 'var(--color-red-500, #dc2626)',
                        borderRadius: '6px', 
                        padding: '8px 10px' 
                      }}>
                        <div style={{ fontSize: '8px', color: 'var(--color-text-600)', fontWeight: 600, textTransform: 'uppercase' }}>Inspected Molecule AD Assessment</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2px' }}>
                          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)' }}>
                            Tanimoto Distance: {queryDistance.toFixed(4)}
                          </span>
                          <span style={{ 
                            fontSize: '9px', 
                            fontWeight: 700, 
                            textTransform: 'uppercase', 
                            background: queryStatus === 'in' ? 'var(--color-brand-600)' : queryStatus === 'borderline' ? 'var(--color-amber-600)' : 'var(--color-red-500)',
                            color: '#ffffff',
                            padding: '1px 6px',
                            borderRadius: '3px'
                          }}>
                            {queryStatus === 'in' ? 'In Domain' : queryStatus === 'borderline' ? 'Borderline' : 'Out of Domain'}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* REGRESSION VISUALIZATIONS */}
                  {diagnostics.task_kind === 'regression' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      {/* Row 1: Parity & Calibration */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                        {/* Parity Plot */}
                        {diagnostics.parity_data && (
                          <div style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '10px' }}>
                            <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-600)', marginBottom: '8px' }}>
                              Parity Plot (Observed vs Predicted)
                            </h4>
                            <div style={{ width: '100%', height: '200px' }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle, #f0f0eb)" />
                                  <XAxis type="number" dataKey="observed" name="Observed" unit="" label={{ value: 'Observed', position: 'bottom', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <YAxis type="number" dataKey="predicted" name="Predicted" unit="" label={{ value: 'Predicted', angle: -90, position: 'left', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <ChartTooltip content={<CustomParityTooltip />} />
                                  <ReferenceLine slope={1} intercept={0} stroke="var(--color-text-400, #888888)" strokeDasharray="3 3" />
                                  <Scatter name="Test Compounds" data={diagnostics.parity_data.points} fill="var(--color-brand-600, #3b6d11)" line={false} />
                                </ScatterChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        )}

                        {/* Calibration Curve */}
                        {diagnostics.calibration_curve && (
                          <div style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '10px' }}>
                            <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-600)', marginBottom: '8px' }}>
                              Calibration Coverage Curve
                            </h4>
                            <div style={{ width: '100%', height: '200px' }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={diagnostics.calibration_curve.points} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle, #f0f0eb)" />
                                  <XAxis dataKey="expected" label={{ value: 'Expected Confidence Level', position: 'bottom', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <YAxis domain={[0, 1]} label={{ value: 'Empirical Coverage Rate', angle: -90, position: 'left', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <ChartTooltip formatter={(value: any) => [Number(value).toFixed(3), 'Coverage']} />
                                  <ReferenceLine slope={1} intercept={0} stroke="var(--color-text-400, #888888)" strokeDasharray="3 3" />
                                  <Line type="monotone" dataKey="actual" name="Actual Coverage" stroke="var(--color-brand-600, #3b6d11)" strokeWidth={2} dot={{ r: 3 }} />
                                </LineChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Row 2: Residuals & AD Distance */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                        {/* Residuals Distribution */}
                        {diagnostics.residual_distribution && (
                          <div style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '10px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                              <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-600)', margin: 0 }}>
                                Residuals Distribution
                              </h4>
                              <span style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-400)' }}>
                                μ={diagnostics.residual_distribution.mean.toFixed(3)}, σ={diagnostics.residual_distribution.std.toFixed(3)}
                              </span>
                            </div>
                            <div style={{ width: '100%', height: '200px' }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={diagnostics.residual_distribution.bins} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle, #f0f0eb)" />
                                  <XAxis dataKey="bin_center" tickFormatter={(v) => Number(v).toFixed(1)} label={{ value: 'Error Residual', position: 'bottom', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <YAxis label={{ value: 'Compound Count', angle: -90, position: 'left', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <ChartTooltip formatter={(value: any) => [value, 'Count']} labelFormatter={(v) => `Bin Center: ${Number(v).toFixed(3)}`} />
                                  <Bar dataKey="count" fill="var(--color-brand-600, #3b6d11)" radius={[3, 3, 0, 0]} />
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        )}

                        {/* Applicability Domain Histogram */}
                        {diagnostics.ad_distance_histogram && (
                          <div style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '10px' }}>
                            <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-600)', marginBottom: '8px' }}>
                              Applicability Domain Distance Distribution
                            </h4>
                            <div style={{ width: '100%', height: '200px' }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart 
                                  data={getAdHistogramData(
                                    diagnostics.ad_distance_histogram.train_distances,
                                    diagnostics.ad_distance_histogram.test_distances
                                  )} 
                                  margin={{ top: 10, right: 10, bottom: 20, left: 10 }}
                                >
                                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle, #f0f0eb)" />
                                  <XAxis dataKey="name" label={{ value: 'Tanimoto Distance to k-NN', position: 'bottom', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <YAxis label={{ value: 'Frequency Count', angle: -90, position: 'left', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <ChartTooltip formatter={(v: any, name?: any) => [v, name === 'train' ? 'Training Set' : 'Test Set']} />
                                  <Legend verticalAlign="top" height={24} iconSize={8} wrapperStyle={{ fontSize: 9 }} />
                                  <Bar dataKey="train" name="Training Set" fill="#475569" radius={[2, 2, 0, 0]} />
                                  {diagnostics.ad_distance_histogram.test_distances && diagnostics.ad_distance_histogram.test_distances.length > 0 && (
                                    <Bar dataKey="test" name="Test Set" fill="var(--color-brand-600, #3b6d11)" radius={[2, 2, 0, 0]} />
                                  )}
                                  {queryDistance !== undefined && queryDistance !== null && queryDistanceBinName && (
                                    <ReferenceLine 
                                      x={queryDistanceBinName} 
                                      stroke={queryLineColor} 
                                      strokeWidth={2}
                                      strokeDasharray="4 4"
                                      label={{ value: 'Query', position: 'top', fill: queryLineColor, fontSize: 8, fontWeight: 700 }}
                                    />
                                  )}
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* CLASSIFICATION VISUALIZATIONS */}
                  {diagnostics.task_kind === 'classification' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      {/* Row 1: ROC & PR Curves */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                        {/* ROC Curve */}
                        {diagnostics.roc_curve && (
                          <div style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '10px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                              <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-600)', margin: 0 }}>
                                Receiver Operating Characteristic (ROC)
                              </h4>
                              <span style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-brand-900)' }}>
                                ROC-AUC: {diagnostics.roc_curve.auc.toFixed(4)}
                              </span>
                            </div>
                            <div style={{ width: '100%', height: '200px' }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={diagnostics.roc_curve.points} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle, #f0f0eb)" />
                                  <XAxis dataKey="fpr" type="number" domain={[0, 1]} label={{ value: 'False Positive Rate', position: 'bottom', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <YAxis dataKey="tpr" type="number" domain={[0, 1]} label={{ value: 'True Positive Rate', angle: -90, position: 'left', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <ChartTooltip formatter={(v: any) => [Number(v).toFixed(3), 'True Positive Rate']} labelFormatter={(v) => `FPR: ${Number(v).toFixed(3)}`} />
                                  <ReferenceLine slope={1} intercept={0} stroke="var(--color-text-400, #888888)" strokeDasharray="3 3" />
                                  <Line type="monotone" dataKey="tpr" name="ROC Curve" stroke="var(--color-brand-600, #3b6d11)" strokeWidth={2} dot={false} />
                                </LineChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        )}

                        {/* PR Curve */}
                        {diagnostics.pr_curve && (
                          <div style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '10px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                              <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-600)', margin: 0 }}>
                                Precision-Recall (PR) Curve
                              </h4>
                              <span style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-blue-700)' }}>
                                PR-AUC: {diagnostics.pr_curve.auc.toFixed(4)}
                              </span>
                            </div>
                            <div style={{ width: '100%', height: '200px' }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={diagnostics.pr_curve.points} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle, #f0f0eb)" />
                                  <XAxis dataKey="recall" type="number" domain={[0, 1]} label={{ value: 'Recall / Sensitivity', position: 'bottom', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <YAxis dataKey="precision" type="number" domain={[0, 1]} label={{ value: 'Precision / PPV', angle: -90, position: 'left', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <ChartTooltip formatter={(v: any) => [Number(v).toFixed(3), 'Precision']} labelFormatter={(v) => `Recall: ${Number(v).toFixed(3)}`} />
                                  <Line type="monotone" dataKey="precision" name="PR Curve" stroke="var(--color-blue-500)" strokeWidth={2} dot={false} />
                                </LineChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Row 2: Reliability Diagram & AD Distance / Confusion Matrix */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '12px' }}>
                        {/* Reliability Diagram */}
                        {diagnostics.reliability_diagram && (
                          <div style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '10px' }}>
                            <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-600)', marginBottom: '8px' }}>
                              Reliability Diagram (Calibration)
                            </h4>
                            <div style={{ width: '100%', height: '180px' }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={diagnostics.reliability_diagram.bins} margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle, #f0f0eb)" />
                                  <XAxis dataKey="avg_predicted" type="number" domain={[0, 1]} label={{ value: 'Mean Predicted Probability', position: 'bottom', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <YAxis type="number" domain={[0, 1]} label={{ value: 'Empirical Positive Fraction', angle: -90, position: 'left', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                  <ChartTooltip formatter={(v: any) => [Number(v).toFixed(3), 'Actual Fraction']} labelFormatter={(v) => `Pred Prob: ${Number(v).toFixed(3)}`} />
                                  <ReferenceLine slope={1} intercept={0} stroke="var(--color-text-400, #888888)" strokeDasharray="3 3" />
                                  <Line type="monotone" dataKey="avg_actual" name="Model Bins" stroke="var(--color-brand-600, #3b6d11)" strokeWidth={2} dot={{ r: 3 }} />
                                </LineChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        )}

                        {/* Confusion Matrix */}
                        {diagnostics.confusion_matrix && renderConfusionMatrix(diagnostics.confusion_matrix)}
                      </div>

                      {/* Row 3: AD Histogram for Classification */}
                      {diagnostics.ad_distance_histogram && (
                        <div style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '10px' }}>
                          <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-600)', marginBottom: '8px' }}>
                            Applicability Domain Distance Distribution
                          </h4>
                          <div style={{ width: '100%', height: '180px' }}>
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart 
                                data={getAdHistogramData(
                                  diagnostics.ad_distance_histogram.train_distances,
                                  diagnostics.ad_distance_histogram.test_distances
                                )} 
                                margin={{ top: 10, right: 10, bottom: 20, left: 10 }}
                              >
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle, #f0f0eb)" />
                                <XAxis dataKey="name" label={{ value: 'Tanimoto Distance to k-NN', position: 'bottom', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                <YAxis label={{ value: 'Frequency Count', angle: -90, position: 'left', fontSize: 9, offset: 5 }} tick={{ fontSize: 9 }} />
                                <ChartTooltip formatter={(v: any, name?: any) => [v, name === 'train' ? 'Training Set' : 'Test Set']} />
                                <Legend verticalAlign="top" height={24} iconSize={8} wrapperStyle={{ fontSize: 9 }} />
                                <Bar dataKey="train" name="Training Set" fill="#475569" radius={[2, 2, 0, 0]} />
                                {diagnostics.ad_distance_histogram.test_distances && diagnostics.ad_distance_histogram.test_distances.length > 0 && (
                                  <Bar dataKey="test" name="Test Set" fill="var(--color-brand-600, #3b6d11)" radius={[2, 2, 0, 0]} />
                                )}
                                {queryDistance !== undefined && queryDistance !== null && queryDistanceBinName && (
                                  <ReferenceLine 
                                    x={queryDistanceBinName} 
                                    stroke={queryLineColor} 
                                    strokeWidth={2}
                                    strokeDasharray="4 4"
                                    label={{ value: 'Query', position: 'top', fill: queryLineColor, fontSize: 8, fontWeight: 700 }}
                                  />
                                )}
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Chemical Class Performance Breakdown Table */}
                  {sortedClassData.length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                        <BarChart2 size={13} color="var(--color-brand-600, #3b6d11)" />
                        <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-600)', margin: 0 }}>
                          Performance Breakdown Per Chemical Family
                        </h4>
                      </div>
                      
                      <div style={{ maxHeight: '180px', overflowY: 'auto', border: '0.5px solid var(--color-border)', borderRadius: '6px' }}>
                        <table style={{ ...tableStyle, width: '100%' }}>
                          <thead>
                            <tr style={{ ...tableHeaderRowStyle, position: 'sticky', top: 0, zIndex: 10 }}>
                              <th 
                                style={{ ...tableHeaderStyle, cursor: 'pointer' }}
                                onClick={() => {
                                  setClassSortOrder(classSortBy === 'name' && classSortOrder === 'desc' ? 'asc' : 'desc');
                                  setClassSortBy('name');
                                }}
                              >
                                Chemical Family {classSortBy === 'name' ? (classSortOrder === 'desc' ? '▼' : '▲') : ''}
                              </th>
                              <th 
                                style={{ ...tableHeaderStyle, textAlign: 'right', cursor: 'pointer' }}
                                onClick={() => {
                                  setClassSortOrder(classSortBy === 'count' && classSortOrder === 'desc' ? 'asc' : 'desc');
                                  setClassSortBy('count');
                                }}
                              >
                                Count {classSortBy === 'count' ? (classSortOrder === 'desc' ? '▼' : '▲') : ''}
                              </th>
                              <th 
                                style={{ ...tableHeaderStyle, textAlign: 'right', cursor: 'pointer' }}
                                onClick={() => {
                                  setClassSortOrder(classSortBy === 'metric' && classSortOrder === 'desc' ? 'asc' : 'desc');
                                  setClassSortBy('metric');
                                }}
                              >
                                {sortedClassData[0]?.metricName || 'Error Metric'} {classSortBy === 'metric' ? (classSortOrder === 'desc' ? '▼' : '▲') : ''}
                              </th>
                              <th 
                                style={{ ...tableHeaderStyle, textAlign: 'right', cursor: 'pointer' }}
                                onClick={() => {
                                  setClassSortOrder(classSortBy === 'ad_coverage' && classSortOrder === 'desc' ? 'asc' : 'desc');
                                  setClassSortBy('ad_coverage');
                                }}
                              >
                                AD Coverage {classSortBy === 'ad_coverage' ? (classSortOrder === 'desc' ? '▼' : '▲') : ''}
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {sortedClassData.map((row, idx) => (
                              <tr key={idx} style={tableBodyRowStyle}>
                                <td style={{ ...tableCellStyle, fontWeight: 500, color: 'var(--color-text-900)' }}>{row.name}</td>
                                <td style={{ ...tableCellStyle, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{row.count}</td>
                                <td style={{ ...tableCellStyle, textAlign: 'right', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                                  {row.metric.toFixed(4)}
                                  {row.coverage !== undefined && (
                                    <span style={{ fontSize: '8px', color: 'var(--color-text-400)', marginLeft: '4px' }}>
                                      ({(row.coverage * 100).toFixed(0)}% cov)
                                    </span>
                                  )}
                                </td>
                                <td style={{ ...tableCellStyle, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                                  <span style={{
                                    color: row.ad_coverage >= 0.8 ? '#16a34a' : row.ad_coverage >= 0.5 ? '#d97706' : '#dc2626',
                                    fontWeight: 600
                                  }}>
                                    {(row.ad_coverage * 100).toFixed(0)}%
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer Section */}
        <div style={footerStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, flexWrap: 'wrap' }}>
            {authors && authors.length > 0 && (
              <div style={footerItemStyle} title="Model Authors / Computational Chemists">
                <Users size={11} style={{ marginRight: '3px' }} />
                <span>{authors.join(', ')}</span>
              </div>
            )}
            <div style={footerItemStyle} title="System Creation Timestamp">
              <Calendar size={11} style={{ marginRight: '3px' }} />
              <span>{created ? new Date(created).toLocaleDateString() : 'Unknown Date'}</span>
            </div>
            <div style={footerItemStyle} title="Distribution License">
              <Shield size={11} style={{ marginRight: '3px' }} />
              <span style={{ textTransform: 'uppercase' }}>{license}</span>
            </div>
          </div>

          <button 
            onClick={onClose}
            className="workflow-btn-configure"
            style={{ height: '28px', padding: '0 16px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            Dismiss
          </button>
        </div>
      </div>
      
      {/* Keyframe animation for modal slide up */}
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes modalSlideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}} />
    </div>
  );
}

// ── Inlined Layout Styles ──────────────────────────────────────────

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: 'rgba(15, 23, 42, 0.65)',
  backdropFilter: 'blur(3px)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 9999,
};

const modalStyle: React.CSSProperties = {
  width: '560px',
  maxHeight: '85vh',
  background: 'var(--color-surface, #ffffff)',
  border: '0.5px solid var(--color-border, #e5e5e0)',
  borderRadius: '12px',
  boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  animation: 'modalSlideUp 200ms ease-out',
};

const headerStyle: React.CSSProperties = {
  padding: '16px 20px',
  borderBottom: '0.5px solid var(--color-border, #e5e5e0)',
  background: 'var(--color-bg, #f5f5f0)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '16px',
};

const closeBtnStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  padding: '4px',
  borderRadius: '4px',
  color: 'var(--color-text-400)',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'all 120ms ease',
};

const bodyStyle: React.CSSProperties = {
  flex: 1,
  padding: '20px',
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: '16px',
};

const sectionStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
};

const sectionTitleStyle: React.CSSProperties = {
  fontSize: '11px',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  margin: 0,
  color: 'var(--color-text-900, #1a1a1a)',
};

const paragraphStyle: React.CSSProperties = {
  fontSize: '11px',
  lineHeight: '1.5',
  color: 'var(--color-text-600, #5a5a5a)',
  margin: '4px 0 0 0',
};

const intendedUseBoxStyle: React.CSSProperties = {
  marginTop: '8px',
  background: 'var(--color-brand-100, #eaf3de)',
  borderLeft: '3px solid var(--color-brand-600, #3b6d11)',
  padding: '8px 10px',
  borderRadius: '0 6px 6px 0',
  fontSize: '10px',
  lineHeight: '1.4',
  color: 'var(--color-text-900, #1a1a1a)',
};

const warningBoxStyle: React.CSSProperties = {
  background: 'var(--color-red-100, #fceae5)',
  border: '0.5px solid rgba(153, 60, 29, 0.3)',
  borderRadius: '8px',
  padding: '12px 14px',
  display: 'flex',
  flexDirection: 'column',
};

const bulletListStyle: React.CSSProperties = {
  paddingLeft: '16px',
  margin: '4px 0 0 0',
  fontSize: '10px',
  lineHeight: '1.5',
  color: 'var(--color-text-600, #5a5a5a)',
  listStyleType: 'disc',
};

const collapsibleHeaderStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  padding: '0 0 6px 0',
  borderBottom: '0.5px solid var(--color-border)',
  width: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  cursor: 'pointer',
  textAlign: 'left',
};

const collapsibleContentStyle: React.CSSProperties = {
  paddingTop: '10px',
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
};

const gridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, 1fr)',
  gap: '8px 16px',
};

const gridItemStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
};

const gridLabelStyle: React.CSSProperties = {
  fontSize: '9px',
  color: 'var(--color-text-400)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
  fontWeight: 600,
};

const gridValueStyle: React.CSSProperties = {
  fontSize: '11px',
  fontWeight: 600,
  color: 'var(--color-text-900)',
};

const tagStyle: React.CSSProperties = {
  background: 'var(--color-bg)',
  border: '0.5px solid var(--color-border)',
  borderRadius: '4px',
  padding: '2px 6px',
  fontSize: '9px',
  color: 'var(--color-text-600)',
  fontWeight: 500,
};

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '10px',
};

const tableHeaderRowStyle: React.CSSProperties = {
  background: 'var(--color-bg)',
  borderBottom: '1px solid var(--color-border)',
};

const tableHeaderStyle: React.CSSProperties = {
  padding: '6px 8px',
  fontWeight: 700,
  color: 'var(--color-text-600)',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
  textAlign: 'left',
};

const tableBodyRowStyle: React.CSSProperties = {
  borderBottom: '0.5px solid var(--color-border-subtle)',
};

const tableCellStyle: React.CSSProperties = {
  padding: '6px 8px',
  color: 'var(--color-text-600)',
};

const calloutBoxStyle: React.CSSProperties = {
  background: 'var(--color-bg)',
  border: '0.5px solid var(--color-border)',
  borderRadius: '6px',
  padding: '10px 12px',
};

const linkStyle: React.CSSProperties = {
  color: 'var(--color-blue-500)',
  textDecoration: 'none',
  wordBreak: 'break-all',
};

const footerStyle: React.CSSProperties = {
  padding: '12px 20px',
  borderTop: '0.5px solid var(--color-border, #e5e5e0)',
  background: 'var(--color-bg, #f5f5f0)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '16px',
};

const footerItemStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  fontSize: '9px',
  color: 'var(--color-text-400)',
  fontWeight: 600,
};

const loaderStyle: React.CSSProperties = {
  width: '24px',
  height: '24px',
  border: '2.5px solid var(--color-border)',
  borderTopColor: 'var(--color-brand-600)',
  borderRadius: '50%',
};
