import { useState, useMemo } from 'react';
import { Tab } from '@headlessui/react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  ComposedChart,
  BarChart,
  Bar,
  Line,
  LineChart,
  ErrorBar,
  Area,
  Legend
} from 'recharts';

interface DiagnosticsPanelProps {
  diagnostics: any;
  modelType: 'regression' | 'classification';
  onSelectCompound?: (index: number) => void;
  highlightedPoints?: number[];
}

export default function DiagnosticsPanel({ diagnostics, modelType, onSelectCompound, highlightedPoints }: DiagnosticsPanelProps) {
  const [threshold, setThreshold] = useState(0.5);

  if (!diagnostics || Object.keys(diagnostics).length === 0) {
    return (
      <div className="p-8 text-center border border-dashed rounded-xl border-[var(--color-border)] bg-[var(--color-surface)]">
        <p className="text-[var(--color-text-400)] text-sm">
          No diagnostics data available for this model version. Diagnostics are compiled during model training.
        </p>
      </div>
    );
  }

  // --- Regression Renderers ---
  if (modelType === 'regression') {
    const {
      parity = { points: [], min: 0, max: 1 },
      residuals_vs_fitted = [],
      residual_histogram = [],
      qq = [],
      learning_curve = [],
      y_scramble = null
    } = diagnostics;

    // 1. AD Counts & Legend for Parity
    const adStats = useMemo(() => {
      const pts = parity.points || [];
      const total = pts.length;
      const inAD = pts.filter((p: any) => p.ad === 'in' || p.ad === 'in_ad').length;
      const borderline = pts.filter((p: any) => p.ad === 'borderline').length;
      const outAD = pts.filter((p: any) => p.ad === 'out' || p.ad === 'out_ad').length;
      return { total, inAD, borderline, outAD };
    }, [parity.points]);

    // 2. Y-Scrambling Histogram Binning
    const scrambleBins = useMemo(() => {
      if (!y_scramble || !y_scramble.distribution || y_scramble.distribution.length === 0) return [];
      const scores = y_scramble.distribution;
      const trueScore = y_scramble.real_score;
      const nBins = 10;
      const minScore = Math.min(...scores, trueScore - 0.1);
      const maxScore = Math.max(...scores, trueScore + 0.1);
      const range = maxScore - minScore || 0.1;
      const binWidth = range / nBins;

      const bins = Array.from({ length: nBins }, (_, i) => ({
        start: minScore + i * binWidth,
        end: minScore + (i + 1) * binWidth,
        center: minScore + (i + 0.5) * binWidth,
        label: (minScore + (i + 0.5) * binWidth).toFixed(2),
        count: 0
      }));

      scores.forEach((s: number) => {
        const idx = Math.min(nBins - 1, Math.floor((s - minScore) / binWidth));
        if (idx >= 0 && bins[idx]) bins[idx].count++;
      });

      return bins;
    }, [y_scramble]);

    return (
      <div className="space-y-6">
        {/* Legend row */}
        <div className="flex flex-wrap items-center gap-4 px-4 py-2 text-xs border rounded-lg bg-[var(--color-bg)] border-[var(--color-border)]">
          <span className="font-semibold text-[var(--color-text-200)]">Applicability Domain (n={adStats.total}):</span>
          <span className="flex items-center gap-1.5 font-medium text-[var(--color-success-700)]">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--color-success-500)]"></span> In-AD (n={adStats.inAD})
          </span>
          <span className="flex items-center gap-1.5 font-medium text-[var(--color-amber-700)]">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--color-amber-500)]"></span> Borderline (n={adStats.borderline})
          </span>
          <span className="flex items-center gap-1.5 font-medium text-[var(--color-red-700)]">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--color-red-500)]"></span> Out-of-AD (n={adStats.outAD})
          </span>
        </div>

        <Tab.Group>
          <Tab.List className="flex p-1 space-x-1 border rounded-xl bg-[var(--color-bg)] border-[var(--color-border)]">
            {['Parity', 'Residuals vs Fitted', 'Residual Histogram', 'Q-Q', 'Learning Curve', 'Y-Scrambling'].map((tabName) => (
              <Tab
                key={tabName}
                className={({ selected }) =>
                  `w-full py-2.5 text-xs font-semibold rounded-lg transition-all focus:outline-none ${
                    selected
                      ? 'bg-[var(--color-surface)] text-[var(--color-brand-700)] shadow-sm'
                      : 'text-[var(--color-text-400)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-200)]'
                  }`
                }
              >
                {tabName}
              </Tab>
            ))}
          </Tab.List>

          <Tab.Panels className="mt-4">
            {/* Parity Plot */}
            <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
              <div className="mb-2">
                <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Predicted vs Observed</h4>
                <p className="text-xs text-[var(--color-text-400)]">Color coded by AD status. Click points to inspect globally.</p>
              </div>
              <div style={{ width: '100%', height: 350 }}>
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis
                      type="number"
                      dataKey="y_true"
                      name="True Value"
                      domain={['auto', 'auto']}
                      tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                      label={{ value: 'True Value', position: 'bottom', offset: 0, fontSize: 11, fill: 'var(--color-text-300)' }}
                    />
                    <YAxis
                      type="number"
                      dataKey="y_pred"
                      name="Predicted"
                      domain={['auto', 'auto']}
                      tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                      label={{ value: 'Predicted Value', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11, fill: 'var(--color-text-300)' }}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="p-3 border rounded-lg bg-[var(--color-surface)] border-[var(--color-border)] shadow-xl text-xs space-y-1">
                              <p className="font-semibold text-[var(--color-text-100)]">Compound Inspection</p>
                              <p className="text-[var(--color-text-300)]">True: <span className="font-medium">{data.y_true.toFixed(3)}</span></p>
                              <p className="text-[var(--color-text-300)]">Pred: <span className="font-medium">{data.y_pred.toFixed(3)}</span></p>
                              <p className="text-[var(--color-text-300)]">AD Status: <span className="font-semibold capitalize">{data.ad}</span></p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <ReferenceLine
                      segment={[
                        { x: parity.min, y: parity.min },
                        { x: parity.max, y: parity.max }
                      ]}
                      stroke="var(--color-text-300)"
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                    />
                    <Scatter
                      data={parity.points}
                      onClick={(_, index) => {
                        if (onSelectCompound) {
                          onSelectCompound(index);
                        }
                      }}
                    >
                      {parity.points.map((entry: any, index: number) => {
                        const status = entry.ad || '';
                        const fill =
                          status === 'in' || status === 'in_ad'
                            ? 'var(--color-success-500)'
                            : status === 'borderline'
                            ? 'var(--color-amber-500)'
                            : 'var(--color-red-500)';
                        const isHighlighted = highlightedPoints?.includes(index);
                        const radius = isHighlighted ? 8 : 5;
                        const stroke = isHighlighted ? '#ef4444' : 'var(--color-surface)';
                        const strokeWidth = isHighlighted ? 3 : 1;
                        return (
                          <circle
                            key={`cell-${index}`}
                            cx={0}
                            cy={0}
                            r={radius}
                            fill={fill}
                            className={`cursor-pointer transition-all duration-300 hover:scale-150 ${isHighlighted ? 'animate-pulse' : ''}`}
                            stroke={stroke}
                            strokeWidth={strokeWidth}
                            style={isHighlighted ? { filter: 'drop-shadow(0 0 4px #ef4444)' } : undefined}
                          />
                        );
                      })}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </Tab.Panel>

            {/* Residuals vs Fitted */}
            <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
              <div className="mb-2">
                <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Residuals vs Fitted Values</h4>
                <p className="text-xs text-[var(--color-text-400)]">Residuals should ideally distribute randomly around the horizontal zero line.</p>
              </div>
              <div style={{ width: '100%', height: 350 }}>
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis
                      type="number"
                      dataKey="y_pred"
                      name="Fitted (y_pred)"
                      domain={['auto', 'auto']}
                      tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                      label={{ value: 'Fitted (y_pred)', position: 'bottom', offset: 0, fontSize: 11, fill: 'var(--color-text-300)' }}
                    />
                    <YAxis
                      type="number"
                      dataKey="residual"
                      name="Residual (y_true - y_pred)"
                      tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                      label={{ value: 'Residual', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: 'var(--color-text-300)' }}
                    />
                    <Tooltip
                      cursor={{ strokeDasharray: '3 3' }}
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="p-3 border rounded-lg bg-[var(--color-surface)] border-[var(--color-border)] shadow-xl text-xs">
                              <p className="text-[var(--color-text-300)]">Fitted: <span className="font-medium">{data.y_pred.toFixed(3)}</span></p>
                              <p className="text-[var(--color-text-300)]">Residual: <span className="font-medium">{data.residual.toFixed(3)}</span></p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <ReferenceLine y={0} stroke="var(--color-red-500)" strokeWidth={1.5} strokeDasharray="3 3" />
                    <Scatter data={residuals_vs_fitted} fill="var(--color-brand-500)" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </Tab.Panel>

            {/* Residual Histogram */}
            <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
              <div className="mb-2">
                <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Residual Distribution with Normal Fit</h4>
                <p className="text-xs text-[var(--color-text-400)]">Overlaying fitted normal curve to evaluate skewness and regression normality assumptions.</p>
              </div>
              <div style={{ width: '100%', height: 350 }}>
                <ResponsiveContainer>
                  <ComposedChart data={residual_histogram} margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis
                      dataKey="bin_center"
                      tickFormatter={(val) => Number(val).toFixed(2)}
                      tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                      label={{ value: 'Residual Interval Center', position: 'bottom', offset: 0, fontSize: 11, fill: 'var(--color-text-300)' }}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                      label={{ value: 'Density / Count', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: 'var(--color-text-300)' }}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="p-3 border rounded-lg bg-[var(--color-surface)] border-[var(--color-border)] shadow-xl text-xs space-y-1">
                              <p className="text-[var(--color-text-300)]">Bin Center: <span className="font-medium">{data.bin_center.toFixed(3)}</span></p>
                              <p className="text-[var(--color-text-300)]">Frequency: <span className="font-semibold text-[var(--color-brand-600)]">{data.count}</span></p>
                              <p className="text-[var(--color-text-300)]">Normal Height: <span className="font-medium">{data.normal_fit.toFixed(1)}</span></p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Bar dataKey="count" fill="var(--color-brand-400)" opacity={0.65} name="Residual Frequency" />
                    <Line type="monotone" dataKey="normal_fit" stroke="var(--color-brand-600)" strokeWidth={2} dot={false} name="Normal Distribution Fit" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </Tab.Panel>

            {/* Q-Q Plot */}
            <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
              <div className="mb-2">
                <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Quantile-Quantile (Q-Q) Plot</h4>
                <p className="text-xs text-[var(--color-text-400)]">Plots sample ordered residuals against theoretical standard normal distribution quantiles.</p>
              </div>
              <div style={{ width: '100%', height: 350 }}>
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis
                      type="number"
                      dataKey="theoretical"
                      name="Theoretical Quantiles"
                      tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                      label={{ value: 'Theoretical Standard Quantiles', position: 'bottom', offset: 0, fontSize: 11, fill: 'var(--color-text-300)' }}
                    />
                    <YAxis
                      type="number"
                      dataKey="sample"
                      name="Ordered Sample Quantiles"
                      tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                      label={{ value: 'Ordered Sample Quantiles', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: 'var(--color-text-300)' }}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="p-3 border rounded-lg bg-[var(--color-surface)] border-[var(--color-border)] shadow-xl text-xs">
                              <p className="text-[var(--color-text-300)]">Theoretical: <span className="font-medium">{data.theoretical.toFixed(3)}</span></p>
                              <p className="text-[var(--color-text-300)]">Sample: <span className="font-medium">{data.sample.toFixed(3)}</span></p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    {qq.length > 0 && (
                      <ReferenceLine
                        segment={[
                          { x: Math.min(...qq.map((q: any) => q.theoretical)), y: Math.min(...qq.map((q: any) => q.theoretical)) },
                          { x: Math.max(...qq.map((q: any) => q.theoretical)), y: Math.max(...qq.map((q: any) => q.theoretical)) }
                        ]}
                        stroke="var(--color-border)"
                        strokeDasharray="4 4"
                      />
                    )}
                    <Scatter data={qq} fill="var(--color-brand-600)" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </Tab.Panel>

            {/* Learning Curve */}
            <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
              <div className="mb-2">
                <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Training & Validation Learning Curve</h4>
                <p className="text-xs text-[var(--color-text-400)]">Scores mean and standard deviation across increasing training sample splits.</p>
              </div>
              <div style={{ width: '100%', height: 350 }}>
                <ResponsiveContainer>
                  <LineChart data={learning_curve} margin={{ top: 20, right: 30, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis
                      dataKey="train_size"
                      tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                      label={{ value: 'Number of Training Samples', position: 'bottom', offset: 0, fontSize: 11, fill: 'var(--color-text-300)' }}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                      label={{ value: 'Performance Score (R²)', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: 'var(--color-text-300)' }}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="p-3 border rounded-lg bg-[var(--color-surface)] border-[var(--color-border)] shadow-xl text-xs space-y-1">
                              <p className="font-semibold text-[var(--color-text-100)]">Samples: {data.train_size}</p>
                              <p className="text-[var(--color-success-700)]">Train R²: <span className="font-medium">{data.train_mean.toFixed(3)} ± {data.train_std.toFixed(3)}</span></p>
                              <p className="text-[var(--color-brand-700)]">Val R²: <span className="font-medium">{data.val_mean.toFixed(3)} ± {data.val_std.toFixed(3)}</span></p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Legend verticalAlign="top" height={36} />
                    <Line dataKey="train_mean" stroke="var(--color-success-500)" strokeWidth={2} dot={{ r: 4.5 }} name="Training Score">
                      <ErrorBar dataKey="train_std" width={4} strokeWidth={1.5} stroke="var(--color-success-400)" direction="y" />
                    </Line>
                    <Line dataKey="val_mean" stroke="var(--color-brand-600)" strokeWidth={2} dot={{ r: 4.5 }} name="Cross-Validation Score">
                      <ErrorBar dataKey="val_std" width={4} strokeWidth={1.5} stroke="var(--color-brand-400)" direction="y" />
                    </Line>
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Tab.Panel>

            {/* Y-Scrambling */}
            <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
              <div className="mb-2">
                <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Y-Scrambling Permutation Null Hypothesis</h4>
                <p className="text-xs text-[var(--color-text-400)]">Calculated Z-score & empirical p-value relative to scrambled targets distribution.</p>
              </div>
              {y_scramble ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-3 border rounded-xl bg-[var(--color-bg)] border-[var(--color-border)] text-center">
                      <p className="text-xs text-[var(--color-text-400)] uppercase font-semibold">True Score</p>
                      <p className="text-lg font-bold text-[var(--color-text-100)]">{y_scramble.real_score.toFixed(3)}</p>
                    </div>
                    <div className="p-3 border rounded-xl bg-[var(--color-bg)] border-[var(--color-border)] text-center">
                      <p className="text-xs text-[var(--color-text-400)] uppercase font-semibold">Mean Permuted</p>
                      <p className="text-lg font-bold text-[var(--color-text-100)]">
                        {y_scramble.distribution && y_scramble.distribution.length
                          ? (y_scramble.distribution.reduce((a: number, b: number) => a + b, 0) / y_scramble.distribution.length).toFixed(3)
                          : '0.000'}
                      </p>
                    </div>
                    <div className="p-3 border rounded-xl bg-[var(--color-bg)] border-[var(--color-border)] text-center">
                      <p className="text-xs text-[var(--color-text-400)] uppercase font-semibold">Empirical p-value</p>
                      <p className="text-lg font-bold text-[var(--color-brand-600)]">p = {y_scramble.p_value.toFixed(4)}</p>
                    </div>
                  </div>
                  <div style={{ width: '100%', height: 260 }}>
                    <ResponsiveContainer>
                      <BarChart data={scrambleBins} margin={{ top: 20, right: 35, bottom: 20, left: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                        <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--color-text-400)' }} />
                        <YAxis tick={{ fontSize: 11, fill: 'var(--color-text-400)' }} allowDecimals={false} />
                        <Tooltip />
                        <Bar dataKey="count" fill="var(--color-text-400)" opacity={0.6} name="Permuted Frequency" />
                        <ReferenceLine
                          x={y_scramble.real_score.toFixed(2)}
                          stroke="var(--color-brand-600)"
                          strokeWidth={2.5}
                          label={{ value: `Real Model Score (p = ${y_scramble.p_value.toFixed(3)})`, position: 'insideTopRight', fill: 'var(--color-brand-700)', fontSize: 11, fontWeight: 'bold' }}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-center text-[var(--color-text-400)] py-8">Y-Scrambling distribution is not computed or available for this run.</p>
              )}
            </Tab.Panel>
          </Tab.Panels>
        </Tab.Group>
      </div>
    );
  }

  // --- Classification Renderers ---
  const {
    confusion_matrix = { tp: 0, fp: 0, fn: 0, tn: 0, total: 0 },
    roc = { points: [], auc: 0 },
    pr = { points: [], auc: 0 },
    calibration = [],
    threshold_sweep = [],
    probability_histogram = { positive: [], negative: [] },
    learning_curve = []
  } = diagnostics;

  // 1. Shaded Confusion Matrix
  const totalCM = Math.max(1, confusion_matrix.tp + confusion_matrix.fp + confusion_matrix.fn + confusion_matrix.tn);

  // 2. Aligned Histograms
  const histDataset = (() => {
    const pos = probability_histogram.positive || [];
    const neg = probability_histogram.negative || [];
    return pos.map((pBin: any, idx: number) => {
      const nBin = neg[idx] || { count: 0 };
      return {
        bin_center: pBin.bin_center,
        positive: pBin.count,
        negative: nBin.count
      };
    });
  })();

  // 3. Threshold Sweep Processing
  const closestSweepIndex = (() => {
    if (threshold_sweep.length === 0) return 0;
    let bestIdx = 0;
    let minDiff = 999;
    threshold_sweep.forEach((pt: any, idx: number) => {
      const diff = Math.abs(pt.threshold - threshold);
      if (diff < minDiff) {
        minDiff = diff;
        bestIdx = idx;
      }
    });
    return bestIdx;
  })();

  const selectedSweep = threshold_sweep[closestSweepIndex] || {
    precision: 0,
    recall: 0,
    f1: 0,
    accuracy: 0,
    tp: 0,
    fp: 0,
    fn: 0,
    tn: 0,
    threshold: 0.5
  };

  return (
    <div className="space-y-6">
      <Tab.Group>
        <Tab.List className="flex p-1 space-x-1 border rounded-xl bg-[var(--color-bg)] border-[var(--color-border)]">
          {['Confusion Matrix', 'ROC', 'PR', 'Calibration', 'Threshold Sweep', 'Probability Histogram', 'Learning Curve'].map((tabName) => (
            <Tab
              key={tabName}
              className={({ selected }) =>
                `w-full py-2.5 text-xs font-semibold rounded-lg transition-all focus:outline-none ${
                  selected
                    ? 'bg-[var(--color-surface)] text-[var(--color-brand-700)] shadow-sm'
                    : 'text-[var(--color-text-400)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-200)]'
                }`
              }
            >
              {tabName}
            </Tab>
          ))}
        </Tab.List>

        <Tab.Panels className="mt-4">
          {/* Confusion Matrix */}
          <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Cross-Validated Confusion Matrix</h4>
              <p className="text-xs text-[var(--color-text-400)]">Validates predictions using actual validation ground truth classes.</p>
            </div>
            <div className="flex justify-center py-6">
              <div className="grid grid-cols-[120px_160px_160px] grid-rows-[40px_120px_120px] gap-2 items-center text-center">
                {/* Labels & Headers */}
                <div className="text-xs font-semibold text-[var(--color-text-300)]">True \ Pred</div>
                <div className="text-xs font-bold text-[var(--color-text-200)] bg-[var(--color-bg)] py-2 border rounded-lg">Negative (0)</div>
                <div className="text-xs font-bold text-[var(--color-text-200)] bg-[var(--color-bg)] py-2 border rounded-lg">Positive (1)</div>

                <div className="text-xs font-bold text-[var(--color-text-200)] bg-[var(--color-bg)] py-10 border rounded-lg h-full flex items-center justify-center">Actual (0)</div>
                {/* TN */}
                <div
                  className="rounded-xl flex flex-col items-center justify-center p-6 border h-full transition-all"
                  style={{
                    background: `rgba(var(--color-brand-500-rgb, 14, 116, 144), ${Math.min(0.8, 0.1 + (confusion_matrix.tn / totalCM) * 0.7)})`,
                    borderColor: 'var(--color-border)',
                    color: confusion_matrix.tn / totalCM > 0.4 ? '#ffffff' : 'var(--color-text-100)'
                  }}
                >
                  <span className="text-3xl font-extrabold">{confusion_matrix.tn}</span>
                  <span className="text-[10px] uppercase font-semibold opacity-75 mt-1">True Negative</span>
                </div>
                {/* FP */}
                <div
                  className="rounded-xl flex flex-col items-center justify-center p-6 border h-full transition-all"
                  style={{
                    background: `rgba(239, 68, 68, ${Math.min(0.8, 0.1 + (confusion_matrix.fp / totalCM) * 0.7)})`,
                    borderColor: 'var(--color-border)',
                    color: confusion_matrix.fp / totalCM > 0.4 ? '#ffffff' : 'var(--color-text-100)'
                  }}
                >
                  <span className="text-3xl font-extrabold">{confusion_matrix.fp}</span>
                  <span className="text-[10px] uppercase font-semibold opacity-75 mt-1">False Positive</span>
                </div>

                <div className="text-xs font-bold text-[var(--color-text-200)] bg-[var(--color-bg)] py-10 border rounded-lg h-full flex items-center justify-center">Actual (1)</div>
                {/* FN */}
                <div
                  className="rounded-xl flex flex-col items-center justify-center p-6 border h-full transition-all"
                  style={{
                    background: `rgba(239, 68, 68, ${Math.min(0.8, 0.1 + (confusion_matrix.fn / totalCM) * 0.7)})`,
                    borderColor: 'var(--color-border)',
                    color: confusion_matrix.fn / totalCM > 0.4 ? '#ffffff' : 'var(--color-text-100)'
                  }}
                >
                  <span className="text-3xl font-extrabold">{confusion_matrix.fn}</span>
                  <span className="text-[10px] uppercase font-semibold opacity-75 mt-1">False Negative</span>
                </div>
                {/* TP */}
                <div
                  className="rounded-xl flex flex-col items-center justify-center p-6 border h-full transition-all"
                  style={{
                    background: `rgba(var(--color-brand-500-rgb, 14, 116, 144), ${Math.min(0.8, 0.1 + (confusion_matrix.tp / totalCM) * 0.7)})`,
                    borderColor: 'var(--color-border)',
                    color: confusion_matrix.tp / totalCM > 0.4 ? '#ffffff' : 'var(--color-text-100)'
                  }}
                >
                  <span className="text-3xl font-extrabold">{confusion_matrix.tp}</span>
                  <span className="text-[10px] uppercase font-semibold opacity-75 mt-1">True Positive</span>
                </div>
              </div>
            </div>
          </Tab.Panel>

          {/* ROC Curve */}
          <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
            <div className="mb-2">
              <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Receiver Operating Characteristic (ROC) Curve</h4>
              <p className="text-xs text-[var(--color-text-400)]">Average ROC Curve with ±1 Standard Deviation CV shaded confidence band.</p>
            </div>
            <div style={{ width: '100%', height: 350 }}>
              <ResponsiveContainer>
                <ComposedChart data={roc.points} margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis
                    type="number"
                    dataKey="fpr"
                    domain={[0, 1]}
                    tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                    label={{ value: 'False Positive Rate (FPR)', position: 'bottom', offset: 0, fontSize: 11, fill: 'var(--color-text-300)' }}
                  />
                  <YAxis
                    type="number"
                    domain={[0, 1]}
                    tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                    label={{ value: 'True Positive Rate (TPR)', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: 'var(--color-text-300)' }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="p-3 border rounded-lg bg-[var(--color-surface)] border-[var(--color-border)] shadow-xl text-xs space-y-1">
                            <p className="text-[var(--color-text-300)]">FPR: <span className="font-medium">{data.fpr.toFixed(3)}</span></p>
                            <p className="text-[var(--color-text-300)]">TPR: <span className="font-semibold text-[var(--color-brand-600)]">{data.tpr.toFixed(3)}</span></p>
                            <p className="text-[var(--color-text-400)]">CI Range: [{data.tpr_min.toFixed(2)}, {data.tpr_max.toFixed(2)}]</p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="tpr_max"
                    stroke="none"
                    fill="var(--color-brand-400)"
                    opacity={0.18}
                    baseValue={"tpr_min" as any}
                    name="±1 SD Interval"
                  />
                  <Line type="monotone" dataKey="tpr" stroke="var(--color-brand-600)" strokeWidth={2} dot={false} name="Mean CV Curve" />
                  <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--color-border)" strokeDasharray="3 3" />
                  <Legend verticalAlign="top" height={36} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 text-center text-xs font-semibold text-[var(--color-text-300)]">
              Mean Cross-Validation AUC-ROC = <span className="text-[var(--color-brand-600)]">{roc.auc.toFixed(4)}</span>
            </div>
          </Tab.Panel>

          {/* PR Curve */}
          <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
            <div className="mb-2">
              <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Precision-Recall (PR) Curve</h4>
              <p className="text-xs text-[var(--color-text-400)]">Mean Precision-Recall curve with ±1 SD CV shaded confidence band.</p>
            </div>
            <div style={{ width: '100%', height: 350 }}>
              <ResponsiveContainer>
                <ComposedChart data={pr.points} margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis
                    type="number"
                    dataKey="recall"
                    domain={[0, 1]}
                    tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                    label={{ value: 'Recall', position: 'bottom', offset: 0, fontSize: 11, fill: 'var(--color-text-300)' }}
                  />
                  <YAxis
                    type="number"
                    domain={[0, 1]}
                    tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                    label={{ value: 'Precision', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: 'var(--color-text-300)' }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="p-3 border rounded-lg bg-[var(--color-surface)] border-[var(--color-border)] shadow-xl text-xs space-y-1">
                            <p className="text-[var(--color-text-300)]">Recall: <span className="font-medium">{data.recall.toFixed(3)}</span></p>
                            <p className="text-[var(--color-text-300)]">Precision: <span className="font-semibold text-[var(--color-brand-600)]">{data.precision.toFixed(3)}</span></p>
                            <p className="text-[var(--color-text-400)]">CI Range: [{data.precision_min.toFixed(2)}, {data.precision_max.toFixed(2)}]</p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="precision_max"
                    stroke="none"
                    fill="var(--color-brand-400)"
                    opacity={0.18}
                    baseValue={"precision_min" as any}
                    name="±1 SD Interval"
                  />
                  <Line type="monotone" dataKey="precision" stroke="var(--color-brand-600)" strokeWidth={2} dot={false} name="Mean CV Curve" />
                  <Legend verticalAlign="top" height={36} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 text-center text-xs font-semibold text-[var(--color-text-300)]">
              Mean PR Area Under Curve = <span className="text-[var(--color-brand-600)]">{pr.auc.toFixed(4)}</span>
            </div>
          </Tab.Panel>

          {/* Calibration Curve */}
          <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
            <div className="mb-2">
              <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Probability Calibration Reliability Curve</h4>
              <p className="text-xs text-[var(--color-text-400)]">Compares predicted probability bins vs actual observed validation label fraction.</p>
            </div>
            <div style={{ width: '100%', height: 350 }}>
              <ResponsiveContainer>
                <LineChart data={calibration} margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis
                    dataKey="pred"
                    type="number"
                    domain={[0, 1]}
                    tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                    label={{ value: 'Mean Predicted Probability', position: 'bottom', offset: 0, fontSize: 11, fill: 'var(--color-text-300)' }}
                  />
                  <YAxis
                    type="number"
                    domain={[0, 1]}
                    tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                    label={{ value: 'Observed Fraction of Positives', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: 'var(--color-text-300)' }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="p-3 border rounded-lg bg-[var(--color-surface)] border-[var(--color-border)] shadow-xl text-xs">
                            <p className="text-[var(--color-text-300)]">Mean Predicted: <span className="font-medium">{data.pred.toFixed(3)}</span></p>
                            <p className="text-[var(--color-text-300)]">Observed Fraction: <span className="font-semibold text-[var(--color-brand-600)]">{data.true.toFixed(3)}</span></p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Line type="monotone" dataKey="true" stroke="var(--color-brand-600)" strokeWidth={2.5} dot={{ r: 4.5 }} name="Model Calibration" />
                  <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--color-text-300)" strokeDasharray="4 4" name="Perfect Calibration" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Tab.Panel>

          {/* Threshold Sweep */}
          <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Interactive Probability Threshold Sweep</h4>
              <p className="text-xs text-[var(--color-text-400)]">Drag threshold slider to evaluate classification metrics and live confusion matrix instantly.</p>
            </div>
            
            {/* Interactive Threshold Slider */}
            <div className="flex items-center gap-6 px-4 py-3.5 border rounded-xl bg-[var(--color-bg)] border-[var(--color-border)] mb-6">
              <span className="text-xs font-semibold text-[var(--color-text-200)] min-w-[120px]">
                Threshold: <span className="text-[var(--color-brand-600)] font-extrabold text-sm">{threshold.toFixed(2)}</span>
              </span>
              <input
                type="range"
                min="0.01"
                max="0.99"
                step="0.02"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="flex-1 accent-[var(--color-brand-600)]"
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Sweep Line Charts */}
              <div className="space-y-4">
                <h5 className="text-xs font-bold uppercase tracking-wider text-[var(--color-text-300)]">Metric Sweeps vs Threshold</h5>
                <div style={{ width: '100%', height: 260 }}>
                  <ResponsiveContainer>
                    <LineChart data={threshold_sweep} margin={{ top: 10, right: 10, bottom: 10, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis dataKey="threshold" tickFormatter={(v) => Number(v).toFixed(2)} tick={{ fontSize: 10, fill: 'var(--color-text-400)' }} />
                      <YAxis domain={[0, 1]} tick={{ fontSize: 10, fill: 'var(--color-text-400)' }} />
                      <Tooltip />
                      <Legend verticalAlign="top" height={32} wrapperStyle={{ fontSize: 10 }} />
                      <Line type="monotone" dataKey="precision" stroke="var(--color-brand-600)" strokeWidth={1.5} dot={false} name="P" />
                      <Line type="monotone" dataKey="recall" stroke="var(--color-success-500)" strokeWidth={1.5} dot={false} name="R" />
                      <Line type="monotone" dataKey="f1" stroke="var(--color-amber-500)" strokeWidth={1.5} dot={false} name="F1" />
                      <Line type="monotone" dataKey="accuracy" stroke="var(--color-red-500)" strokeWidth={1.5} dot={false} name="Acc" />
                      <ReferenceLine x={selectedSweep.threshold} stroke="var(--color-text-400)" strokeDasharray="3 3" strokeWidth={1.5} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Dynamic Confusion Matrix */}
              <div className="space-y-4">
                <h5 className="text-xs font-bold uppercase tracking-wider text-[var(--color-text-300)]">Live Matrix at t = {selectedSweep.threshold.toFixed(2)}</h5>
                <div className="grid grid-cols-[100px_1fr_1fr] grid-rows-[32px_90px_90px] gap-1 text-center text-xs">
                  <div className="text-[10px] font-semibold text-[var(--color-text-400)] self-center">True \ Pred</div>
                  <div className="font-bold text-[var(--color-text-200)] bg-[var(--color-bg)] py-1.5 border rounded-md">Neg (0)</div>
                  <div className="font-bold text-[var(--color-text-200)] bg-[var(--color-bg)] py-1.5 border rounded-md">Pos (1)</div>

                  <div className="font-bold text-[var(--color-text-200)] bg-[var(--color-bg)] border rounded-md flex items-center justify-center">Actual (0)</div>
                  <div className="rounded-lg flex flex-col justify-center items-center p-3 border bg-[var(--color-surface)] border-[var(--color-border)]">
                    <span className="text-xl font-bold text-[var(--color-success-600)]">{selectedSweep.tn}</span>
                    <span className="text-[9px] opacity-75">True Neg</span>
                  </div>
                  <div className="rounded-lg flex flex-col justify-center items-center p-3 border bg-[var(--color-surface)] border-[var(--color-border)]">
                    <span className="text-xl font-bold text-[var(--color-red-500)]">{selectedSweep.fp}</span>
                    <span className="text-[9px] opacity-75">False Pos</span>
                  </div>

                  <div className="font-bold text-[var(--color-text-200)] bg-[var(--color-bg)] border rounded-md flex items-center justify-center">Actual (1)</div>
                  <div className="rounded-lg flex flex-col justify-center items-center p-3 border bg-[var(--color-surface)] border-[var(--color-border)]">
                    <span className="text-xl font-bold text-[var(--color-red-500)]">{selectedSweep.fn}</span>
                    <span className="text-[9px] opacity-75">False Neg</span>
                  </div>
                  <div className="rounded-lg flex flex-col justify-center items-center p-3 border bg-[var(--color-surface)] border-[var(--color-border)]">
                    <span className="text-xl font-bold text-[var(--color-success-600)]">{selectedSweep.tp}</span>
                    <span className="text-[9px] opacity-75">True Pos</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="px-3 py-1.5 border rounded-lg bg-[var(--color-bg)] border-[var(--color-border)] flex justify-between">
                    <span className="text-[var(--color-text-400)]">Precision</span>
                    <span className="font-bold text-[var(--color-text-100)]">{(selectedSweep.precision * 100).toFixed(1)}%</span>
                  </div>
                  <div className="px-3 py-1.5 border rounded-lg bg-[var(--color-bg)] border-[var(--color-border)] flex justify-between">
                    <span className="text-[var(--color-text-400)]">Recall (Sens)</span>
                    <span className="font-bold text-[var(--color-text-100)]">{(selectedSweep.recall * 100).toFixed(1)}%</span>
                  </div>
                  <div className="px-3 py-1.5 border rounded-lg bg-[var(--color-bg)] border-[var(--color-border)] flex justify-between">
                    <span className="text-[var(--color-text-400)]">F1-Score</span>
                    <span className="font-bold text-[var(--color-text-100)]">{(selectedSweep.f1 * 100).toFixed(1)}%</span>
                  </div>
                  <div className="px-3 py-1.5 border rounded-lg bg-[var(--color-bg)] border-[var(--color-border)] flex justify-between">
                    <span className="text-[var(--color-text-400)]">Accuracy</span>
                    <span className="font-bold text-[var(--color-text-100)]">{(selectedSweep.accuracy * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            </div>
          </Tab.Panel>

          {/* Probability Histogram */}
          <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
            <div className="mb-2">
              <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Validation Predicted Probabilities Distribution</h4>
              <p className="text-xs text-[var(--color-text-400)]">Semi-transparent overlaid distribution for true toxic (positives) and safe (negatives) compounds.</p>
            </div>
            <div style={{ width: '100%', height: 350 }}>
              <ResponsiveContainer>
                <BarChart data={histDataset} margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis
                    dataKey="bin_center"
                    tickFormatter={(val) => Number(val).toFixed(2)}
                    tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                    label={{ value: 'Mean Predicted Class Probability', position: 'bottom', offset: 0, fontSize: 11, fill: 'var(--color-text-300)' }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                    label={{ value: 'Count of Compounds', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: 'var(--color-text-300)' }}
                  />
                  <Tooltip />
                  <Legend verticalAlign="top" height={36} />
                  <Bar dataKey="negative" fill="var(--color-brand-600)" opacity={0.65} name="Negative Label (0)" />
                  <Bar dataKey="positive" fill="var(--color-red-500)" opacity={0.65} name="Positive Label (1)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Tab.Panel>

          {/* Learning Curve */}
          <Tab.Panel className="p-4 border rounded-xl bg-[var(--color-surface)] border-[var(--color-border)]">
            <div className="mb-2">
              <h4 className="text-sm font-semibold text-[var(--color-text-200)]">Classification Learning Curve</h4>
              <p className="text-xs text-[var(--color-text-400)]">Scores mean and standard deviation across increasing training sample splits.</p>
            </div>
            <div style={{ width: '100%', height: 350 }}>
              <ResponsiveContainer>
                <LineChart data={learning_curve} margin={{ top: 20, right: 30, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis
                    dataKey="train_size"
                    tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                    label={{ value: 'Number of Training Samples', position: 'bottom', offset: 0, fontSize: 11, fill: 'var(--color-text-300)' }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: 'var(--color-text-400)' }}
                    label={{ value: 'Performance Score (ROC-AUC)', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: 'var(--color-text-300)' }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="p-3 border rounded-lg bg-[var(--color-surface)] border-[var(--color-border)] shadow-xl text-xs space-y-1">
                            <p className="font-semibold text-[var(--color-text-100)]">Samples: {data.train_size}</p>
                            <p className="text-[var(--color-success-700)]">Train AUC: <span className="font-medium">{data.train_mean.toFixed(3)} ± {data.train_std.toFixed(3)}</span></p>
                            <p className="text-[var(--color-brand-700)]">Val AUC: <span className="font-medium">{data.val_mean.toFixed(3)} ± {data.val_std.toFixed(3)}</span></p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Legend verticalAlign="top" height={36} />
                  <Line dataKey="train_mean" stroke="var(--color-success-500)" strokeWidth={2} dot={{ r: 4.5 }} name="Training Score">
                    <ErrorBar dataKey="train_std" width={4} strokeWidth={1.5} stroke="var(--color-success-400)" direction="y" />
                  </Line>
                  <Line dataKey="val_mean" stroke="var(--color-brand-600)" strokeWidth={2} dot={{ r: 4.5 }} name="Cross-Validation Score">
                    <ErrorBar dataKey="val_std" width={4} strokeWidth={1.5} stroke="var(--color-brand-400)" direction="y" />
                  </Line>
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Tab.Panel>
        </Tab.Panels>
      </Tab.Group>
    </div>
  );
}
