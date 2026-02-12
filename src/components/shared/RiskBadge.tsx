import type { RiskLevel } from '../../types';

interface RiskBadgeProps {
  level: RiskLevel;
  /** Use 'good' context when High means positive (e.g., pesticide-likeness) */
  context?: 'risk' | 'good';
}

export function RiskBadge({ level, context = 'risk' }: RiskBadgeProps) {
  let className = 'risk-badge ';

  if (level === 'Low') {
    className += context === 'risk' ? 'low' : 'low';
  } else if (level === 'Med') {
    className += 'medium';
  } else if (level === 'High') {
    className += context === 'good' ? 'high-good' : 'high';
  }

  return <span className={className}>{level}</span>;
}
