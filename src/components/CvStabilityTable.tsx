interface CvRow {
  fold: number | 'summary';
  n_train?: number;
  n_val?: number;
  r2_val?: number;
  rmse_val?: number;
  mae_val?: number;
  r2_train?: number;
  accuracy_val?: number;
  f1_score?: number;
  auc_roc?: number;
  accuracy_train?: number;
  mean?: number;
  std?: number;
  min?: number;
  max?: number;
  n_folds?: number;
  error?: string;
}

interface CvStabilityTableProps {
  cvResults: CvRow[];
  modelType: 'regression' | 'classification';
}

export function CvStabilityTable({ cvResults, modelType }: CvStabilityTableProps) {
  if (!cvResults || cvResults.length === 0) return null;

  const foldRows = cvResults.filter((r) => r.fold !== 'summary');
  const summary = cvResults.find((r) => r.fold === 'summary');

  const primaryLabel = modelType === 'regression' ? 'R² Val' : 'Acc Val';

  const getColor = (val: number | undefined) => {
    if (val == null) return 'var(--color-text-400)';
    if (modelType === 'regression') {
      return val > 0.7 ? 'var(--color-brand-700)' : val > 0.4 ? 'var(--color-amber-700)' : 'var(--color-red-700)';
    } else {
      return val > 0.8 ? 'var(--color-brand-700)' : val > 0.6 ? 'var(--color-amber-700)' : 'var(--color-red-700)';
    }
  };

  const fmt = (v: number | undefined, isPercent = false) => {
    if (v == null) return '—';
    if (isPercent) return `${(v * 100).toFixed(1)}%`;
    return v.toFixed(3);
  };

  return (
    <div style={{ marginBottom: '16px' }}>
      <div className="plot-title">Cross-Validation Stability</div>

      {summary && (
        <div style={{
          display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px', marginTop: '6px',
        }}>
          {(['mean', 'std', 'min', 'max'] as const).map((k) => {
            const val = summary[k];
            const isPercent = modelType === 'classification';
            return (
              <div key={k} style={{
                flex: '1 1 60px', background: 'var(--color-bg)', border: '0.5px solid var(--color-border)',
                borderRadius: '6px', padding: '6px 8px', textAlign: 'center',
              }}>
                <div style={{
                  fontSize: '13px', fontWeight: 700,
                  color: k === 'mean' ? getColor(val) : 'var(--color-text-200)',
                }}>
                  {fmt(val, isPercent)}
                </div>
                <div style={{ fontSize: '9px', color: 'var(--color-text-400)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {k === 'mean' ? `Mean ${primaryLabel}` : k === 'std' ? 'Std Dev' : k === 'min' ? 'Min' : 'Max'}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <table style={{ width: '100%', fontSize: '10px', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: 'var(--color-border-subtle)', textAlign: 'left' }}>
            <th style={{ padding: '5px 6px' }}>Fold</th>
            <th style={{ padding: '5px 6px' }}>Train N</th>
            <th style={{ padding: '5px 6px' }}>Val N</th>
            <th style={{ padding: '5px 6px' }}>{primaryLabel}</th>
            {modelType === 'regression' ? (
              <>
                <th style={{ padding: '5px 6px' }}>RMSE</th>
                <th style={{ padding: '5px 6px' }}>MAE</th>
                <th style={{ padding: '5px 6px' }}>R² Train</th>
              </>
            ) : (
              <>
                <th style={{ padding: '5px 6px' }}>F1</th>
                <th style={{ padding: '5px 6px' }}>AUC</th>
                <th style={{ padding: '5px 6px' }}>Acc Train</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {foldRows.map((row, i) => (
            <tr key={i} style={{
              borderBottom: '0.5px solid var(--color-border-subtle)',
              background: i % 2 === 0 ? 'transparent' : 'var(--color-bg)',
            }}>
              <td style={{ padding: '4px 6px', fontWeight: 600 }}>
                {row.error ? `#${row.fold} ⚠` : `#${row.fold}`}
              </td>
              <td style={{ padding: '4px 6px', color: 'var(--color-text-400)' }}>{row.n_train ?? '—'}</td>
              <td style={{ padding: '4px 6px', color: 'var(--color-text-400)' }}>{row.n_val ?? '—'}</td>
              {row.error ? (
                <td colSpan={4} style={{ padding: '4px 6px', color: 'var(--color-red-700)', fontSize: '9px' }}>
                  {row.error}
                </td>
              ) : modelType === 'regression' ? (
                <>
                  <td style={{ padding: '4px 6px', fontWeight: 600, color: getColor(row.r2_val) }}>{fmt(row.r2_val)}</td>
                  <td style={{ padding: '4px 6px' }}>{fmt(row.rmse_val)}</td>
                  <td style={{ padding: '4px 6px' }}>{fmt(row.mae_val)}</td>
                  <td style={{ padding: '4px 6px', color: 'var(--color-text-400)' }}>{fmt(row.r2_train)}</td>
                </>
              ) : (
                <>
                  <td style={{ padding: '4px 6px', fontWeight: 600, color: getColor(row.accuracy_val) }}>{fmt(row.accuracy_val, true)}</td>
                  <td style={{ padding: '4px 6px' }}>{fmt(row.f1_score, true)}</td>
                  <td style={{ padding: '4px 6px' }}>{fmt(row.auc_roc, true)}</td>
                  <td style={{ padding: '4px 6px', color: 'var(--color-text-400)' }}>{fmt(row.accuracy_train, true)}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {summary && summary.std != null && summary.mean != null && (
        <div style={{
          marginTop: '6px', fontSize: '9px',
          color: summary.std / Math.max(0.01, Math.abs(summary.mean)) < 0.2
            ? 'var(--color-brand-700)' : 'var(--color-amber-700)',
          fontWeight: 500,
        }}>
          {summary.std / Math.max(0.01, Math.abs(summary.mean)) < 0.2
            ? '✓ Low CV variability — model generalises consistently'
            : '⚠ High CV variability — consider more data or regularization'}
        </div>
      )}
    </div>
  );
}
