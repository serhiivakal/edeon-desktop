import { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Prediction } from '../../types';
import { ModelTierBadge } from './ModelTierBadge';
import { ADWarning } from './ADWarning';
import { VerificationBadge } from '../shared/VerificationBadge';
import { ReproducibilityInfo } from '../shared/ReproducibilityInfo';

export interface PredictionDisplayProps {
  prediction: Prediction;
  onClick?: () => void;
}

const OPERA_SUPPORTED_ENDPOINTS = [
  'soil_koc',
  'bcf',
  'soil_dt50',
  'rat_acute_oral_ld50',
  'logp',
  'pka',
  'solubility',
  'henrys_law'
];

export function PredictionDisplay({ prediction, onClick }: PredictionDisplayProps) {
  const { value, units, ci_lower, ci_upper, ad_status, ad_score, tier, warnings } = prediction;
  
  const [showCompare, setShowCompare] = useState(false);
  const [operaPrediction, setOperaPrediction] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isOperaSupported = OPERA_SUPPORTED_ENDPOINTS.includes(prediction.endpoint);

  const renderValue = () => {
    switch (value.kind) {
      case 'numeric':
        return (
          <span style={{ fontWeight: 700, fontSize: '15px', color: 'var(--color-text-900, #1a1a1a)' }}>
            {value.numeric.toFixed(3)}
            {units && <span style={{ fontSize: '11px', fontWeight: 500, color: 'var(--color-text-600, #5a5a5a)', marginLeft: '4px' }}>{units}</span>}
          </span>
        );
      case 'categorical':
        return (
          <span style={{ fontWeight: 700, fontSize: '15px', color: 'var(--color-text-900, #1a1a1a)' }}>
            {value.categorical}
          </span>
        );
      case 'binary':
        return (
          <span style={{ fontWeight: 700, fontSize: '15px', color: 'var(--color-text-900, #1a1a1a)' }}>
            {value.binary ? 'Active' : 'Inactive'}
          </span>
        );
      default:
        return <span style={{ color: 'var(--color-text-400)' }}>—</span>;
    }
  };

  const renderOperaValue = (val: typeof value, unitStr: string) => {
    switch (val.kind) {
      case 'numeric':
        return `${val.numeric.toFixed(3)} ${unitStr}`;
      case 'categorical':
        return val.categorical;
      case 'binary':
        return val.binary ? 'Active' : 'Inactive';
      default:
        return '—';
    }
  };

  const handleOpenCompare = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowCompare(true);
    setLoading(true);
    setError(null);
    try {
      const response = await invoke<Prediction[]>('model_predict', {
        endpoint: prediction.endpoint,
        smiles: [prediction.smiles],
        preferredTier: 3
      });
      if (response && response.length > 0) {
        setOperaPrediction(response[0]);
      } else {
        setError('No prediction returned from OPERA.');
      }
    } catch (err: any) {
      console.error('[PredictionDisplay] Failed to fetch OPERA prediction:', err);
      setError(err?.toString() || 'Failed to fetch OPERA prediction.');
    } finally {
      setLoading(false);
    }
  };

  const getLogValue = (val: number, endpoint: string): number => {
    if (val <= 0) return 0;
    if (['soil_koc', 'bcf', 'soil_dt50', 'rat_acute_oral_ld50', 'solubility', 'henrys_law'].includes(endpoint)) {
      return Math.log10(val);
    }
    return val; // logp is already log units
  };

  // Compare predictions for warnings/discrepancies
  let discrepancyText = "";
  let isSignificantDiscrepancy = false;
  let isDomainConflict = false;

  if (operaPrediction) {
    if (value.kind === 'numeric' && operaPrediction.value.kind === 'numeric') {
      const val1 = value.numeric;
      const val2 = operaPrediction.value.numeric;
      
      const logVal1 = getLogValue(val1, prediction.endpoint);
      const logVal2 = getLogValue(val2, prediction.endpoint);
      
      const diff = Math.abs(logVal1 - logVal2);
      isSignificantDiscrepancy = diff > 0.5;
      
      if (prediction.endpoint === 'logp') {
        discrepancyText = `${diff.toFixed(3)} units`;
      } else {
        discrepancyText = `${diff.toFixed(3)} log units`;
      }
    }

    isDomainConflict = 
      (ad_status === 'in' && operaPrediction.ad_status === 'out') ||
      (ad_status === 'out' && operaPrediction.ad_status === 'in');
  }

  const hasCi = ci_lower !== null && ci_upper !== null;

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        padding: '10px 12px',
        background: 'var(--color-surface, #ffffff)',
        border: '0.5px solid var(--color-border, #e5e5e0)',
        borderRadius: '6px',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 150ms ease-in-out',
        boxShadow: onClick ? 'var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.04))' : 'none',
        userSelect: 'none',
      }}
      className={onClick ? 'prediction-display-interactive' : ''}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
        {/* Left Side: Primary Value */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {renderValue()}
          {prediction.provenance && (
            <ReproducibilityInfo provenance={prediction.provenance} modelId={prediction.model_id} />
          )}
        </div>

        {/* Right Side: Badges inlined */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {isOperaSupported && (
            <button
              onClick={handleOpenCompare}
              style={{
                background: 'rgba(59, 130, 246, 0.08)',
                color: '#3b82f6',
                border: 'none',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '9px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 120ms ease',
                display: 'flex',
                alignItems: 'center',
                gap: '2px',
              }}
              title="Compare with US EPA OPERA Tier-3 Reference"
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(59, 130, 246, 0.08)';
              }}
            >
              📊 Compare OPERA
            </button>
          )}
          {tier === 1 && <VerificationBadge endpoint={prediction.endpoint} verified={true} variant="compact" />}
          <ModelTierBadge tier={tier} />
          <ADWarning status={ad_status} score={ad_score ?? undefined} />
        </div>
      </div>

      {/* Confidence Intervals (smaller, below value) */}
      {hasCi && (
        <div style={{ fontSize: '10px', color: 'var(--color-text-600, #5a5a5a)', fontWeight: 500 }}>
          95% Conformal CI: <span style={{ fontFamily: 'var(--font-mono, monospace)', background: 'var(--color-bg, #f5f5f0)', padding: '1px 4px', borderRadius: '4px', border: '0.5px solid var(--color-border, #e5e5e0)' }}>
            [{ci_lower.toFixed(3)} — {ci_upper.toFixed(3)}]
          </span>
        </div>
      )}

      {/* Experimental Values Overlay Row */}
      {prediction.provenance?.experimental_values && prediction.provenance.experimental_values.length > 0 && (
        <div style={{ 
          fontSize: '10px', 
          color: 'var(--color-brand-700, #3c6e11)', 
          fontWeight: 600, 
          display: 'flex', 
          flexDirection: 'column',
          gap: '2px',
          marginTop: '4px',
          paddingTop: '4px',
          borderTop: '0.5px solid var(--color-border, #e5e5e0)'
        }}>
          {prediction.provenance.experimental_values.map((exp: any, i: number) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
              <span>
                🧪 Measured: <span style={{ fontFamily: 'var(--font-mono, monospace)', background: 'rgba(60, 110, 17, 0.05)', padding: '1px 4px', borderRadius: '4px' }}>
                  {exp.value} {exp.units}
                </span>
              </span>
              <span style={{ fontSize: '9px', fontWeight: 500, color: 'var(--color-text-500, #7a7a7a)', fontStyle: 'italic' }} title={exp.citation || undefined}>
                ({exp.source})
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Warnings (if any) as small italic note below */}
      {warnings && warnings.length > 0 && (
        <div style={{ fontSize: '9px', fontStyle: 'italic', color: 'var(--color-red-700, #993c1d)', marginTop: '2px', display: 'flex', gap: '4px', alignItems: 'center' }}>
          <span>⚠</span>
          <span>{warnings.join('; ')}</span>
        </div>
      )}

      {/* Comparison Modal Dialog */}
      {showCompare && (
        <div
          onClick={(e) => {
            e.stopPropagation();
            setShowCompare(false);
          }}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.6)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '20px',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%',
              maxWidth: '560px',
              background: 'var(--color-surface, #ffffff)',
              borderRadius: '12px',
              border: '1px solid var(--color-border, #e5e5e0)',
              boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)',
              display: 'flex',
              flexDirection: 'column',
              maxHeight: '90vh',
              overflow: 'hidden',
            }}
          >
            {/* Header */}
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid var(--color-border, #e5e5e0)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <span style={{ fontSize: '15px', fontWeight: 650, color: 'var(--color-text-900, #1a1a1a)' }}>
                OPERA Tier-3 Cross-Reference Comparison
              </span>
              <button
                onClick={() => setShowCompare(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '18px',
                  color: 'var(--color-text-400, #a0a0a0)',
                  cursor: 'pointer',
                  padding: '4px',
                  lineHeight: 1,
                }}
              >
                ×
              </button>
            </div>

            {/* Content Scrollable */}
            <div style={{ padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              
              {/* SMILES and Endpoint Info */}
              <div style={{ fontSize: '11px', color: 'var(--color-text-600, #5a5a5a)', background: 'var(--color-bg, #f5f5f0)', padding: '10px', borderRadius: '6px', border: '0.5px solid var(--color-border, #e5e5e0)' }}>
                <div style={{ marginBottom: '4px' }}>
                  <strong>Endpoint:</strong> {prediction.endpoint}
                </div>
                <div style={{ wordBreak: 'break-all', fontFamily: 'var(--font-mono, monospace)', fontSize: '10px' }}>
                  <strong>SMILES:</strong> {prediction.smiles}
                </div>
              </div>

              {loading && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 0', gap: '12px' }}>
                  <div style={{
                    width: '32px',
                    height: '32px',
                    border: '3px solid rgba(59, 130, 246, 0.1)',
                    borderTopColor: '#3b82f6',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite',
                  }} />
                  <style dangerouslySetInnerHTML={{__html: `
                    @keyframes spin { to { transform: rotate(360deg); } }
                  `}} />
                  <span style={{ fontSize: '12px', color: 'var(--color-text-600, #5a5a5a)', fontWeight: 550 }}>Invoking local OPERA engine...</span>
                </div>
              )}

              {error && (
                <div style={{ padding: '16px', background: '#fef2f2', border: '1px solid #fee2e2', borderRadius: '6px', color: '#b91c1c', fontSize: '12px', display: 'flex', gap: '8px' }}>
                  <span>❌</span>
                  <span>{error}</span>
                </div>
              )}

              {!loading && !error && operaPrediction && (
                <>
                  {/* Side-by-Side Cards */}
                  <div style={{ display: 'flex', gap: '12px' }}>
                    {/* Edeon Backend Card */}
                    <div style={{
                      flex: 1,
                      padding: '14px',
                      borderRadius: '8px',
                      border: '1px solid rgba(74, 117, 26, 0.3)',
                      background: 'linear-gradient(135deg, rgba(244, 248, 240, 0.4) 0%, rgba(255, 255, 255, 1) 100%)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '11px', fontWeight: 650, color: '#3c6e11' }}>Edeon Reference</span>
                        <ModelTierBadge tier={tier} />
                      </div>
                      <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-text-900, #1a1a1a)' }}>
                        {renderValue()}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '10px', color: 'var(--color-text-600)' }}>
                        <div><strong>AD:</strong> <ADWarning status={ad_status} score={ad_score ?? undefined} /></div>
                        {hasCi && <div><strong>CI:</strong> [{ci_lower.toFixed(2)} - {ci_upper.toFixed(2)}]</div>}
                        <div style={{ fontSize: '9px', fontStyle: 'italic', color: '#7a7a7a' }}>{prediction.model_id}</div>
                      </div>
                    </div>

                    {/* OPERA Card */}
                    <div style={{
                      flex: 1,
                      padding: '14px',
                      borderRadius: '8px',
                      border: '1px solid rgba(59, 130, 246, 0.3)',
                      background: 'linear-gradient(135deg, rgba(239, 246, 255, 0.4) 0%, rgba(255, 255, 255, 1) 100%)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '11px', fontWeight: 650, color: '#2563eb' }}>EPA OPERA</span>
                        <ModelTierBadge tier={3} />
                      </div>
                      <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-text-900, #1a1a1a)' }}>
                        {renderOperaValue(operaPrediction.value, operaPrediction.units)}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '10px', color: 'var(--color-text-600)' }}>
                        <div><strong>AD:</strong> <ADWarning status={operaPrediction.ad_status} score={operaPrediction.ad_score ?? undefined} /></div>
                        {operaPrediction.provenance?.confidence_index !== undefined && (
                          <div><strong>Accuracy index:</strong> {operaPrediction.provenance.confidence_index}</div>
                        )}
                        <div style={{ fontSize: '9px', fontStyle: 'italic', color: '#7a7a7a' }}>{operaPrediction.model_id}</div>
                      </div>
                    </div>
                  </div>

                  {/* Discrepancy & Conflict Banners */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    
                    {/* Value Delta */}
                    {discrepancyText && (
                      <div style={{
                        padding: '12px 14px',
                        borderRadius: '6px',
                        background: isSignificantDiscrepancy ? '#fef2f2' : '#f0fdf4',
                        border: `1px solid ${isSignificantDiscrepancy ? '#fee2e2' : '#dcfce7'}`,
                        color: isSignificantDiscrepancy ? '#991b1b' : '#166534',
                        fontSize: '11px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '2px',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                          <span>Prediction Discrepancy (Δ):</span>
                          <span>{discrepancyText}</span>
                        </div>
                        {isSignificantDiscrepancy && (
                          <div style={{ fontSize: '10px', marginTop: '4px', opacity: 0.9 }}>
                            ⚠ Discrepancy exceeds 0.5 log units. This chemical space may have high model uncertainty.
                          </div>
                        )}
                      </div>
                    )}

                    {/* AD Conflict */}
                    {isDomainConflict && (
                      <div style={{
                        padding: '10px 12px',
                        borderRadius: '6px',
                        background: '#fffbeb',
                        border: '1px solid #fef3c7',
                        color: '#92400e',
                        fontSize: '11px',
                        display: 'flex',
                        gap: '6px',
                        fontWeight: 550,
                      }}>
                        <span>⚠️</span>
                        <span>
                          <strong>Domain Conflict:</strong> One model classifies this compound as IN domain while the other classifies it as OUT.
                        </span>
                      </div>
                    )}

                    {/* Mock mode indicator */}
                    {operaPrediction.provenance?.warnings?.some((w: string) => w.includes("mock mode")) && (
                      <div style={{
                        padding: '10px 12px',
                        borderRadius: '6px',
                        background: 'var(--color-bg, #f5f5f0)',
                        border: '1px solid var(--color-border, #e5e5e0)',
                        color: 'var(--color-text-600, #5a5a5a)',
                        fontSize: '10px',
                        display: 'flex',
                        gap: '6px',
                        fontStyle: 'italic',
                      }}>
                        <span>ℹ</span>
                        <span>OPERA binary was not found locally; displaying calculated mock values with a small shift (+0.1 log units).</span>
                      </div>
                    )}

                  </div>
                </>
              )}

            </div>

            {/* Footer */}
            <div style={{
              padding: '12px 20px',
              borderTop: '1px solid var(--color-border, #e5e5e0)',
              display: 'flex',
              justifyContent: 'flex-end',
              background: 'var(--color-bg, #f9f9f6)',
            }}>
              <button
                onClick={() => setShowCompare(false)}
                style={{
                  background: 'var(--color-surface, #ffffff)',
                  border: '1px solid var(--color-border, #e5e5e0)',
                  borderRadius: '6px',
                  padding: '6px 16px',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--color-text-700, #3a3a3a)',
                  cursor: 'pointer',
                  transition: 'all 120ms ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--color-bg, #f5f5f0)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'var(--color-surface, #ffffff)';
                }}
              >
                Close
              </button>
            </div>

          </div>
        </div>
      )}

      {onClick && (
        <style dangerouslySetInnerHTML={{ __html: `
          .prediction-display-interactive:hover {
            border-color: var(--color-brand-600, #3b6d11) !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;
            transform: translateY(-1px);
          }
        `}} />
      )}
    </div>
  );
}
