import { useState } from 'react';
import { HelpCircle, ExternalLink } from 'lucide-react';
import helpContent from '../../content/help/help_content.json';

export interface ContextualHelpProps {
  topicId: string;
  position?: 'top' | 'right' | 'bottom' | 'left';
}

export function ContextualHelp({ topicId, position = 'top' }: ContextualHelpProps) {
  const [hovered, setHovered] = useState(false);
  const data = (helpContent as Record<string, { title: string; body: string; learn_more?: string }>)[topicId];

  if (!data) return null;

  const getPositionStyles = (): React.CSSProperties => {
    switch (position) {
      case 'left':
        return {
          right: 'calc(100% + 6px)',
          top: '50%',
          transform: 'translateY(-50%)',
        };
      case 'right':
        return {
          left: 'calc(100% + 6px)',
          top: '50%',
          transform: 'translateY(-50%)',
        };
      case 'bottom':
        return {
          top: 'calc(100% + 6px)',
          left: '50%',
          transform: 'translateX(-50%)',
        };
      case 'top':
      default:
        return {
          bottom: 'calc(100% + 6px)',
          left: '50%',
          transform: 'translateX(-50%)',
        };
    }
  };

  const getArrowStyles = (): React.CSSProperties => {
    switch (position) {
      case 'left':
        return {
          left: '100%',
          top: '50%',
          transform: 'translateY(-50%)',
          borderColor: 'transparent transparent transparent #18181b',
        };
      case 'right':
        return {
          right: '100%',
          top: '50%',
          transform: 'translateY(-50%)',
          borderColor: 'transparent #18181b transparent transparent',
        };
      case 'bottom':
        return {
          bottom: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          borderColor: 'transparent transparent #18181b transparent',
        };
      case 'top':
      default:
        return {
          top: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          borderColor: '#18181b transparent transparent transparent',
        };
    }
  };

  return (
    <div
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        cursor: 'help',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <HelpCircle
        size={11}
        style={{
          color: hovered ? 'var(--color-brand-700, #3b6d11)' : 'var(--color-text-tertiary, #a1a1aa)',
          transition: 'color 120ms ease',
          marginLeft: '4px',
          verticalAlign: 'middle',
        }}
      />

      {hovered && (
        <div
          style={{
            position: 'absolute',
            width: '220px',
            padding: '10px 12px',
            background: '#18181b', // Slate-900 surface overlay
            border: '0.5px solid #3f3f46',
            color: '#e4e4e7', // zinc-200
            fontSize: '10px',
            lineHeight: '1.4',
            borderRadius: '8px',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -4px rgba(0, 0, 0, 0.3)',
            zIndex: 1100,
            pointerEvents: 'none',
            textAlign: 'left',
            ...getPositionStyles(),
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '4px', color: '#ffffff' }}>
            {data.title}
          </div>
          <div style={{ color: '#d4d4d8' }}>{data.body}</div>
          {data.learn_more && (
            <div style={{ marginTop: '6px', borderTop: '0.5px solid rgba(255,255,255,0.1)', paddingTop: '4px', display: 'flex', alignItems: 'center', gap: '3px', color: '#60a5fa', fontWeight: 500 }}>
              <ExternalLink size={8} /> Learn more: {data.learn_more.split('/').pop()}
            </div>
          )}

          {/* Tooltip arrow */}
          <div
            style={{
              position: 'absolute',
              borderWidth: '5px',
              borderStyle: 'solid',
              ...getArrowStyles(),
            }}
          />
        </div>
      )}
    </div>
  );
}
