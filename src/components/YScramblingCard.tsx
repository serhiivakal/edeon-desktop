import { BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer, Cell } from 'recharts';

interface ScrambleHistogramProps {
  scores: number[];
  trueScore: number;
}

function ScrambleHistogram({ scores, trueScore }: ScrambleHistogramProps) {
  if (!scores || scores.length === 0) return null;

  // Build 12-bin histogram from the scrambled scores
  const N_BINS = 12;
  const minVal = Math.min(...scores, trueScore - 0.05);
  const maxVal = Math.max(...scores, trueScore + 0.05);
  const range = maxVal - minVal || 0.1;
  const binWidth = range / N_BINS;

  const bins = Array.from({ length: N_BINS }, (_, i) => ({
    label: (minVal + i * binWidth).toFixed(2),
    midpoint: minVal + (i + 0.5) * binWidth,
    count: 0,
  }));

  for (const s of scores) {
    const idx = Math.min(N_BINS - 1, Math.floor((s - minVal) / binWidth));
    if (idx >= 0) bins[idx].count += 1;
  }

  const data = bins.map((b) => ({ x: b.label, count: b.count, mid: b.midpoint }));

  // Find which bin the trueScore falls in for the ReferenceLine x position
  const trueLabel = bins.reduce((best, b) =>
    Math.abs(b.midpoint - trueScore) < Math.abs(best.midpoint - trueScore) ? b : best
  ).label;

  return (
    <div style={{ height: 100, marginTop: 10, marginBottom: 6 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
          <XAxis
            dataKey="x"
            tick={{ fontSize: 8, fill: 'var(--color-text-400)' }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 8, fill: 'var(--color-text-400)' }}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--color-surface)',
              border: '0.5px solid var(--color-border)',
              fontSize: 10,
              borderRadius: 4,
            }}
            formatter={((v: unknown) => [v, 'Count']) as any}
            labelFormatter={((l: unknown) => `Score ≈ ${String(l)}`) as any}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {data.map((entry, idx) => (
              <Cell
                key={idx}
                fill={entry.mid >= trueScore
                  ? 'var(--color-red-700)'
                  : 'var(--color-text-400)'}
                fillOpacity={entry.mid >= trueScore ? 0.7 : 0.4}
              />
            ))}
          </Bar>
          <ReferenceLine
            x={trueLabel}
            stroke="var(--color-brand-600)"
            strokeWidth={2}
            strokeDasharray="4 3"
            label={{
              value: 'True',
              position: 'insideTopRight',
              fontSize: 9,
              fill: 'var(--color-brand-700)',
            }}
          />
        </BarChart>
      </ResponsiveContainer>
      <div style={{ textAlign: 'center', fontSize: 9, color: 'var(--color-text-400)', marginTop: 2 }}>
        Permuted score distribution — red bars: permutations ≥ true score
      </div>
    </div>
  );
}

interface YScramblingCardProps {
  yScramble: {
    n_iterations: number;
    primary_metric: string;
    true_score: number;
    scrambled_scores: number[];
    scrambled_mean: number;
    scrambled_std: number;
    z_score: number;
    p_value: number;
    verdict: 'robust' | 'marginal' | 'fails' | 'pending';
    error?: string;
  };
}

