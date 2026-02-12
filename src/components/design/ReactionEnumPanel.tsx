import React, { useState, useEffect } from 'react';
import { useDesignStore, ReactionTemplate, ReactionEnumerateResult } from '../../store/designStore';
import { FeasibilityBadge } from '../retro/FeasibilityBadge';
import { useCompoundStore } from '../../store/compoundStore';
import { useProjectStore } from '../../store/projectStore';

interface ReactionEnumPanelProps {
  coreSmiles?: string;
}

export const ReactionEnumPanel: React.FC<ReactionEnumPanelProps> = ({ coreSmiles: initialCore }) => {
  const templates = useDesignStore((s) => s.reactionTemplates);
  const listTemplates = useDesignStore((s) => s.listReactionTemplates);
  const enumerateReaction = useDesignStore((s) => s.enumerateReaction);
  const loading = useDesignStore((s) => s.loading);

  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const addCompound = useCompoundStore((s) => s.addCompound);

  const [selectedTemplate, setSelectedTemplate] = useState<string>('amide_coupling');
  const [coreSmiles, setCoreSmiles] = useState<string>(initialCore || '');
  const [result, setResult] = useState<ReactionEnumerateResult | null>(null);

  useEffect(() => {
    listTemplates().catch(() => {});
  }, [listTemplates]);

  useEffect(() => {
    if (initialCore) setCoreSmiles(initialCore);
  }, [initialCore]);

  const handleRun = async () => {
    try {
      const res = await enumerateReaction(selectedTemplate, coreSmiles || undefined);
      setResult(res);
    } catch (e) {
      console.error(e);
    }
  };

  const handleAdd = async (smiles: string) => {
    if (!activeProjectId) return;
    try {
      await addCompound(activeProjectId, `Reaction product (${selectedTemplate})`, smiles);
    } catch (e) {
      console.error('Failed to add compound:', e);
    }
  };

  const currentTemplate = templates.find((t) => t.id === selectedTemplate);

  return (
    <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '16px' }}>
      <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-text-900)', marginBottom: '12px' }}>
        Combinatorial Reaction Enumeration
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '12px', alignItems: 'end', marginBottom: '16px' }}>
        <div>
          <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-500)', display: 'block', marginBottom: '4px' }}>
            Reaction Template
          </label>
          <select
            value={selectedTemplate}
            onChange={(e) => setSelectedTemplate(e.target.value)}
            style={{ width: '100%', padding: '6px 10px', fontSize: '12px', borderRadius: '6px', border: '1px solid var(--color-border)' }}
          >
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-500)', display: 'block', marginBottom: '4px' }}>
            Query Core SMILES (Optional)
          </label>
          <input
            type="text"
            value={coreSmiles}
            onChange={(e) => setCoreSmiles(e.target.value)}
            placeholder="e.g. CC(=O)O"
            style={{ width: '100%', padding: '6px 10px', fontSize: '12px', borderRadius: '6px', border: '1px solid var(--color-border)' }}
          />
        </div>

        <button
          onClick={handleRun}
          disabled={loading}
          style={{
            padding: '6px 16px',
            borderRadius: '6px',
            border: 'none',
            background: 'var(--color-brand-600)',
            color: 'white',
            fontWeight: 600,
            fontSize: '12px',
            cursor: loading ? 'wait' : 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? 'Enumerating...' : 'Enumerate Products'}
        </button>
      </div>

      {currentTemplate && (
        <div style={{ fontSize: '11px', color: 'var(--color-text-500)', background: 'rgba(0,0,0,0.02)', padding: '8px 12px', borderRadius: '6px', marginBottom: '16px' }}>
          <strong>SMARTS:</strong> <code style={{ fontFamily: 'monospace' }}>{currentTemplate.smarts}</code> &mdash; {currentTemplate.description}
        </div>
      )}

      {result && result.products && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-700)', marginBottom: '8px' }}>
            Enumerated Products ({result.n_passed} passed filters out of {result.n_generated} generated)
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px', maxHeight: '400px', overflowY: 'auto' }}>
            {result.products.map((p, idx) => (
              <div
                key={idx}
                style={{
                  padding: '10px',
                  borderRadius: '6px',
                  border: '0.5px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                }}
              >
                <div style={{ fontSize: '11px', fontFamily: 'monospace', wordBreak: 'break-all', color: 'var(--color-text-800)' }}>
                  {p.smiles}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
                  <FeasibilityBadge smiles={p.smiles} />
                  <button
                    onClick={() => handleAdd(p.smiles)}
                    style={{
                      fontSize: '10px',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      border: '0.5px solid var(--color-brand-300)',
                      background: 'var(--color-brand-50)',
                      color: 'var(--color-brand-700)',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    + Add to Library
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
