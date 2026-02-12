import { useEffect, useState } from 'react';
import { useWorkflowStore, WorkflowType } from '../store/workflowStore';
import { EmptyState } from '../components/shared/EmptyState';
import { FolderOpen } from 'lucide-react';

export function WorkflowGalleryView() {
  const { availableWorkflows, fetchAvailableWorkflows, setSelectedWorkflowId, setWorkflowType } = useWorkflowStore();
  const [activeTab, setActiveTab] = useState<'packaged' | 'interactive'>('packaged');

  useEffect(() => {
    fetchAvailableWorkflows();
  }, [fetchAvailableWorkflows]);

  // Map backend IDs to clean display details
  const cardsDetails: Record<string, { desc: string; icon: string; color: string }> = {
    registration_readiness: {
      desc: "Comprehensive regulatory pre-screening under EU 1107/2009 & EFSA guidelines. Detects PBT, PMT, endocrine disruption, and groundwater hazards for parents and metabolites.",
      icon: "📋",
      color: "var(--color-brand-700)"
    },
    pollinator_safety: {
      desc: "Advanced ecotoxicological risk assessment. Weights intrinsic honeybee hazard (oral & contact) against exposure likelihood using Briggs/Kleier systemicity models.",
      icon: "🐝",
      color: "#d97706" // amber/gold
    },
    tp_liability: {
      desc: "Degradation liability sweep. Simulates metabolic and abiotic transformation pathways, profiles all generated metabolites, and flags offspring worse than their parents.",
      icon: "🌱",
      color: "#059669" // emerald
    },
    lead_optimization: {
      desc: "Multi-objective lead optimization assistant. Identifies key series liabilities, generates bioisosteric analog proposals, and ranks them while gating out-of-domain predictions.",
      icon: "⚡",
      color: "var(--color-blue-500)"
    },
    hit_triage: {
      desc: "Top-of-funnel triage system. Gates raw hit libraries by pesticide-likeness and PAINS alerts, downsamples to diverse candidates, and ranks via custom MPO presets.",
      icon: "📉",
      color: "#8b5cf6" // purple
    },
    comparative_benchmarking: {
      desc: "Position candidates against standard marketed actives. Aligns persistency, fate, and safety axes with visual predicted vs. measured references.",
      icon: "📊",
      color: "#3b82f6" // blue
    },
    selectivity_optimization: {
      desc: "Widen limiting safety margins across non-target species using maximin multi-species objectives, ranking structural analog candidates.",
      icon: "🎯",
      color: "#ec4899" // pink
    },
    scaffold_hop: {
      desc: "Generate novel scaffolds retaining your lead's safety and fate profile. Ranks proposals by structural distance with legal/FTO warning protections.",
      icon: "🔍",
      color: "#f59e0b" // amber
    }
  };

  const interactiveWorkflows: { id: WorkflowType; name: string; persona: string; desc: string; icon: string; stepsCount: number; color: string }[] = [
    {
      id: 'library_prep',
      name: "Screening Library Preparation",
      persona: "Discovery / Library Prep",
      desc: "Standardize imported structures, apply Lipinski and Tice herbicide rules, filter toxicophores (PAINS), perform Butina diversity clustering, and optimize 3D conformers at pH 7.4.",
      icon: "📚",
      stepsCount: 6,
      color: "var(--color-brand-700)"
    },
    {
      id: 'active_learning',
      name: "Virtual Screening & Active Learning Gate",
      persona: "Virtual Screening",
      desc: "Execute high-throughput virtual screening (HTVS) cycles combined with active learning loops. Curate activity data, perform QSAR inference, filter by Applicability Domain (AD), and validate with AutoDock Vina.",
      icon: "⚡",
      stepsCount: 7,
      color: "#d97706"
    },
    {
      id: 'bioisostere_opt',
      name: "Bioisosteric Lead Optimization",
      persona: "Medicinal Chemistry",
      desc: "Interactively suggest bioisosteres and run rescoring/docking loops. Computes physicochemical properties, target affinity predictions, MPO scores, and 2D/3D interaction contacts maps.",
      icon: "🧬",
      stepsCount: 7,
      color: "#059669"
    },
    {
      id: 'resistance_mitigation',
      name: "Target-Site Resistance Mitigation",
      persona: "Ecotox / Safety",
      desc: "Profile target mutation escape rates and select bypass chemistries. Simulates AutoDock Vina WT vs. mutant receptor docking, and runs ecotox profiling side-by-side.",
      icon: "🛡️",
      stepsCount: 7,
      color: "var(--color-blue-500)"
    },
    {
      id: 'lead_opt',
      name: "Lead Optimization Pre-Screen",
      persona: "Medicinal Chemistry",
      desc: "Standard screening workflow for a lead series. Computes physicochemical parameters, Tice compliance, ecotox selectivity margins, and resistance risk scores.",
      icon: "🚀",
      stepsCount: 7,
      color: "#7c3aed"
    }
  ];

  const handleSelectPackaged = (id: string) => {
    setSelectedWorkflowId(id);
  };

  const handleSelectInteractive = (id: WorkflowType) => {
    setWorkflowType(id);
    setSelectedWorkflowId('legacy');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', padding: '24px 32px', boxSizing: 'border-box' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 600, color: 'var(--color-brand-900)', margin: '0 0 8px 0' }}>
          Workflow Gallery
        </h1>
        <p style={{ fontSize: '15px', color: 'var(--color-text-600)', margin: 0 }}>
          Select a packaged decision-grade dossier workflow or run an interactive legacy simulation pipeline.
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '32px', borderBottom: '1px solid var(--color-border)', paddingBottom: '12px' }}>
        <button
          onClick={() => setActiveTab('packaged')}
          style={{
            padding: '8px 16px',
            fontSize: '14px',
            fontWeight: 600,
            borderRadius: '6px',
            border: '1px solid',
            borderColor: activeTab === 'packaged' ? 'var(--color-brand-500)' : 'var(--color-border)',
            backgroundColor: activeTab === 'packaged' ? 'rgba(74, 117, 89, 0.08)' : 'var(--color-surface)',
            color: activeTab === 'packaged' ? 'var(--color-brand-900)' : 'var(--color-text-600)',
            cursor: 'pointer',
            transition: 'all 0.2s',
            outline: 'none'
          }}
        >
          📁 Packaged Dossiers (W1 - W8)
        </button>
        <button
          onClick={() => setActiveTab('interactive')}
          style={{
            padding: '8px 16px',
            fontSize: '14px',
            fontWeight: 600,
            borderRadius: '6px',
            border: '1px solid',
            borderColor: activeTab === 'interactive' ? 'var(--color-brand-500)' : 'var(--color-border)',
            backgroundColor: activeTab === 'interactive' ? 'rgba(74, 117, 89, 0.08)' : 'var(--color-surface)',
            color: activeTab === 'interactive' ? 'var(--color-brand-900)' : 'var(--color-text-600)',
            cursor: 'pointer',
            transition: 'all 0.2s',
            outline: 'none'
          }}
        >
          🧪 Interactive Legacy Workflows
        </button>
      </div>

      {activeTab === 'packaged' ? (
        availableWorkflows.length === 0 ? (
          <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
            <EmptyState
              icon={<FolderOpen size={20} />}
              title="No workflows available"
              description="The packaged dossier templates catalog is currently empty. Reload or check connection."
              primaryAction={{
                label: "Reload Workflows",
                onClick: fetchAvailableWorkflows
              }}
            />
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '24px', flex: 1 }}>
            {availableWorkflows.map((wf) => {
              const detail = cardsDetails[wf.id] || {
                desc: "Custom pre-made recipe workflow.",
                icon: "⚙️",
                color: "var(--color-brand-700)"
              };

              return (
                <div
                  key={wf.id}
                  onClick={() => handleSelectPackaged(wf.id)}
                  className="card-hover-animation"
                  style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    padding: '24px',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    transition: 'all 200ms ease',
                    position: 'relative',
                    overflow: 'hidden',
                    boxShadow: 'var(--shadow-sm)'
                  }}
                >
                  {/* Colored top bar accent */}
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '4px', backgroundColor: detail.color }} />

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <span style={{ fontSize: '32px' }}>{detail.icon}</span>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        color: 'var(--color-text-600)',
                        background: 'var(--color-sidebar)',
                        padding: '4px 8px',
                        borderRadius: '4px'
                      }}
                    >
                      {wf.persona}
                    </span>
                  </div>

                  <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-brand-900)', margin: '0 0 10px 0' }}>
                    {wf.name}
                  </h3>

                  <p style={{ fontSize: '13px', lineHeight: 1.5, color: 'var(--color-text-600)', margin: '0 0 20px 0', flex: 1 }}>
                    {detail.desc}
                  </p>

                  <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: 'var(--color-text-400)' }}>
                    <span>Input: <strong style={{ color: 'var(--color-text-600)' }}>{wf.input_kind}</strong></span>
                    <span>{wf.step_names.length} steps</span>
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '24px', flex: 1 }}>
          {interactiveWorkflows.map((wf) => {
            return (
              <div
                key={wf.id}
                onClick={() => handleSelectInteractive(wf.id)}
                className="card-hover-animation"
                style={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '8px',
                  padding: '24px',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'all 200ms ease',
                  position: 'relative',
                  overflow: 'hidden',
                  boxShadow: 'var(--shadow-sm)'
                }}
              >
                {/* Colored top bar accent */}
                <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '4px', backgroundColor: wf.color }} />

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <span style={{ fontSize: '32px' }}>{wf.icon}</span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      color: 'var(--color-text-600)',
                      background: 'var(--color-sidebar)',
                      padding: '4px 8px',
                      borderRadius: '4px'
                    }}
                  >
                    {wf.persona}
                  </span>
                </div>

                <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-brand-900)', margin: '0 0 10px 0' }}>
                  {wf.name}
                </h3>

                <p style={{ fontSize: '13px', lineHeight: 1.5, color: 'var(--color-text-600)', margin: '0 0 20px 0', flex: 1 }}>
                  {wf.desc}
                </p>

                <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: 'var(--color-text-400)' }}>
                  <span>Interactive Simulation</span>
                  <span>{wf.stepsCount} stages</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div style={{ marginTop: '32px', padding: '16px', background: 'var(--color-brand-100)', border: '1px solid var(--color-brand-50)', borderRadius: '6px', fontSize: '13px', color: 'var(--color-brand-900)' }}>
        <strong>💡 Pro-tip:</strong> Use <strong>Packaged Dossiers</strong> for decision-grade screenings with structured PDF reports, and use <strong>Interactive Legacy Workflows</strong> for manual, stage-by-stage simulations (e.g., custom bioisostere generation, docking, and 3D pose inspections).
      </div>
    </div>
  );
}
