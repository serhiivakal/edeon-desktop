interface VerdictHeaderProps {
  verdict: {
    band: 'GO' | 'CONDITIONAL' | 'NO_GO' | string;
    driver: string;
    confidence: 'high' | 'moderate' | 'low' | string;
    rationale: string;
  };
  warnings?: string[];
}

export function VerdictHeader({ verdict, warnings = [] }: VerdictHeaderProps) {

  // Tailored color maps
  const colorMap = {
    GO: {
      bg: 'var(--color-brand-100)',
      border: 'var(--color-brand-50)',
      text: 'var(--color-brand-900)',
      pillBg: 'var(--color-brand-700)',
      pillText: '#ffffff',
      icon: '✓',
      label: 'Recommended GO'
    },
    CONDITIONAL: {
      bg: 'var(--color-amber-100)',
      border: 'var(--color-amber-50)',
      text: 'var(--color-amber-700)',
      pillBg: 'var(--color-amber-50)',
      pillText: 'var(--color-amber-700)',
      icon: '⚠',
      label: 'CONDITIONAL / WATCH'
    },
    NO_GO: {
      bg: 'var(--color-red-100)',
      border: 'var(--color-red-50)',
      text: 'var(--color-red-700)',
      pillBg: 'var(--color-red-500)',
      pillText: '#ffffff',
      icon: '✕',
      label: 'NO-GO (Showstopper Triggered)'
    }
  };

  const currentTheme = colorMap[verdict.band as keyof typeof colorMap] || colorMap.CONDITIONAL;

  return (
    <div
      style={{
        background: currentTheme.bg,
        border: `1px solid ${currentTheme.border}`,
        borderRadius: '8px',
        padding: '24px',
        marginBottom: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        boxShadow: 'var(--shadow-sm)',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              backgroundColor: currentTheme.pillBg,
              color: currentTheme.pillText,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '22px',
              fontWeight: 'bold',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }}
          >
            {currentTheme.icon}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
              <span style={{ fontSize: '20px', fontWeight: 700, color: currentTheme.text }}>
                {currentTheme.label}
              </span>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  padding: '2px 8px',
                  borderRadius: '12px',
                  backgroundColor: verdict.confidence === 'high' ? 'rgba(45, 80, 22, 0.15)' : 'rgba(0,0,0,0.05)',
                  color: currentTheme.text,
                  border: `1px solid ${currentTheme.border}`
                }}
              >
                {verdict.confidence} confidence
              </span>
            </div>
            <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--color-text-600)' }}>
              Driver: <strong style={{ color: currentTheme.text }}>{verdict.driver}</strong>
            </div>
          </div>
        </div>
      </div>

      <div style={{ borderTop: `1px solid ${currentTheme.border}`, paddingTop: '16px' }}>
        <h4 style={{ margin: '0 0 6px 0', fontSize: '13px', fontWeight: 600, color: currentTheme.text, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Decision Rationale
        </h4>
        <p style={{ margin: 0, fontSize: '14px', lineHeight: 1.5, color: 'var(--color-text-900)' }}>
          {verdict.rationale}
        </p>
      </div>

      {warnings.length > 0 && (
        <div style={{ marginTop: '8px', padding: '12px 16px', background: 'rgba(255,255,255,0.6)', border: '1px dashed var(--color-border)', borderRadius: '6px' }}>
          <h5 style={{ margin: '0 0 6px 0', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-600)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>⚠️</span> Data Gaps & Warnings ({warnings.length})
          </h5>
          <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '12px', color: 'var(--color-text-600)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
