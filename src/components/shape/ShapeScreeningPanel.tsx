import React, { useState } from 'react';
import { useShapeStore, ShapeResultItem } from '../../store/shapeStore';
import { useCompoundStore } from '../../store/compoundStore';
import { useProjectStore } from '../../store/projectStore';

interface ShapeScreeningPanelProps {
  candidates: Array<{ id: string; smiles: string; [key: string]: any }>;
  defaultReference?: string;
}

export const ShapeScreeningPanel: React.FC<ShapeScreeningPanelProps> = ({ candidates, defaultReference = '' }) => {
  const [reference, setReference] = useState<string>(defaultReference);
  const screen3d = useShapeStore((s) => s.screen3d);
  const screenResult = useShapeStore((s) => s.screenResult);
  const loading = useShapeStore((s) => s.loading);

  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const addCompound = useCompoundStore((s) => s.addCompound);

  const handleRun = async () => {
    if (!reference.trim() || candidates.length === 0) return;
    try {
      await screen3d(reference, candidates, 50);
    } catch (e) {
      console.error('3D Shape screening failed:', e);
    }
  };

  const handleAdd = async (smiles: string) => {
    if (!activeProjectId) return;
    try {
      await addCompound(activeProjectId, '3D Scaffold Hop Candidate', smiles);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div style={{ padding: '16px', background: 'var(--color-surface)', borderRadius: '8px', border: '0.5px solid var(--color-border)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-text-900)' }}>
        3D Shape & Electrostatic Similarity Screening (ROCS-Style Scaffold Hopping)
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '12px', alignItems: 'end' }}>
        <div>
          <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-500)', display: 'block', marginBottom: '4px' }}>
            Active Reference Ligand SMILES
          </label>
          <input
            type="text"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="e.g. CC(=O)NC1=CC=CC=C1"
            style={{ width: '100%', padding: '6px 10px', fontSize: '12px', borderRadius: '6px', border: '1px solid var(--color-border)' }}
          />
        </div>

        <button
          onClick={handleRun}
          disabled={loading || !reference.trim() || candidates.length === 0}
          style={{
            padding: '6px 16px',
            borderRadius: '6px',
            border: 'none',
            background: 'var(--color-brand-600)',
            color: 'white',
            fontWeight: 600,
            fontSize: '12px',
            cursor: loading ? 'wait' : 'pointer',
            opacity: loading || !reference.trim() || candidates.length === 0 ? 0.5 : 1,
          }}
        >
          {loading ? 'Aligning 3D Confs...' : 'Run 3D Screen'}
        </button>
      </div>

      {screenResult && screenResult.results && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-700)', marginBottom: '8px' }}>
            Ranked Candidates ({screenResult.n_returned} returned out of {screenResult.n_screened} screened)
          </div>

          <div style={{ overflowX: 'auto', borderRadius: '6px', border: '0.5px solid var(--color-border)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'rgba(0,0,0,0.03)', borderBottom: '1px solid var(--color-border)' }}>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Candidate SMILES</th>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>ComboScore (Max 2.0)</th>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Shape Sim (Open3DAlign)</th>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Electrostatic Sim (espsim)</th>
                  <th style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--color-text-600)' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {screenResult.results.map((item: ShapeResultItem, idx: number) => (
                  <tr key={idx} style={{ borderBottom: '0.5px solid var(--color-border)' }}>
                    <td style={{ padding: '6px 10px', fontFamily: 'monospace', fontSize: '11px', color: 'var(--color-text-800)' }}>
                      {item.smiles}
                    </td>
                    <td style={{ padding: '6px 10px' }}>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: item.combo_score >= 1.2 ? 'rgba(16, 185, 129, 0.15)' : item.combo_score >= 0.8 ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                          color: item.combo_score >= 1.2 ? '#10b981' : item.combo_score >= 0.8 ? '#f59e0b' : '#ef4444',
                        }}
                      >
                        {item.combo_score.toFixed(3)} / 2.0
                      </span>
                    </td>
                    <td style={{ padding: '6px 10px', color: 'var(--color-text-700)' }}>
                      {item.shape_score.toFixed(3)}
                    </td>
                    <td style={{ padding: '6px 10px', color: 'var(--color-text-700)' }}>
                      {item.esp_score.toFixed(3)}
                    </td>
                    <td style={{ padding: '6px 10px' }}>
                      <button
                        onClick={() => handleAdd(item.smiles)}
                        style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-brand-300)', background: 'var(--color-brand-50)', color: 'var(--color-brand-700)', fontWeight: 600, cursor: 'pointer' }}
                      >
                        + Library
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
