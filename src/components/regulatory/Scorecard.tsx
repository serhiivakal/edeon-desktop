import { useEffect, useState } from 'react';
import { useRegulatoryStore, type CriterionResult, type OverallRisk, type RiskStatus } from '../../store/regulatoryStore';

// ─── Status Configuration ────────────────────────────────────────────────────

const STATUS_CONFIG: Record<RiskStatus, { label: string; color: string; bg: string; icon: string }> = {
  pass: {
    label: 'Pass',
    color: 'var(--color-brand-700, #047857)',
    bg: 'rgba(16, 185, 129, 0.08)',
    icon: '✓',
  },
  watch: {
    label: 'Watch',
    color: 'var(--color-amber-700, #b45309)',
    bg: 'rgba(245, 158, 11, 0.08)',
    icon: '⚠',
  },
  likely_showstopper: {
    label: 'Showstopper',
    color: 'var(--color-red-700, #b91c1c)',
    bg: 'rgba(239, 68, 68, 0.08)',
    icon: '✕',
  },
};

// ─── Overall Risk Badge ──────────────────────────────────────────────────────

function OverallBadge({ risk }: { risk: OverallRisk }) {
  const config: Record<OverallRisk, { label: string; color: string; bg: string }> = {
    low: { label: 'Low Risk', color: 'var(--color-brand-700, #047857)', bg: 'rgba(16, 185, 129, 0.1)' },
    medium: { label: 'Medium Risk', color: 'var(--color-amber-700, #b45309)', bg: 'rgba(245, 158, 11, 0.1)' },
    high: { label: 'High Risk', color: 'var(--color-red-700, #b91c1c)', bg: 'rgba(239, 68, 68, 0.1)' },
    showstopper: { label: 'Showstopper', color: '#7f1d1d', bg: 'rgba(127, 29, 29, 0.12)' },
  };

  const c = config[risk] || config.medium;

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      padding: '6px 14px',
      borderRadius: '6px',
      background: c.bg,
      border: `0.5px solid ${c.color}22`,
    }}>
      <span style={{ fontSize: '14px', fontWeight: 700, color: c.color }}>{c.label}</span>
    </div>
  );
}

// ─── Criterion Row ───────────────────────────────────────────────────────────

function CriterionRow({ criterion }: { criterion: CriterionResult }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = STATUS_CONFIG[criterion.status] || STATUS_CONFIG.watch;

  return (
    <div style={{
      padding: '8px 10px',
      borderRadius: '6px',
      marginBottom: '6px',
      background: cfg.bg,
      border: `0.5px solid ${cfg.color}22`,
      cursor: 'pointer',
      transition: 'all 0.15s ease',
    }}
      onClick={() => setExpanded(!expanded)}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: cfg.color }}>{cfg.icon}</span>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-primary, #1f2937)' }}>
            {criterion.criterion}
          </span>
        </div>
        <span style={{
          fontSize: '10px',
          fontWeight: 600,
          color: cfg.color,
          padding: '2px 6px',
          borderRadius: '4px',
          background: `${cfg.color}11`,
        }}>
          {cfg.label}
        </span>
      </div>

      {expanded && (
        <div style={{ marginTop: '6px', paddingLeft: '4px' }}>
          {criterion.evidence.map((ev: string, i: number) => (
            <div
              key={i}
              style={{
                fontSize: '11px',
                color: 'var(--color-text-secondary, #6b7280)',
                marginBottom: '2px',
                lineHeight: '1.4',
              }}
            >
              &bull; {ev}
            </div>
          ))}
          {criterion.verdict && (
            <div style={{ fontSize: '11px', fontWeight: 600, color: cfg.color, marginTop: '4px' }}>
              Verdict: {criterion.verdict}
            </div>
          )}
          <div style={{ fontSize: '10px', color: 'var(--color-text-tertiary, #9ca3af)', marginTop: '4px', fontStyle: 'italic' }}>
            Ref: {criterion.source_ref}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Scorecard Component ────────────────────────────────────────────────

interface ScorecardProps {
  smiles?: string;
  /** If true, auto-fetch when smiles changes */
  autoFetch?: boolean;
  /** Compact mode for embedding in other views */
  compact?: boolean;
}

export function Scorecard({ smiles, autoFetch = true, compact = false }: ScorecardProps) {
  const assessRisk = useRegulatoryStore((s) => s.assessRisk);
  const cache = useRegulatoryStore((s) => s.cache);
  const isLoading = useRegulatoryStore((s) => s.isLoading);
  const error = useRegulatoryStore((s) => s.error);

  useEffect(() => {
    if (autoFetch && smiles && !cache[smiles]) {
      assessRisk(smiles).catch(console.error);
    }
  }, [smiles, autoFetch, assessRisk, cache]);

  if (!smiles) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-tertiary, #9ca3af)', fontSize: '13px' }}>
        Select a compound to view registration risk assessment.
      </div>
    );
  }

  if (isLoading && !cache[smiles]) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-secondary, #6b7280)', fontSize: '13px' }}>
        Assessing registration risk...
      </div>
    );
  }

  if (error && !cache[smiles]) {
    return (
      <div style={{ padding: '16px', background: 'rgba(239,68,68,0.06)', borderRadius: '6px', color: 'var(--color-red-700, #b91c1c)', fontSize: '12px' }}>
        Error: {error}
      </div>
    );
  }

  const result = cache[smiles];
  if (!result) return null;

  const { criteria, overall, disclaimer } = result;

  return (
    <div style={{ padding: compact ? '12px' : '16px' }}>
      {/* Disclaimer banner */}
      <div
        style={{
          padding: '10px 12px',
          borderRadius: '6px',
          background: 'rgba(59, 130, 246, 0.06)',
          border: '0.5px solid rgba(59, 130, 246, 0.2)',
          marginBottom: '16px',
          fontSize: '11px',
          color: 'var(--color-text-secondary, #6b7280)',
          lineHeight: '1.5',
        }}
      >
        {disclaimer || 'In-silico screening signal only \u2014 not a regulatory determination.'}
      </div>

      {/* Overall Risk Badge */}
      <div style={{ marginBottom: '12px' }}>
        <OverallBadge risk={overall.risk} />
        <div style={{ display: 'flex', gap: '12px', marginTop: '6px', fontSize: '11px', color: 'var(--color-text-secondary, #6b7280)' }}>
          <span>&#10003; {overall.pass_count} pass</span>
          <span>&#9888; {overall.watch_count} watch</span>
          <span>&#10005; {overall.showstopper_count} showstopper</span>
        </div>
      </div>

      {/* Criteria List */}
      <div>
        {criteria.map((c: CriterionResult, i: number) => (
          <CriterionRow key={i} criterion={c} />
        ))}
      </div>
    </div>
  );
}

/**
 * Compact inline badge for use in tables/lists.
 */
export function RegRiskBadge({ smiles }: { smiles: string }) {
  const cache = useRegulatoryStore((s) => s.cache);
  const result = cache[smiles];

  if (!result) return null;

  const riskColors: Record<string, string> = {
    low: 'var(--color-brand-600, #059669)',
    medium: 'var(--color-amber-600, #d97706)',
    high: 'var(--color-red-600, #dc2626)',
    showstopper: '#7f1d1d',
  };

  const color = riskColors[result.overall.risk] || riskColors.medium;

  return (
    <span style={{
      fontSize: '10px',
      fontWeight: 700,
      color,
      padding: '1px 5px',
      borderRadius: '3px',
      background: `${color}11`,
      border: `0.5px solid ${color}33`,
      textTransform: 'uppercase',
    }}>
      {result.overall.risk}
    </span>
  );
}
