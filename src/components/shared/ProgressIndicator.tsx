import { X } from 'lucide-react';

export interface ProgressIndicatorProps {
  variant: 'determinate' | 'indeterminate';
  value?: number; // 0-100 for determinate
  label?: string; // e.g., "Docking pose 3 of 9"
  estimated_remaining_sec?: number;
  elapsed_sec?: number;
  cancelable?: boolean;
  onCancel?: () => void;
  size?: 'sm' | 'md' | 'lg';
}

export function ProgressIndicator({
  variant,
  value = 0,
  label,
  estimated_remaining_sec,
  elapsed_sec,
  cancelable = false,
  onCancel,
  size = 'md',
}: ProgressIndicatorProps) {
  const formatTime = (sec?: number) => {
    if (sec === undefined || sec === null || sec < 0) return null;
    if (sec < 60) return `${Math.round(sec)}s`;
    const mins = Math.floor(sec / 60);
    const remaining = Math.round(sec % 60);
    return `${mins}m ${remaining}s`;
  };

  const getBarHeight = () => {
    switch (size) {
      case 'sm':
        return '4px';
      case 'lg':
        return '10px';
      case 'md':
      default:
        return '6px';
    }
  };

  const cleanPercent = Math.min(100, Math.max(0, value));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', width: '100%', margin: '8px 0' }}>
      {/* Top Labels */}
      {(label || cancelable) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
          {label && (
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-secondary, #52525b)' }}>
              {label}
            </span>
          )}
          
          {cancelable && onCancel && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onCancel();
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                background: 'none',
                border: 'none',
                color: 'var(--color-status-poor, #dc2626)',
                fontSize: '10px',
                fontWeight: 600,
                cursor: 'pointer',
                padding: '2px 4px',
                borderRadius: '4px',
                transition: 'background 120ms ease',
                outline: 'none',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-status-poor-bg, #fef2f2)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <X size={10} />
              Cancel
            </button>
          )}
        </div>
      )}

      {/* Progress Track */}
      <div
        style={{
          width: '100%',
          height: getBarHeight(),
          background: 'var(--color-border-subtle, #f0f0eb)',
          borderRadius: '9999px',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {variant === 'determinate' ? (
          <div
            style={{
              height: '100%',
              width: `${cleanPercent}%`,
              background: 'var(--color-brand-700, #3b6d11)',
              borderRadius: '9999px',
              transition: 'width 200ms ease-out',
            }}
          />
        ) : (
          <div
            style={{
              height: '100%',
              width: '40%',
              background: 'var(--color-brand-700, #3b6d11)',
              borderRadius: '9999px',
              position: 'absolute',
              top: 0,
              animation: 'progressIndeterminateScan 1.6s infinite linear',
            }}
          />
        )}
      </div>

      {/* Bottom Stats (ETA, Elapsed) */}
      {(elapsed_sec !== undefined || estimated_remaining_sec !== undefined || (variant === 'determinate' && cleanPercent > 0)) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9.5px', color: 'var(--color-text-tertiary, #a1a1aa)', fontWeight: 500 }}>
          <div>
            {variant === 'determinate' && <span>{Math.round(cleanPercent)}% complete</span>}
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {elapsed_sec !== undefined && (
              <span>Elapsed: {formatTime(elapsed_sec)}</span>
            )}
            {estimated_remaining_sec !== undefined && estimated_remaining_sec > 0 && (
              <span>ETA: {formatTime(estimated_remaining_sec)}</span>
            )}
          </div>
        </div>
      )}

      {/* Indeterminate keyframe scan style */}
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes progressIndeterminateScan {
          0% { left: -40%; }
          100% { left: 100%; }
        }
      ` }} />
    </div>
  );
}
