import { ReactNode } from 'react';

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description: string;
  primaryAction?: { label: string; onClick: () => void };
  secondaryAction?: { label: string; onClick: () => void };
}

export function EmptyState({
  icon,
  title,
  description,
  primaryAction,
  secondaryAction,
}: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '32px 24px',
        background: 'var(--color-surface, #ffffff)',
        border: '1px dashed var(--color-border-default, #d4d4d8)',
        borderRadius: '8px',
        maxWidth: '420px',
        margin: '24px auto',
        boxShadow: 'var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))',
      }}
    >
      {icon && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            background: 'var(--color-action-secondary, #f4f4f5)',
            color: 'var(--color-brand-700, #3b6d11)',
            marginBottom: '16px',
            fontSize: '20px',
          }}
        >
          {icon}
        </div>
      )}

      <h3
        style={{
          fontSize: '14px',
          fontWeight: 650,
          color: 'var(--color-text-primary, #18181b)',
          margin: '0 0 6px 0',
        }}
      >
        {title}
      </h3>

      <p
        style={{
          fontSize: '12px',
          color: 'var(--color-text-secondary, #52525b)',
          margin: '0 0 20px 0',
          lineHeight: '1.5',
        }}
      >
        {description}
      </p>

      {(primaryAction || secondaryAction) && (
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', justifyContent: 'center', flexWrap: 'wrap' }}>
          {secondaryAction && (
            <button
              onClick={secondaryAction.onClick}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                border: '1px solid var(--color-border-default, #d4d4d8)',
                background: 'var(--color-surface, #ffffff)',
                color: 'var(--color-text-secondary, #52525b)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 120ms ease',
                outline: 'none',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--color-action-secondary, #f4f4f5)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'var(--color-surface, #ffffff)';
              }}
            >
              {secondaryAction.label}
            </button>
          )}
          
          {primaryAction && (
            <button
              onClick={primaryAction.onClick}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                border: 'none',
                background: 'var(--color-brand-700, #3b6d11)',
                color: 'var(--color-text-inverse, #ffffff)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 120ms ease',
                outline: 'none',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--color-brand-800, #2d5016)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'var(--color-brand-700, #3b6d11)';
              }}
            >
              {primaryAction.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
