import React, { useState } from 'react';
import { VerdictHeader } from './VerdictHeader';
import { useWorkflowStore } from '../../store/workflowStore';
import { useUIStore } from '../../store/uiStore';
import { AttritionWaterfall } from './AttritionWaterfall';
import { PositioningChartbook } from './PositioningChartbook';
import { SelectivityWindow } from './SelectivityWindow';

import { BottleneckCard } from '../bottleneck/BottleneckCard';
import { useBottleneckStore } from '../../store/bottleneckStore';

interface DecisionArtifactProps {
  workflowResult: {
    id: string;
    name: string;
    status: string;
    started_at: string;
    completed_at: string | null;
    workflow_id: string;
    params: Record<string, any>;
    verdict: {
      overall: {
        band: string;
        driver: string;
        confidence: string;
        rationale: string;
      } | null;
      sections: Record<string, string>;
      warnings: string[];
    } | null;
    provenance: Record<string, any>;
  };
}

export function DecisionArtifact({ workflowResult }: DecisionArtifactProps) {
  const [showProvenance, setShowProvenance] = useState(false);

  const verdict = workflowResult.verdict?.overall;
  const sections = (workflowResult.verdict?.sections || {}) as Record<string, any>;
  const warnings = workflowResult.verdict?.warnings || [];
  const provenance = workflowResult.provenance || {};

  const results = useWorkflowStore((s) => s.results);
  const selectedCompoundId = useUIStore((s) => s.selectedCompoundId);
  const selectedCompound = results.find((r) => r.id === selectedCompoundId) || results[0];

  const bottleneckAnalysis = useBottleneckStore((s) => s.analysis);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '16px', background: 'var(--color-bg)', borderRadius: '8px', border: '1px solid var(--color-border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-brand-900)', margin: '0 0 4px 0' }}>
            Decision Dossier: {workflowResult.name}
          </h2>
          <div style={{ fontSize: '12px', color: 'var(--color-text-400)' }}>
            Run ID: <span style={{ fontFamily: 'var(--font-mono)' }}>{workflowResult.id}</span> · Completed: {workflowResult.completed_at ? new Date(workflowResult.completed_at).toLocaleString() : 'N/A'}
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={() => setShowProvenance(!showProvenance)}
            style={{
              padding: '6px 12px',
              fontSize: '13px',
              fontWeight: 500,
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            {showProvenance ? 'Hide Provenance' : 'Show Provenance'}
          </button>
        </div>
      </div>

      {verdict && (
        <VerdictHeader verdict={verdict} warnings={warnings} />
      )}

      {bottleneckAnalysis && (
        <BottleneckCard analysis={bottleneckAnalysis} />
      )}

      {/* Scaffold-Hop Legal & FTO Warning Disclaimer Banner */}
      {workflowResult.workflow_id === 'scaffold_hop' && sections.legal_disclaimer && (
        <div style={{
          backgroundColor: 'rgba(251, 191, 36, 0.08)',
          border: '1px dashed #fbbf24',
          borderRadius: '8px',
          padding: '16px',
          display: 'flex',
          gap: '12px',
          alignItems: 'flex-start',
          boxShadow: 'var(--shadow-sm)'
        }}>
          <span style={{ fontSize: '20px' }}>⚠️</span>
          <div>
            <h4 style={{ margin: '0 0 4px 0', fontSize: '13px', fontWeight: 600, color: '#b45309', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Legal & FTO Disclaimer
            </h4>
            <p style={{ margin: 0, fontSize: '12px', lineHeight: 1.6, color: '#78350f', fontWeight: 500 }}>
              {sections.legal_disclaimer}
            </p>
          </div>
        </div>
      )}

      {/* Custom Tier 2 Workflow Views */}
      {workflowResult.workflow_id === 'hit_triage' && sections.attrition && (
        <AttritionWaterfall attrition={sections.attrition} />
      )}

      {workflowResult.workflow_id === 'comparative_benchmarking' && selectedCompound && (
        <PositioningChartbook
          comparisons={(selectedCompound as any).comparisons}
          candidateName={selectedCompound.name}
        />
      )}

      {workflowResult.workflow_id === 'selectivity_optimization' && selectedCompound && (
        <SelectivityWindow
          parentMinMargin={(selectedCompound as any).parent_min_margin}
          limitingOrganism={(selectedCompound as any).limiting_organism}
          parentProfiles={(selectedCompound as any).parent_profiles}
          analogs={(selectedCompound as any).analogs}
        />
      )}

      {/* Dossier Structured Sections */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {Object.entries(sections)
          .filter(([key]) => !['attrition', 'reference_actives_queried', 'legal_disclaimer'].includes(key))
          .map(([key, content]) => {
            // Format label nicely
            const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            const isDisclaimer = key === 'disclaimer';
            
            return (
              <div
                key={key}
                style={{
                  backgroundColor: isDisclaimer ? '#fcfcf9' : 'var(--color-surface)',
                  border: isDisclaimer ? '1px dashed var(--color-border-subtle)' : '1px solid var(--color-border)',
                  borderRadius: '6px',
                  padding: '16px',
                  boxShadow: isDisclaimer ? 'none' : 'var(--shadow-sm)'
                }}
              >
                <h4 style={{
                  margin: '0 0 8px 0',
                  fontSize: '13px',
                  fontWeight: 600,
                  color: isDisclaimer ? 'var(--color-text-600)' : 'var(--color-brand-900)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}>
                  {label}
                </h4>
                <p style={{
                  margin: 0,
                  fontSize: isDisclaimer ? '12px' : '14px',
                  lineHeight: 1.6,
                  color: isDisclaimer ? 'var(--color-text-600)' : 'var(--color-text-900)',
                  fontStyle: isDisclaimer ? 'italic' : 'normal'
                }}>
                  {content}
                </p>
              </div>
            );
          })}
      </div>

      {/* Provenance Manifest Card */}
      {showProvenance && (
        <div style={{ padding: '16px', background: '#f5f5f0', border: '1px solid var(--color-border)', borderRadius: '6px', fontSize: '13px' }}>
          <h4 style={{ margin: '0 0 10px 0', color: 'var(--color-brand-900)' }}>🛰️ Reproducibility & Provenance Manifest</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: '8px', fontFamily: 'var(--font-mono)', fontSize: '12px', wordBreak: 'break-all' }}>
            <strong>Edeon Version:</strong> <span>{provenance.edeon_version || '0.1.0'}</span>
            <strong>Workflow Spec:</strong> <span>{provenance.workflow_id} (v{provenance.workflow_version || '1.0'})</span>
            <strong>Run Date:</strong> <span>{provenance.run_utc}</span>
            <strong>Input Hash:</strong> <span>{provenance.input_hash}</span>
            {provenance.model_ids && (
              <>
                <strong style={{ gridColumn: '1 / -1', marginTop: '8px', borderBottom: '1px solid var(--color-border)', paddingBottom: '4px', color: 'var(--color-text-600)' }}>Active Models:</strong>
                {Object.entries(provenance.model_ids).map(([m, v]) => (
                  <React.Fragment key={m}>
                    <span style={{ paddingLeft: '10px' }}>{m}:</span> <span>{v as string}</span>
                  </React.Fragment>
                ))}
              </>
            )}
            {provenance.params && (
              <>
                <strong style={{ gridColumn: '1 / -1', marginTop: '8px', borderBottom: '1px solid var(--color-border)', paddingBottom: '4px', color: 'var(--color-text-600)' }}>Parameters:</strong>
                {Object.entries(provenance.params).map(([k, v]) => (
                  <React.Fragment key={k}>
                    <span style={{ paddingLeft: '10px' }}>{k}:</span> <span>{JSON.stringify(v)}</span>
                  </React.Fragment>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
