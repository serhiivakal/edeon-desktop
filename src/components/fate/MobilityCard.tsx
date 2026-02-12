import React from 'react';
import { useFateStore, MobilityResult } from '../../store/fateStore';

interface MobilityCardProps {
  smiles: string;
}

export const MobilityCard: React.FC<MobilityCardProps> = ({ smiles }) => {
  const mobility = useFateStore((s) => s.mobility);
  const predictMobility = useFateStore((s) => s.predictMobility);

  const res: MobilityResult | undefined = mobility[smiles];

  React.useEffect(() => {
    if (smiles && !res) {
      predictMobility(smiles).catch(() => {});
    }
  }, [smiles, res, predictMobility]);

  if (!res) {
    return (
      <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '16px' }}>
        <div style={{ fontSize: '12px', color: 'var(--color-text-400)' }}>Calculating systemic mobility...</div>
      </div>
    );
  }

  const classColorMap = {
    phloem: '#10b981',
    ambimobile: '#3b82f6',
    xylem: '#f59e0b',
    immobile: '#6b7280',
  };

  const badgeBg = `${classColorMap[res.class]}18`;
  const badgeBorder = `${classColorMap[res.class]}40`;

  return (
    <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Mechanistic Systemic Mobility (Kleier & Bromilow Ion Trap)
        </div>
        <span
          style={{
            fontSize: '10px',
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: '10px',
            background: res.confidence === 'in_domain' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
            color: res.confidence === 'in_domain' ? '#10b981' : '#f59e0b',
          }}
        >
          {res.confidence.toUpperCase().replace('_', ' ')}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '14px' }}>
        {/* Mobility Class */}
        <div style={{ padding: '10px', borderRadius: '6px', background: badgeBg, border: `0.5px solid ${badgeBorder}` }}>
          <div style={{ fontSize: '10px', fontWeight: 500, color: classColorMap[res.class] }}>Systemic Class</div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: classColorMap[res.class], marginTop: '2px', textTransform: 'capitalize' }}>
            {res.class}
          </div>
        </div>

        {/* Bromilow Phloem CF */}
        <div style={{ padding: '10px', borderRadius: '6px', background: 'var(--color-surface-hover)', border: '0.5px solid var(--color-border)' }}>
          <div style={{ fontSize: '10px', fontWeight: 500, color: 'var(--color-text-500)' }}>Phloem Conc. Factor</div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-text-900)', marginTop: '2px' }}>
            {res.phloem_concentration_factor.toFixed(1)}x
          </div>
        </div>

        {/* Kleier Xylem Index */}
        <div style={{ padding: '10px', borderRadius: '6px', background: 'var(--color-surface-hover)', border: '0.5px solid var(--color-border)' }}>
          <div style={{ fontSize: '10px', fontWeight: 500, color: 'var(--color-text-500)' }}>Kleier Xylem Index</div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-text-900)', marginTop: '4px' }}>
            {res.xylem_index.toFixed(2)}
          </div>
        </div>

        {/* Kleier Phloem Index */}
        <div style={{ padding: '10px', borderRadius: '6px', background: 'var(--color-surface-hover)', border: '0.5px solid var(--color-border)' }}>
          <div style={{ fontSize: '10px', fontWeight: 500, color: 'var(--color-text-500)' }}>Kleier Phloem Index</div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-text-900)', marginTop: '4px' }}>
            {res.phloem_index.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Driver Readout */}
      <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: 'var(--color-text-600)', background: 'rgba(0,0,0,0.02)', padding: '8px 12px', borderRadius: '6px' }}>
        <span>LogKow: <strong>{res.drivers.logkow}</strong></span>
        <span>MW: <strong>{res.drivers.mw} g/mol</strong></span>
        <span>pKa: <strong>{res.drivers.pka ? res.drivers.pka.join(', ') : 'None'}</strong></span>
        <span>Apoplast Charge (pH 5.5): <strong>{res.drivers.dominant_charge_apoplast}</strong></span>
      </div>
    </div>
  );
};
