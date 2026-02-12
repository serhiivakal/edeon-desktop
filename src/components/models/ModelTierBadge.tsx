import { useState } from 'react';

export interface ModelTierBadgeProps {
  tier: 1 | 2 | 3 | 4;
}

export function ModelTierBadge({ tier }: ModelTierBadgeProps) {
  const [hovered, setHovered] = useState(false);

  const getTierInfo = () => {
    switch (tier) {
      case 1:
        return {
          label: 'Reference',
          bg: 'var(--color-brand-100, #eaf3de)',
          color: 'var(--color-brand-700, #2d5016)',
          border: '0.5px solid rgba(45, 80, 22, 0.4)',
          desc: 'High-quality experimental measurements and reference standards.',
        };
      case 2:
        return {
          label: 'Screening',
          bg: 'var(--color-amber-100, #faeeda)',
          color: 'var(--color-amber-700, #854f0b)',
          border: '0.5px solid rgba(133, 79, 11, 0.4)',
          desc: 'Semi-quantitative assays or localized screening studies.',
        };
      case 3:
        return {
          label: 'External',
          bg: 'var(--color-blue-100, #e6f1fb)',
          color: 'var(--color-blue-700, #0c447c)',
          border: '0.5px solid rgba(12, 68, 124, 0.4)',
          desc: 'General third-party external QSAR models and consensus predictions.',
        };
      case 4:
      default:
        return {
          label: 'Custom',
          bg: '#f3e8ff', // premium purple light
          color: '#6b21a8', // deep purple text
          border: '0.5px solid rgba(107, 33, 168, 0.4)',
          desc: 'Custom machine learning model trained locally via QSAR Studio.',
        };
    }
  };

  const info = getTierInfo();

  return (
    <div
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '20px',
          padding: '0 8px',
          borderRadius: '10px',
          fontSize: '9px',
          fontWeight: 600,
          letterSpacing: '0.02em',
          textTransform: 'uppercase',
          background: info.bg,
          color: info.color,
          border: info.border,
          cursor: 'help',
          userSelect: 'none',
          transition: 'all 150ms ease-in-out',
          boxShadow: hovered ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
        }}
      >
        T{tier}: {info.label}
      </span>

      {hovered && (
        <div
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 6px)',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '200px',
            padding: '8px 10px',
            background: '#1e293b', // slate-800 for dark mode look tooltip
            color: '#f8fafc', // slate-50
            fontSize: '10px',
            lineHeight: '1.4',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.12)',
            zIndex: 1000,
            pointerEvents: 'none',
            textAlign: 'center',
            animation: 'fadeInTierBadge 150ms ease-out',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '2px', color: '#ffffff' }}>
            Tier {tier} — {info.label}
          </div>
          {info.desc}
          {/* Tooltip arrow */}
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              borderWidth: '5px',
              borderStyle: 'solid',
              borderColor: '#1e293b transparent transparent transparent',
            }}
          />
        </div>
      )}
      
      {/* Keyframe animation styling */}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes fadeInTierBadge {
          from { opacity: 0; transform: translate(-50%, 4px); }
          to { opacity: 1; transform: translate(-50%, 0); }
        }
      `}} />
    </div>
  );
}