export function YScramblingCard({ yScramble }: YScramblingCardProps) {
  if (!yScramble) return null;

  if (yScramble.error) {
    return (
      <div className="plot-container-card" style={{ marginBottom: '16px' }}>
        <div className="plot-title">Y-Scrambling Sanity Check</div>
        <div style={{ fontSize: '10px', color: 'var(--color-red-700)', marginTop: '6px' }}>
          ⚠ Y-Scrambling failed: {yScramble.error}
        </div>
      </div>
    );
  }

  const verdictColor = {
    robust: 'var(--color-brand-700)',
    marginal: 'var(--color-amber-700)',
    fails: 'var(--color-red-700)',
    pending: 'var(--color-text-400)',
  }[yScramble.verdict];

  const verdictBg = {
    robust: 'var(--color-brand-100)',
    marginal: 'var(--color-amber-100)',
    fails: 'var(--color-red-100)',
    pending: 'var(--color-border-subtle)',
  }[yScramble.verdict];

  const verdictBorder = {
    robust: 'var(--color-brand-300)',
    marginal: 'var(--color-amber-300)',
    fails: 'var(--color-red-300)',
    pending: 'var(--color-border)',
  }[yScramble.verdict];

  const verdictText = {
    robust: '✓ Model robust — true performance significantly exceeds chance',
    marginal: '⚠ Marginal — true score only modestly exceeds scrambled baseline',
    fails: '✗ Fails sanity check — model may be fitting noise',
    pending: '— Result pending',
  }[yScramble.verdict];

  const metricLabel = yScramble.primary_metric === 'r2_val' ? 'R²' : 'Accuracy';
  const isPercent = yScramble.primary_metric === 'accuracy_val';
  const fmt = (v: number) => isPercent ? `${(v * 100).toFixed(1)}%` : v.toFixed(3);

  return (
    <div className="plot-container-card" style={{ marginBottom: '16px' }}>
      <div className="plot-title">
        Y-Scrambling Sanity Check ({yScramble.n_iterations} permutations)
      </div>

      {/* Two big numbers side by side */}
      <div className="scramble-comparison">
        <div className="scramble-stat real">
          <div className="scramble-val">{fmt(yScramble.true_score)}</div>
          <div className="scramble-label">True Model {metricLabel}</div>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', color: 'var(--color-text-400)',
          fontSize: '16px', padding: '0 8px',
        }}>
          vs
        </div>
        <div className="scramble-stat scrambled">
          <div className="scramble-val">
            {fmt(yScramble.scrambled_mean)}
            <span style={{ fontSize: '11px', fontWeight: 400, color: 'var(--color-text-400)' }}>
              {' '}±{fmt(yScramble.scrambled_std)}
            </span>
          </div>
          <div className="scramble-label">Scrambled Baseline</div>
        </div>
      </div>

      {/* Additional stats row */}
      <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
        <div style={{
          flex: '1 1 80px', textAlign: 'center',
          background: 'var(--color-bg)', border: '0.5px solid var(--color-border)',
          borderRadius: '6px', padding: '5px 8px',
        }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-200)' }}>
            {yScramble.z_score.toFixed(2)}σ
          </div>
          <div style={{ fontSize: '9px', color: 'var(--color-text-400)', textTransform: 'uppercase' }}>Z-score</div>
        </div>
        <div style={{
          flex: '1 1 80px', textAlign: 'center',
          background: 'var(--color-bg)', border: '0.5px solid var(--color-border)',
          borderRadius: '6px', padding: '5px 8px',
        }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-200)' }}>
            {yScramble.p_value < 0.001 ? '<0.001' : yScramble.p_value.toFixed(3)}
          </div>
          <div style={{ fontSize: '9px', color: 'var(--color-text-400)', textTransform: 'uppercase' }}>p-value</div>
        </div>
        <div style={{
          flex: '1 1 80px', textAlign: 'center',
          background: 'var(--color-bg)', border: '0.5px solid var(--color-border)',
          borderRadius: '6px', padding: '5px 8px',
        }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-200)' }}>
            {fmt(yScramble.true_score - yScramble.scrambled_mean)}
          </div>
          <div style={{ fontSize: '9px', color: 'var(--color-text-400)', textTransform: 'uppercase' }}>Δ Gain</div>
        </div>
      </div>

      {/* Histogram */}
      <ScrambleHistogram
        scores={yScramble.scrambled_scores}
        trueScore={yScramble.true_score}
      />

      {/* Verdict badge */}
      <div style={{
        marginTop: '8px', padding: '7px 10px', borderRadius: '6px',
        background: verdictBg,
        border: `0.5px solid ${verdictBorder}`,
        color: verdictColor,
        fontSize: '10px', fontWeight: 600,
      }}>
        {verdictText}
      </div>
    </div>
  );
}
