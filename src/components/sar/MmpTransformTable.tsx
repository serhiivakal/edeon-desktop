import React from 'react';
import { SelectivityTransform } from '../../store/sarStore';

interface MmpTransformTableProps {
  transforms: SelectivityTransform[];
}

export const MmpTransformTable: React.FC<MmpTransformTableProps> = ({ transforms }) => {
  if (!transforms || transforms.length === 0) {
    return (
      <div style={{ padding: '16px', fontSize: '12px', color: 'var(--color-text-400)', textAlign: 'center' }}>
        No matched molecular pair transforms indexed yet. Click "Analyze Library MMPs" to extract selectivity rules.
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto', borderRadius: '8px', border: '0.5px solid var(--color-border)', background: 'var(--color-surface)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
        <thead>
          <tr style={{ background: 'rgba(0,0,0,0.03)', borderBottom: '1px solid var(--color-border)' }}>
            <th style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--color-text-600)' }}>Transformation (R1 &rarr; R2)</th>
            <th style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--color-text-600)' }}>Pairs Count</th>
            <th style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--color-text-600)' }}>&Delta; Selectivity</th>
            <th style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--color-text-600)' }}>&Delta; Target Potency</th>
            <th style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--color-text-600)' }}>&Delta; Off-Target</th>
            <th style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--color-text-600)' }}>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {transforms.map((t, idx) => (
            <tr key={idx} style={{ borderBottom: '0.5px solid var(--color-border)' }}>
              <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontSize: '11px', color: 'var(--color-text-900)' }}>
                {t.transform}
              </td>
              <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--color-text-700)' }}>
                {t.count}
              </td>
              <td style={{ padding: '8px 12px', fontWeight: 700, color: t.mean_delta_selectivity > 0 ? '#10b981' : '#ef4444' }}>
                {t.mean_delta_selectivity > 0 ? `+${t.mean_delta_selectivity.toFixed(2)}` : t.mean_delta_selectivity.toFixed(2)}
              </td>
              <td style={{ padding: '8px 12px', color: 'var(--color-text-700)' }}>
                {t.mean_delta_potency > 0 ? `+${t.mean_delta_potency.toFixed(2)}` : t.mean_delta_potency.toFixed(2)}
              </td>
              <td style={{ padding: '8px 12px', color: 'var(--color-text-700)' }}>
                {t.mean_delta_off_target > 0 ? `+${t.mean_delta_off_target.toFixed(2)}` : t.mean_delta_off_target.toFixed(2)}
              </td>
              <td style={{ padding: '8px 12px' }}>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 600,
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: t.confidence === 'high' ? 'rgba(16, 185, 129, 0.15)' : t.confidence === 'medium' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(107, 114, 128, 0.15)',
                    color: t.confidence === 'high' ? '#10b981' : t.confidence === 'medium' ? '#f59e0b' : '#6b7280',
                  }}
                >
                  {t.confidence.toUpperCase()}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
