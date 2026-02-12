import React from 'react';
import { useRetroStore } from '../../store/retroStore';

interface FeasibilityBadgeProps {
  smiles: string;
}

export const FeasibilityBadge: React.FC<FeasibilityBadgeProps> = ({ smiles }) => {
  const saScores = useRetroStore((s) => s.saScores);
  const gating = useRetroStore((s) => s.gating);
  const getSaScore = useRetroStore((s) => s.getSaScore);

  const gateData = gating[smiles];
  const score = gateData ? gateData.feasibility_score : saScores[smiles];
  const tier = gateData ? gateData.tier : (score >= 0.7 ? 'green' : score >= 0.45 ? 'amber' : 'red');

  React.useEffect(() => {
    if (smiles && score === undefined) {
      getSaScore(smiles).catch(() => {});
    }
  }, [smiles, score, getSaScore]);

  if (score === undefined) {
    return <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>SA...</span>;
  }

  const tierColors = {
    green: { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981', border: 'rgba(16, 185, 129, 0.4)' },
    amber: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.4)' },
    red: { bg: 'rgba(239, 68, 68, 0.15)', text: '#ef4444', border: 'rgba(239, 68, 68, 0.4)' },
  };

  const currentStyle = tierColors[tier] || tierColors.amber;

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 7px',
        borderRadius: '10px',
        background: currentStyle.bg,
        border: `0.5px solid ${currentStyle.border}`,
        fontSize: '11px',
        fontWeight: 600,
        color: currentStyle.text,
      }}
      title={`Makeability Score: ${(score * 100).toFixed(0)}% (${tier.toUpperCase()})`}
    >
      <span>Makeability</span>
      <span>{(score * 100).toFixed(0)}%</span>
    </div>
  );
};
