import { useState } from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  HelpCircle 
} from 'lucide-react';

export interface ADWarningProps {
  status: 'in' | 'borderline' | 'out' | 'unknown';
  score?: number;
}

export function ADWarning({ status, score }: ADWarningProps) {
  const [hovered, setHovered] = useState(false);

  const getStatusInfo = () => {
    switch (status) {
      case 'in':
        return {
          label: 'In domain',
          bg: 'var(--color-brand-100, #eaf3de)',
          color: 'var(--color-brand-700, #2d5016)',
          border: '0.5px solid rgba(45, 80, 22, 0.4)',
          icon: <CheckCircle2 size={12} style={{ marginRight: '4px', flexShrink: 0 }} />,
          desc: 'Compound falls fully inside the model\'s Applicability Domain (high reliability).',
        };
      case 'borderline':
        return {
          label: 'Borderline',
          bg: 'var(--color-amber-100, #faeeda)',
          color: 'var(--color-amber-700, #854f0b)',
          border: '0.5px solid rgba(133, 79, 11, 0.4)',
          icon: <AlertTriangle size={12} style={{ marginRight: '4px', flexShrink: 0 }} />,
          desc: 'Compound is near the model boundary limit. Prediction carries moderate uncertainty.',
        };
      case 'out':
        return {
          label: 'Out of domain',
          bg: 'var(--color-red-100, #fceae5)',
          color: 'var(--color-red-700, #993c1d)',
          border: '0.5px solid rgba(153, 60, 29, 0.4)',
          icon: <XCircle size={12} style={{ marginRight: '4px', flexShrink: 0 }} />,
          desc: 'Compound is structurally dissimilar from the training dataset. Prediction is unreliable.',
        };
      case 'unknown':
      default:
        return {
          label: 'AD unknown',
          bg: 'var(--color-bg, #f5f5f0)',
          color: 'var(--color-text-600, #5a5a5a)',
          border: '0.5px solid var(--color-border, #e5e5e0)',
          icon: <HelpCircle size={12} style={{ marginRight: '4px', flexShrink: 0 }} />,
          desc: 'Applicability Domain coordinates or structural training baselines are unavailable.',
        };
    }
  };

  const info = getStatusInfo();

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
          height: '20px',
          padding: '0 8px',
          borderRadius: '10px',
          fontSize: '9px',
          fontWeight: 600,
          background: info.bg,
          color: info.color,
          border: info.border,
          cursor: 'help',
          userSelect: 'none',
          transition: 'all 150ms ease-in-out',
          boxShadow: hovered ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
        }}
      >
        {info.icon}
        {info.label}
      </span>

      {hovered && (
        <div
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 6px)',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '210px',
            padding: '8px 10px',
            background: '#1e293b', // premium slate-800 for dark mode look tooltip
            color: '#f8fafc', // slate-50
            fontSize: '10px',
            lineHeight: '1.4',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.12)',
            zIndex: 1000,
            pointerEvents: 'none',
            textAlign: 'center',
            animation: 'fadeInADWarning 150ms ease-out',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '2px', color: '#ffffff' }}>
            Applicability Domain
          </div>
          <div style={{ marginBottom: '4px' }}>{info.desc}</div>
          {score !== undefined && (
            <div style={{ 
              marginTop: '4px', 
              paddingTop: '4px', 
              borderTop: '0.5px solid rgba(255,255,255,0.15)', 
              fontSize: '9px',
              color: '#94a3b8',
              fontFamily: 'var(--font-mono, monospace)'
            }}>
              AD Score: {score.toFixed(3)}
            </div>
          )}
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
        @keyframes fadeInADWarning {
          from { opacity: 0; transform: translate(-50%, 4px); }
          to { opacity: 1; transform: translate(-50%, 0); }
        }
      `}} />
    </div>
  );
}
