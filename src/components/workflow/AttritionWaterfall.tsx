
interface AttritionStage {
  stage: string;
  in: number;
  out: number;
  dropped: number;
  reason: string;
}

interface AttritionWaterfallProps {
  attrition: AttritionStage[];
}

export function AttritionWaterfall({ attrition }: AttritionWaterfallProps) {
  if (!attrition || attrition.length === 0) return null;

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
      <h3 style={{
        margin: '0 0 4px 0',
        fontSize: '16px',
        fontWeight: 600,
        color: 'var(--color-brand-900)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
        📉 Attrition Waterfall Funnel
      </h3>
      <p style={{ margin: 0, fontSize: '13px', color: 'var(--color-text-500)', lineHeight: '1.4' }}>
        Visual breakdown of compound filter attrition across triage gating stages.
      </p>

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        marginTop: '8px'
      }}>
        {attrition.map((stage, idx) => {
          const retentionRate = stage.in > 0 ? ((stage.out / stage.in) * 100).toFixed(0) : '0';
          const stageName = stage.stage.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
          
          return (
            <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                padding: '12px 16px',
                position: 'relative',
                overflow: 'hidden'
              }}>
                {/* Visual indicator bar */}
                <div style={{
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  bottom: 0,
                  width: `${retentionRate}%`,
                  background: 'rgba(74, 222, 128, 0.1)',
                  zIndex: 0,
                  transition: 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)'
                }} />

                <div style={{ zIndex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--color-text-900)' }}>
                    {stageName}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--color-text-500)' }}>
                    Reason: {stage.reason}
                  </div>
                </div>

                <div style={{ zIndex: 1, display: 'flex', alignItems: 'center', gap: '20px' }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '12px', color: 'var(--color-text-400)' }}>Gated Out</div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-error)' }}>
                      -{stage.dropped}
                    </div>
                  </div>
                  
                  <div style={{ textAlign: 'right', minWidth: '80px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--color-text-400)' }}>Survivors</div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-success)' }}>
                      {stage.out} <span style={{ fontWeight: 400, fontSize: '12px', color: 'var(--color-text-500)' }}>({retentionRate}%)</span>
                    </div>
                  </div>
                </div>
              </div>
              
              {idx < attrition.length - 1 && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  color: 'var(--color-border)',
                  fontSize: '14px',
                  margin: '-4px 0'
                }}>
                  ↓
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
