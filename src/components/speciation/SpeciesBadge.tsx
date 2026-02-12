import React from 'react';
import { useFateStore, SpeciationResult } from '../../store/fateStore';

interface SpeciesBadgeProps {
  smiles: string;
}

export const SpeciesBadge: React.FC<SpeciesBadgeProps> = ({ smiles }) => {
  const phTarget = useFateStore((s) => s.phTarget);
  const speciation = useFateStore((s) => s.speciation);
  const loadSpeciation = useFateStore((s) => s.loadSpeciation);

  const key = `${smiles}_${phTarget}`;
  const data: SpeciationResult | undefined = speciation[key];

  React.useEffect(() => {
    if (smiles && !data) {
      loadSpeciation(smiles).catch(() => {});
    }
  }, [smiles, phTarget, data, loadSpeciation]);

  if (!data || !data.microspecies || data.microspecies.length === 0) {
    return <span style={{ fontSize: '11px', color: 'var(--color-text-400)' }}>pH {phTarget}: Neutral</span>;
  }

  const dom = data.microspecies.find((m) => m.dominant) || data.microspecies[0];
  const chargeStr = dom.charge > 0 ? `+${dom.charge}` : `${dom.charge}`;
  const pctStr = `${(dom.fraction_at_target * 100).toFixed(0)}%`;

  const badgeBg =
    dom.charge < 0
      ? 'rgba(239, 68, 68, 0.15)'
      : dom.charge > 0
      ? 'rgba(59, 130, 246, 0.15)'
      : 'rgba(107, 114, 128, 0.15)';

  const badgeColor =
    dom.charge < 0
      ? '#ef4444'
      : dom.charge > 0
      ? '#3b82f6'
      : 'var(--color-text-600)';

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '2px 8px',
        borderRadius: '12px',
        background: badgeBg,
        border: `0.5px solid ${badgeColor}`,
        fontSize: '11px',
        fontWeight: 500,
        color: badgeColor,
      }}
      title={`Dominant species at pH ${phTarget}: Charge ${chargeStr} (${pctStr} population)`}
    >
      <span>pH {phTarget}</span>
      <span>•</span>
      <span>Charge {chargeStr} ({pctStr})</span>
    </div>
  );
};
