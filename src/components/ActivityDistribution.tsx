import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export interface ActivityStats {
  model_type: 'regression' | 'classification';
  min?: number;
  max?: number;
  median?: number;
  mean?: number;
  q1?: number;
  q3?: number;
  iqr?: number;
  std?: number;
  dynamic_range?: number;
  histogram?: {
    bins: number[];
    counts: number[];
  };
  range_warning?: boolean;
  class_counts?: {
    '0': number;
    '1': number;
  };
  imbalance_ratio?: number;
  imbalance_warning?: boolean;
  imbalance_recommendation?: 'class_weight' | 'smote' | null;
}

interface ActivityDistributionProps {
  stats: ActivityStats;
}

export function ActivityDistribution({ stats }: ActivityDistributionProps) {
  if (stats.model_type === 'regression' && stats.histogram) {
    // Format histogram data for Recharts BarChart
    const data = stats.histogram.bins.map((binVal, idx) => ({
      name: binVal.toFixed(2),
      count: stats.histogram!.counts[idx],
    }));

    return (
      <div className="activity-distribution-regression" style={{ marginTop: '16px' }}>
        <div className="config-section-title" style={{ fontSize: '10px', marginBottom: '8px' }}>
          📈 Curated Activity Distribution Histogram (20 bins)
        </div>

        {/* Recharts BarChart */}
        <div style={{ width: '100%', height: '160px', marginBottom: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 5, right: 5, left: -25, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" />
              <XAxis dataKey="name" stroke="var(--color-text-400)" fontSize={8} tickLine={false} />
              <YAxis stroke="var(--color-text-400)" fontSize={8} tickLine={false} />
              <Tooltip
                contentStyle={{
                  background: 'var(--color-bg-dark)',
                  borderColor: 'var(--color-border)',
                  fontSize: '10px',
                  borderRadius: '4px',
                }}
                labelFormatter={(label) => `Activity Bin Center: ${label}`}
              />
              <Bar dataKey="count" fill="var(--color-brand-600)" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Descriptive Statistics Strip */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gap: '6px',
            textAlign: 'center',
            background: 'var(--color-bg-dark)',
            padding: '10px',
            borderRadius: '6px',
            border: '0.5px solid var(--color-border-subtle)',
          }}
        >
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700 }}>{stats.min?.toFixed(2) ?? '—'}</div>
            <div style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Min</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700 }}>{stats.q1?.toFixed(2) ?? '—'}</div>
            <div style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Q1</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700 }}>{stats.median?.toFixed(2) ?? '—'}</div>
            <div style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Median</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700 }}>{stats.mean?.toFixed(2) ?? '—'}</div>
            <div style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Mean</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700 }}>{stats.q3?.toFixed(2) ?? '—'}</div>
            <div style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Q3</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700 }}>{stats.max?.toFixed(2) ?? '—'}</div>
            <div style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Max</div>
          </div>
          <div>
            <div
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: stats.range_warning ? 'var(--color-amber-700)' : 'var(--color-brand-700)',
              }}
            >
              {stats.dynamic_range?.toFixed(2) ?? '—'}
            </div>
            <div style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Range</div>
          </div>
        </div>

        {/* Dynamic Range Warning Callout */}
        {stats.range_warning && (
          <div
            className="workflow-error"
            style={{
              marginTop: '10px',
              fontSize: '10px',
              background: 'rgba(245, 158, 11, 0.08)',
              border: '0.5px solid rgba(245, 158, 11, 0.4)',
              color: 'var(--color-amber-900)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>⚠</span>
            <span>
              Dynamic range is only <strong>{stats.dynamic_range?.toFixed(2)} log units</strong>; QSAR
              signal may be insufficient. <strong>&ge; 2.0</strong> recommended for robust regression modeling.
            </span>
          </div>
        )}
      </div>
    );
  }

  if (stats.model_type === 'classification' && stats.class_counts) {
    const total = stats.class_counts['0'] + stats.class_counts['1'];
    const pct0 = total > 0 ? (stats.class_counts['0'] / total) * 100 : 0;
    const pct1 = total > 0 ? (stats.class_counts['1'] / total) * 100 : 0;

    return (
      <div className="activity-distribution-classification" style={{ marginTop: '16px' }}>
        <div className="config-section-title" style={{ fontSize: '10px', marginBottom: '8px' }}>
          📈 Curated Classification Label Balance
        </div>

        {/* Stacked Proportional Bar Layout */}
        <div
          style={{
            display: 'flex',
            height: '24px',
            borderRadius: '6px',
            overflow: 'hidden',
            background: 'var(--color-border-subtle)',
            marginBottom: '10px',
          }}
        >
          {stats.class_counts['0'] > 0 && (
            <div
              style={{
                width: `${pct0}%`,
                background: 'var(--color-brand-600)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
                fontSize: '10px',
                fontWeight: 'bold',
                minWidth: '50px',
                transition: 'width 0.3s ease',
              }}
              title={`Class 0 (Safe): ${stats.class_counts['0']} compounds`}
            >
              Safe (0): {stats.class_counts['0']} ({pct0.toFixed(0)}%)
            </div>
          )}
          {stats.class_counts['1'] > 0 && (
            <div
              style={{
                width: `${pct1}%`,
                background: 'var(--color-red-500)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
                fontSize: '10px',
                fontWeight: 'bold',
                minWidth: '50px',
                transition: 'width 0.3s ease',
              }}
              title={`Class 1 (Toxic): ${stats.class_counts['1']} compounds`}
            >
              Toxic (1): {stats.class_counts['1']} ({pct1.toFixed(0)}%)
            </div>
          )}
        </div>

        {/* Statistics Grid */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            background: 'var(--color-bg-dark)',
            padding: '8px 12px',
            borderRadius: '6px',
            border: '0.5px solid var(--color-border-subtle)',
            fontSize: '10px',
          }}
        >
          <span>
            Total Compounds: <strong>{total}</strong>
          </span>
          <span>
            Label Balance Ratio:{' '}
            <strong style={{ color: stats.imbalance_warning ? 'var(--color-amber-700)' : 'var(--color-brand-700)' }}>
              {stats.imbalance_ratio?.toFixed(1) ?? '1.0'}:1
            </strong>
          </span>
          <span
            style={{
              color: stats.imbalance_warning ? 'var(--color-amber-700)' : 'var(--color-brand-700)',
              fontWeight: 'bold',
            }}
          >
            {stats.imbalance_warning ? '⚠️ Imbalanced' : '✓ Balanced'}
          </span>
        </div>

        {/* Dynamic Class Imbalance Recommendation Callout */}
        {stats.imbalance_warning && (
          <div
            className="workflow-error"
            style={{
              marginTop: '10px',
              fontSize: '10px',
              background: 'rgba(245, 158, 11, 0.08)',
              border: '0.5px solid rgba(245, 158, 11, 0.4)',
              color: 'var(--color-amber-900)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>⚠️</span>
            <span>
              Class imbalance <strong>{stats.imbalance_ratio?.toFixed(1)}:1</strong> detected. Consider
              enabling{' '}
              <strong>
                {stats.imbalance_recommendation === 'smote' ? 'SMOTE (oversampling)' : 'Class Weighting'}
              </strong>{' '}
              mitigation in Step 2. (Automatically pre-selected).
            </span>
          </div>
        )}
      </div>
    );
  }

  return null;
}
