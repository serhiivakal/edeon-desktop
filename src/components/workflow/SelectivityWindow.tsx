import { useState } from 'react';

interface SelectivityProfile {
  organism: string;
  latin: string;
  selectivity_index: number;
  level: 'safe' | 'moderate' | 'danger';
  detail: string;
  ci_lower: number;
  ci_upper: number;
  ad_status: string;
}

interface AnalogDetail {
  smiles: string;
  transformation: string;
  min_selectivity: number;
  lift: number;
  collapses_margin: boolean;
  trade_offs: string[];
  rank_score: number;
  is_in_domain: boolean;
  profiles: SelectivityProfile[];
}

interface SelectivityWindowProps {
  parentMinMargin: number;
  limitingOrganism: string;
  parentProfiles: SelectivityProfile[];
  analogs: AnalogDetail[];
}

export function SelectivityWindow({ limitingOrganism, parentProfiles, analogs }: SelectivityWindowProps) {
  const [selectedAnalogIndex, setSelectedAnalogIndex] = useState<number>(0);

  if (!parentProfiles || parentProfiles.length === 0) return null;

  const selectedAnalog = analogs && analogs.length > selectedAnalogIndex ? analogs[selectedAnalogIndex] : null;

  // Organism order mapping to keep charts consistent
  const organisms = ['Honeybee', 'Earthworm', 'Fish', 'Bird', 'Daphnia', 'Mammal'];

  const getProfileForOrganism = (profiles: SelectivityProfile[], org: string) => {
    return profiles.find(p => p.organism.toLowerCase() === org.toLowerCase());
  };

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
      gap: '18px'
    }}>
      <div>
        <h3 style={{ margin: '0 0 4px 0', fontSize: '16px', fontWeight: 600, color: 'var(--color-brand-900)' }}>
          🎯 Selectivity Window Margin Optimization
        </h3>
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--color-text-500)' }}>
          Widen limiting safety margins across non-target species. Highlighted organism indicates the primary liability.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: '20px', alignItems: 'flex-start' }}>
        {/* Left list of suggestions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <h4 style={{ margin: '0 0 4px 0', fontSize: '13px', fontWeight: 600, color: 'var(--color-text-600)' }}>
            Suggested Analogs
          </h4>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            maxHeight: '320px',
            overflowY: 'auto',
            paddingRight: '4px'
          }}>
            {analogs && analogs.length > 0 ? (
              analogs.map((analog, idx) => {
                const isSelected = idx === selectedAnalogIndex;
                return (
                  <button
                    key={idx}
                    onClick={() => setSelectedAnalogIndex(idx)}
                    style={{
                      padding: '12px',
                      textAlign: 'left',
                      background: isSelected ? 'rgba(var(--color-brand-rgb), 0.05)' : 'var(--color-surface)',
                      border: '1px solid',
                      borderColor: isSelected ? 'var(--color-brand-500)' : 'var(--color-border)',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div style={{
                      fontWeight: 600,
                      fontSize: '13px',
                      color: isSelected ? 'var(--color-brand-900)' : 'var(--color-text-900)',
                      wordBreak: 'break-all'
                    }}>
                      {analog.transformation}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--color-text-500)' }}>
                      <span>Min Margin: {analog.min_selectivity.toFixed(1)}x</span>
                      <span style={{
                        color: analog.lift > 0 ? 'var(--color-success)' : 'var(--color-error)',
                        fontWeight: 600
                      }}>
                        {analog.lift >= 0 ? `+${analog.lift.toFixed(1)}x` : `${analog.lift.toFixed(1)}x`} lift
                      </span>
                    </div>
                    {analog.collapses_margin && (
                      <div style={{ fontSize: '10px', color: '#b91c1c', marginTop: '2px', fontWeight: 500 }}>
                        ⚠️ Trade-off: collapses another margin
                      </div>
                    )}
                  </button>
                );
              })
            ) : (
              <div style={{ fontSize: '12px', color: 'var(--color-text-400)', padding: '12px', textAlign: 'center' }}>
                No analogs suggested.
              </div>
            )}
          </div>
        </div>

        {/* Right selectivity window comparison charts */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <h4 style={{ margin: '0 0 4px 0', fontSize: '13px', fontWeight: 600, color: 'var(--color-text-600)' }}>
            Species Safety Margin Comparison
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {organisms.map(org => {
              const pProfile = getProfileForOrganism(parentProfiles, org);
              const aProfile = selectedAnalog ? getProfileForOrganism(selectedAnalog.profiles, org) : null;
              
              if (!pProfile) return null;

              const isLimiting = org.toLowerCase() === limitingOrganism.toLowerCase();
              const pVal = pProfile.selectivity_index;
              const aVal = aProfile ? aProfile.selectivity_index : pVal;

              // Compute max range for layout scaling (max of 100 fold safety margin)
              const maxScaleVal = 100.0;
              const pPercent = Math.min(100, (pVal / maxScaleVal) * 100);
              const aPercent = Math.min(100, (aVal / maxScaleVal) * 100);

              return (
                <div
                  key={org}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '100px 1fr 80px',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '8px 12px',
                    background: isLimiting ? 'rgba(234, 179, 8, 0.05)' : 'transparent',
                    border: isLimiting ? '1px solid rgba(234, 179, 8, 0.2)' : 'none',
                    borderRadius: '6px'
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                      {org} {isLimiting && '🎯'}
                    </span>
                    <span style={{ fontSize: '10px', color: 'var(--color-text-400)', fontStyle: 'italic' }}>
                      {pProfile.latin}
                    </span>
                  </div>

                  {/* Dual Bar Chart */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {/* Parent bar */}
                    <div style={{ height: '8px', background: '#e5e7eb', borderRadius: '4px', position: 'relative', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${pPercent}%`,
                        background: '#9ca3af',
                        borderRadius: '4px'
                      }} />
                    </div>
                    {/* Analog bar */}
                    {selectedAnalog && (
                      <div style={{ height: '8px', background: '#e5e7eb', borderRadius: '4px', position: 'relative', overflow: 'hidden' }}>
                        <div style={{
                          height: '100%',
                          width: `${aPercent}%`,
                          background: aVal < pVal ? '#f87171' : 'var(--color-brand-500)',
                          borderRadius: '4px'
                        }} />
                      </div>
                    )}
                  </div>

                  {/* Values label */}
                  <div style={{ textAlign: 'right', fontSize: '12px' }}>
                    <div style={{ color: '#4b5563' }}>Lead: {pVal.toFixed(0)}x</div>
                    {selectedAnalog && (
                      <div style={{
                        fontWeight: 600,
                        color: aVal > pVal ? 'var(--color-success)' : aVal < pVal ? 'var(--color-error)' : '#4b5563'
                      }}>
                        Anal: {aVal.toFixed(0)}x
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Legend and Info */}
          {selectedAnalog && (
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: '11px',
              color: 'var(--color-text-500)',
              marginTop: '10px',
              borderTop: '1px solid var(--color-border)',
              paddingTop: '8px'
            }}>
              <div style={{ display: 'flex', gap: '10px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ width: '8px', height: '8px', background: '#9ca3af', borderRadius: '2px' }} /> Lead compound
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ width: '8px', height: '8px', background: 'var(--color-brand-500)', borderRadius: '2px' }} /> Optimized Analog
                </span>
              </div>
              <div>
                * Safety margins capped at 100x fold-change for visualization.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
