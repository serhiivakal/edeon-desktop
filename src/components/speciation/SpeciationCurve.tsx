import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { useFateStore, SpeciationCurve as SpeciationCurveType } from '../../store/fateStore';

interface SpeciationCurveProps {
  smiles: string;
}

export const SpeciationCurve: React.FC<SpeciationCurveProps> = ({ smiles }) => {
  const speciationCurves = useFateStore((s) => s.speciationCurves);
  const loadSpeciationCurve = useFateStore((s) => s.loadSpeciationCurve);

  const curveData: SpeciationCurveType | undefined = speciationCurves[smiles];

  React.useEffect(() => {
    if (smiles && !curveData) {
      loadSpeciationCurve(smiles).catch(() => {});
    }
  }, [smiles, curveData, loadSpeciationCurve]);

  if (!curveData || !curveData.series || curveData.series.length === 0) {
    return (
      <div style={{ padding: '16px', fontSize: '12px', color: 'var(--color-text-400)' }}>
        Generating speciation curve...
      </div>
    );
  }

  // Transform series into Recharts data array
  const formattedData = curveData.series.map((item) => {
    const entry: Record<string, any> = { ph: item.ph };
    item.species.forEach((sp, idx) => {
      entry[`species_${idx}`] = Math.round(sp.fraction * 100);
      entry[`label_${idx}`] = sp.smiles;
    });
    return entry;
  });

  const numSpecies = curveData.series[0]?.species?.length || 1;
  const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6'];

  return (
    <div style={{ width: '100%', height: 220, display: 'flex', flexDirection: 'column' }}>
      <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '8px', color: 'var(--color-text-700)' }}>
        pH Speciation Distribution Curve (Henderson–Hasselbalch)
      </div>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={formattedData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="ph" label={{ value: 'Soil pH', position: 'bottom', offset: 0, fontSize: 11 }} />
          <YAxis unit="%" domain={[0, 100]} fontSize={11} />
          <Tooltip
            formatter={(val: any) => [`${val}%`, 'Population']}
            labelFormatter={(label) => `pH ${label}`}
          />
          {Array.from({ length: numSpecies }).map((_, idx) => (
            <Area
              key={idx}
              type="monotone"
              dataKey={`species_${idx}`}
              stackId="1"
              stroke={colors[idx % colors.length]}
              fill={colors[idx % colors.length]}
              fillOpacity={0.6}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};
