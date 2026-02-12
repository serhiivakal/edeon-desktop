import { useState } from 'react';

interface ComparisonAxis {
  candidate_value: number;
  candidate_source: string;
  candidate_ad: string;
  reference_value: number;
  reference_source: string;
  reference_ref: string;
  comparison: 'better' | 'comparable' | 'worse';
}

interface ComparisonActive {
  reference_id: string;
  reference_name: string;
  reference_smiles: string;
  reference_moa: string;
  axes: Record<string, ComparisonAxis>;
  better_count: number;
  worse_count: number;
}

interface PositioningChartbookProps {
  comparisons: ComparisonActive[];
  candidateName: string;
}

export function PositioningChartbook({ comparisons, candidateName }: PositioningChartbookProps) {
  const [activeTab, setActiveTab] = useState<number>(0);

  if (!comparisons || comparisons.length === 0) {
    return (
      <div style={{ padding: '16px', border: '1px dashed var(--color-border)', borderRadius: '8px', textAlign: 'center', color: 'var(--color-text-400)' }}>
        No reference active comparisons available.
      </div>
    );
  }

  const selectedRef = comparisons[activeTab];

  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.6)',
      backdropFilter: 'blur(8px)',
      border: '1px solid var(--color-border)',
      borderRadius: '12px',
      padding: '20px',
      boxShadow: 'var(--shadow-md)',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '16px', fontWeight: 600, color: 'var(--color-brand-900)' }}>
            📊 Competitive Positioning Chartbook
          </h3>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--color-text-500)' }}>
            Benchmark candidate safety and fate profiles against standard marketed actives.
          </p>
        </div>
        
        {/* Source indicator legend */}
        <div style={{ display: 'flex', gap: '12px', fontSize: '11px', background: 'var(--color-surface)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--color-border)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#3b82f6' }} /> Measured
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#8b5cf6' }} /> Predicted
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444' }} /> Out of Domain (OOD)
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--color-border)', paddingBottom: '8px', overflowX: 'auto' }}>
        {comparisons.map((ref, idx) => (
          <button
            key={ref.reference_id}
            onClick={() => setActiveTab(idx)}
            style={{
              padding: '6px 12px',
              fontSize: '13px',
              fontWeight: 500,
              border: '1px solid',
              borderColor: activeTab === idx ? 'var(--color-brand-500)' : 'var(--color-border)',
              backgroundColor: activeTab === idx ? 'rgba(var(--color-brand-rgb), 0.05)' : 'transparent',
              color: activeTab === idx ? 'var(--color-brand-900)' : 'var(--color-text-600)',
              borderRadius: '6px',
              cursor: 'pointer',
              whiteSpace: 'nowrap'
            }}
          >
            vs. {ref.reference_name} ({ref.better_count} W / {ref.worse_count} L)
          </button>
        ))}
      </div>

      {/* Active Comparison Detail */}
      {selectedRef && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Ref Info Header */}
          <div style={{ padding: '12px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
            <div>
              <span style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 600, color: 'var(--color-text-400)' }}>Reference Standard</span>
              <h4 style={{ margin: '2px 0 0 0', fontSize: '15px', color: 'var(--color-text-900)' }}>{selectedRef.reference_name}</h4>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 600, color: 'var(--color-text-400)' }}>Mechanism of Action</span>
              <div style={{ margin: '2px 0 0 0', fontSize: '13px', color: 'var(--color-text-700)' }}>{selectedRef.reference_moa || 'Unknown MoA'}</div>
            </div>
          </div>

          {/* Axes comparison grid */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {Object.entries(selectedRef.axes).map(([axisName, axisData]) => {
              const friendlyName = axisName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
              
              // Resolve status classes/colors
              const compColors = {
                better: { bg: 'rgba(74, 222, 128, 0.1)', border: '#4ade80', text: '#166534', label: 'Better' },
                comparable: { bg: 'rgba(209, 213, 219, 0.2)', border: '#d1d5db', text: '#374151', label: 'Comparable' },
                worse: { bg: 'rgba(248, 113, 113, 0.1)', border: '#f87171', text: '#991b1b', label: 'Worse' }
              };
              
              const compStyle = compColors[axisData.comparison];
              const isOod = axisData.candidate_ad === 'out' || axisData.candidate_ad === 'out_of_domain';
              
              return (
                <div
                  key={axisName}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '150px 1fr 1fr 100px',
                    alignItems: 'center',
                    gap: '16px',
                    padding: '12px 16px',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    backgroundColor: 'var(--color-surface)',
                    position: 'relative'
                  }}
                >
                  {/* Axis Title */}
                  <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--color-text-800)' }}>
                    {friendlyName}
                  </div>

                  {/* Candidate Value */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>{candidateName} (You)</span>
                      <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text-900)' }}>
                        {axisData.candidate_value.toFixed(1)}
                      </span>
                    </div>
                    <span style={{
                      fontSize: '10px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: isOod ? 'rgba(239, 68, 68, 0.1)' : 'rgba(139, 92, 246, 0.1)',
                      color: isOod ? '#ef4444' : '#8b5cf6',
                      border: '1px solid',
                      borderColor: isOod ? '#ef4444' : 'transparent',
                      fontWeight: 500
                    }}>
                      {isOod ? '⚠️ OOD' : 'Predicted'}
                    </span>
                  </div>

                  {/* Reference Value */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>{selectedRef.reference_name}</span>
                      <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text-900)' }}>
                        {axisData.reference_value.toFixed(1)}
                      </span>
                    </div>
                    <span style={{
                      fontSize: '10px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: axisData.reference_source === 'measured' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(139, 92, 246, 0.1)',
                      color: axisData.reference_source === 'measured' ? '#3b82f6' : '#8b5cf6',
                      fontWeight: 500
                    }} title={axisData.reference_ref}>
                      {axisData.reference_source === 'measured' ? 'Measured' : 'Predicted'}
                    </span>
                  </div>

                  {/* Verdict badge */}
                  <div style={{
                    padding: '4px 8px',
                    borderRadius: '6px',
                    backgroundColor: compStyle.bg,
                    border: `1px solid ${compStyle.border}`,
                    color: compStyle.text,
                    fontSize: '11px',
                    fontWeight: 600,
                    textAlign: 'center',
                    textTransform: 'uppercase'
                  }}>
                    {compStyle.label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
