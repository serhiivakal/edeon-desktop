import React from 'react';
import { FreeWilsonResult } from '../../store/sarStore';

interface FreeWilsonPanelProps {
  result: FreeWilsonResult | null;
}

export const FreeWilsonPanel: React.FC<FreeWilsonPanelProps> = ({ result }) => {
  if (!result || !result.ok) {
    return (
      <div style={{ padding: '16px', fontSize: '12px', color: 'var(--color-text-400)', textAlign: 'center' }}>
        No Free-Wilson model fitted yet. Click "Fit Free-Wilson Model" to decompose series R-group contributions.
      </div>
    );
  }

  return (
    <div style={{ padding: '16px', background: 'var(--color-surface)', borderRadius: '8px', border: '0.5px solid var(--color-border)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-text-900)' }}>
            Free-Wilson SAR Additive Model ({result.endpoint})
          </div>
          <div style={{ fontSize: '11px', color: 'var(--color-text-500)', marginTop: '2px' }}>
            Dominant Core: <code style={{ fontFamily: 'monospace' }}>{result.dominant_core}</code>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-brand-600)' }}>
            R<sup>2</sup> = {(result.r2_score * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>
            Intercept &mu; = {result.intercept_mu.toFixed(2)} (N = {result.n_samples})
          </div>
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
          <thead>
            <tr style={{ background: 'rgba(0,0,0,0.03)', borderBottom: '1px solid var(--color-border)' }}>
              <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Substituent Group</th>
              <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Contribution Coefficient (c<sub>j</sub>)</th>
              <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Impact</th>
            </tr>
          </thead>
          <tbody>
            {result.substituent_coefficients.map((sc, idx) => (
              <tr key={idx} style={{ borderBottom: '0.5px solid var(--color-border)' }}>
                <td style={{ padding: '6px 10px', fontFamily: 'monospace', fontSize: '11px', color: 'var(--color-text-800)' }}>
                  {sc.substituent}
                </td>
                <td style={{ padding: '6px 10px', fontWeight: 700, color: sc.coefficient > 0 ? '#10b981' : '#ef4444' }}>
                  {sc.coefficient > 0 ? `+${sc.coefficient.toFixed(3)}` : sc.coefficient.toFixed(3)}
                </td>
                <td style={{ padding: '6px 10px' }}>
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 600,
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: sc.coefficient > 0 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                      color: sc.coefficient > 0 ? '#10b981' : '#ef4444',
                    }}
                  >
                    {sc.coefficient > 0 ? 'INCREASES POTENCY' : 'DECREASES POTENCY'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
