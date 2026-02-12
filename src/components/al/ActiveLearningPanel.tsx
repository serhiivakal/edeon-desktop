import React from 'react';
import { useActiveLearningStore, AlSuggestedCandidate } from '../../store/activeLearningStore';
import { useCompoundStore } from '../../store/compoundStore';
import { useProjectStore } from '../../store/projectStore';

interface ActiveLearningPanelProps {
  labeledPool: Array<{ id: string; smiles: string; [key: string]: any }>;
  candidatePool: Array<{ id: string; smiles: string; [key: string]: any }>;
}

export const ActiveLearningPanel: React.FC<ActiveLearningPanelProps> = ({ labeledPool, candidatePool }) => {
  const acquisition = useActiveLearningStore((s) => s.acquisition);
  const batchSize = useActiveLearningStore((s) => s.batchSize);
  const batchResult = useActiveLearningStore((s) => s.batchResult);
  const loading = useActiveLearningStore((s) => s.loading);

  const setAcquisition = useActiveLearningStore((s) => s.setAcquisition);
  const setBatchSize = useActiveLearningStore((s) => s.setBatchSize);
  const suggestNextBatch = useActiveLearningStore((s) => s.suggestNextBatch);

  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const addCompound = useCompoundStore((s) => s.addCompound);

  const handleRun = async () => {
    if (labeledPool.length === 0 || candidatePool.length === 0) return;
    try {
      await suggestNextBatch(labeledPool, candidatePool);
    } catch (e) {
      console.error('Active Learning batch selection failed:', e);
    }
  };

  const handleAdd = async (smiles: string) => {
    if (!activeProjectId) return;
    try {
      await addCompound(activeProjectId, 'AL Prioritized Batch', smiles);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div style={{ padding: '16px', background: 'var(--color-surface)', borderRadius: '8px', border: '0.5px solid var(--color-border)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-text-900)' }}>
            Bayesian-Optimization Active-Learning Loop (BoTorch / GPyTorch GP)
          </div>
          <div style={{ fontSize: '11px', color: 'var(--color-text-500)', marginTop: '2px' }}>
            Training Pool: {labeledPool.length} compounds &bull; Unlabeled Candidate Pool: {candidatePool.length} compounds
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={loading || labeledPool.length === 0 || candidatePool.length === 0}
          style={{
            padding: '6px 16px',
            borderRadius: '6px',
            border: 'none',
            background: 'var(--color-brand-600)',
            color: 'white',
            fontWeight: 600,
            fontSize: '12px',
            cursor: loading ? 'wait' : 'pointer',
            opacity: loading || labeledPool.length === 0 || candidatePool.length === 0 ? 0.5 : 1,
          }}
        >
          {loading ? 'Solving GP Model...' : 'Suggest Prioritized Batch'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', background: 'rgba(0,0,0,0.02)', padding: '12px', borderRadius: '6px', border: '0.5px solid var(--color-border)' }}>
        <div>
          <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-600)', display: 'block', marginBottom: '4px' }}>
            Acquisition Policy
          </label>
          <select
            value={acquisition}
            onChange={(e) => setAcquisition(e.target.value as any)}
            style={{ width: '100%', padding: '6px 10px', fontSize: '12px', borderRadius: '6px', border: '1px solid var(--color-border)', background: 'var(--color-surface)' }}
          >
            <option value="ei">Expected Improvement (EI)</option>
            <option value="ucb">Upper Confidence Bound (UCB)</option>
            <option value="ts">Thompson Sampling (TS)</option>
          </select>
        </div>

        <div>
          <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-600)', display: 'block', marginBottom: '4px' }}>
            Batch Size (N)
          </label>
          <input
            type="number"
            min={1}
            max={50}
            value={batchSize}
            onChange={(e) => setBatchSize(parseInt(e.target.value) || 10)}
            style={{ width: '100%', padding: '6px 10px', fontSize: '12px', borderRadius: '6px', border: '1px solid var(--color-border)', background: 'var(--color-surface)' }}
          />
        </div>

        <div>
          <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-600)', display: 'block', marginBottom: '4px' }}>
            Surrogate GP Metric
          </label>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-brand-600)', paddingTop: '6px' }}>
            {batchResult && batchResult.model_metrics ? `R² = ${(batchResult.model_metrics.r2_score * 100).toFixed(1)}% (f* = ${batchResult.model_metrics.f_best})` : 'Unfitted'}
          </div>
        </div>
      </div>

      {batchResult && batchResult.suggested_batch && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-700)', marginBottom: '8px' }}>
            Recommended Priority Synthesis Batch ({batchResult.suggested_batch.length} compounds prioritized via {batchResult.acquisition_method})
          </div>

          <div style={{ overflowX: 'auto', borderRadius: '6px', border: '0.5px solid var(--color-border)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'rgba(0,0,0,0.03)', borderBottom: '1px solid var(--color-border)' }}>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Rank</th>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Candidate SMILES</th>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Predicted Mean (&mu;)</th>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>GP Uncertainty (&plusmn;2&sigma;)</th>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Acquisition Score</th>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {batchResult.suggested_batch.map((cand: AlSuggestedCandidate) => (
                  <tr key={cand.rank} style={{ borderBottom: '0.5px solid var(--color-border)' }}>
                    <td style={{ padding: '6px 10px', fontWeight: 700, color: 'var(--color-text-900)' }}>
                      #{cand.rank}
                    </td>
                    <td style={{ padding: '6px 10px', fontFamily: 'monospace', fontSize: '11px', color: 'var(--color-text-800)' }}>
                      {cand.smiles}
                    </td>
                    <td style={{ padding: '6px 10px', fontWeight: 600, color: '#10b981' }}>
                      {cand.predicted_mean.toFixed(2)}
                    </td>
                    <td style={{ padding: '6px 10px', color: 'var(--color-text-600)' }}>
                      &plusmn; {(cand.predicted_std * 2.0).toFixed(2)}
                    </td>
                    <td style={{ padding: '6px 10px' }}>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: 'rgba(59, 130, 246, 0.15)',
                          color: '#3b82f6',
                        }}
                      >
                        {cand.acquisition_score.toFixed(3)}
                      </span>
                    </td>
                    <td style={{ padding: '6px 10px' }}>
                      <button
                        onClick={() => handleAdd(cand.smiles)}
                        style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-brand-300)', background: 'var(--color-brand-50)', color: 'var(--color-brand-700)', fontWeight: 600, cursor: 'pointer' }}
                      >
                        + Synthesize
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
