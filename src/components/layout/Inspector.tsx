import { useEffect, useState, useRef } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useUIStore } from '../../store/uiStore';
import { useCompoundStore } from '../../store/compoundStore';
import { useWorkflowStore } from '../../store/workflowStore';
import { useModelStore } from '../../store/modelStore';
import { useKnowledgeStore } from '../../store/knowledgeStore';
import type { WorkflowResultRecord, Prediction } from '../../types';
import { PredictionDisplay } from '../models/PredictionDisplay';
import { ModelCardViewer } from '../models/ModelCardViewer';
import { CompoundDetailModal } from '../workflow/CompoundDetailModal';
import { CompoundCompareModal } from '../workflow/CompoundCompareModal';
import { UqBadge } from '../uq/UqBadge';
import { IntervalBar } from '../uq/IntervalBar';
import { BioisostereCarousel } from '../bioisostere/BioisostereCarousel';
import { EmptyState } from '../shared/EmptyState';
import { ContextualHelp } from '../shared/ContextualHelp';


/** Hook to fetch 2D SVG — uses MCS highlighting when MCS is active. Gracefully falls back to standard depiction if MCS fails. */
function useStructureSvg(smiles: string | undefined) {
  const [svg, setSvg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mcsActive = useUIStore((s) => s.mcsActive);
  const mcsSmarts = useUIStore((s) => s.mcsSmarts);

  useEffect(() => {
    if (!smiles) { setSvg(null); setError(null); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);

    const tryDepict = async () => {
      try {
        if (mcsActive && mcsSmarts) {
          try {
            const res = await invoke<string>('depict_mcs', { smiles, mcsSmarts });
            if (!cancelled) {
              setSvg(res);
              setError(null);
            }
            return;
          } catch (err) {
            console.warn('[useStructureSvg] MCS depiction failed, falling back to standard depiction:', err);
          }
        }
        const res = await invoke<string>('depict_compound', { smiles });
        if (!cancelled) {
          setSvg(res);
          setError(null);
        }
      } catch (err) {
        console.error('[useStructureSvg] Depiction failed:', err);
        if (!cancelled) {
          setSvg(null);
          setError(String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    tryDepict();

    return () => { cancelled = true; };
  }, [smiles, mcsActive, mcsSmarts]);

  return { svg, loading, error };
}

/** Render an SVG string safely into a container. */
function StructureView({ svg, loading, error }: { svg: string | null; loading: boolean; error: string | null }) {
  if (loading) {
    return (
      <div className="inspector-structure">
        <div className="inspector-structure-placeholder">
          <span className="inspector-structure-loading">Rendering...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="inspector-structure">
        <div className="inspector-structure-placeholder" style={{ padding: '8px', textAlign: 'center', color: 'var(--color-red-600)' }}>
          <span style={{ fontWeight: 600, display: 'block', marginBottom: '2px' }}>Depiction Failed</span>
          <span style={{ fontSize: '9px', opacity: 0.8, display: 'block', wordBreak: 'break-all', maxHeight: '40px', overflowY: 'auto' }}>{error}</span>
        </div>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="inspector-structure">
        <div className="inspector-structure-placeholder">
          <span>2D structure unavailable</span>
        </div>
      </div>
    );
  }

  // Preprocess root SVG tag to replace fixed width and height with 100%
  // so that the vector graphics scale fluidly and perfectly inside the flexbox card.
  let cleanedSvg = svg;
  const svgTagEnd = cleanedSvg.indexOf('>');
  if (svgTagEnd !== -1) {
    let svgTag = cleanedSvg.substring(0, svgTagEnd + 1);
    const rest = cleanedSvg.substring(svgTagEnd + 1);
    svgTag = svgTag.replace(/width=['"][^'"]*['"]/, 'width="100%"');
    svgTag = svgTag.replace(/height=['"][^'"]*['"]/, 'height="100%"');
    cleanedSvg = svgTag + rest;
  }

  return (
    <div
      className="inspector-structure inspector-structure-svg"
      dangerouslySetInnerHTML={{ __html: cleanedSvg }}
    />
  );
}

interface SystemicMobilityResult {
  foliar: number;
  xylem: number;
  phloem: number;
  category: 'Full Systemic' | 'Xylem-Mobile' | 'Phloem-Mobile' | 'Contact-Only';
  foliarRating: 'High' | 'Moderate' | 'Low';
  xylemRating: 'High' | 'Moderate' | 'Low';
  phloemRating: 'High' | 'Moderate' | 'Low';
}

function calculateSystemicMobility(
  logp: number | null | undefined,
  mw: number | null | undefined,
  tpsa: number | null | undefined
): SystemicMobilityResult | null {
  if (logp === null || logp === undefined || mw === null || mw === undefined || tpsa === null || tpsa === undefined) {
    return null;
  }

  // 1. Leaf Absorption (Foliar Penetration)
  const foliar = Math.exp(-Math.pow(logp - 2.5, 2) / 6.0) * (1.0 - Math.min(0.8, mw / 700.0));

  // 2. Root Uptake & Xylem Translocation (Briggs TSCF model)
  const xylem = 0.784 * Math.exp(-Math.pow(logp - 1.78, 2) / 2.44) + 0.006;

  // 3. Phloem Systemic Mobility (Kleier PMF bivariate model approximation)
  const phloem = Math.exp(-Math.pow(logp - 1.0, 2) / 3.0) * Math.exp(-Math.pow(tpsa - 80, 2) / 4000.0);

  const foliarRating = foliar >= 0.6 ? 'High' : foliar >= 0.3 ? 'Moderate' : 'Low';
  const xylemRating = xylem >= 0.4 ? 'High' : xylem >= 0.15 ? 'Moderate' : 'Low';
  const phloemRating = phloem >= 0.5 ? 'High' : phloem >= 0.2 ? 'Moderate' : 'Low';

  let category: 'Full Systemic' | 'Xylem-Mobile' | 'Phloem-Mobile' | 'Contact-Only';
  if (xylem >= 0.15 && phloem >= 0.2) {
    category = 'Full Systemic';
  } else if (xylem >= 0.15) {
    category = 'Xylem-Mobile';
  } else if (phloem >= 0.2) {
    category = 'Phloem-Mobile';
  } else {
    category = 'Contact-Only';
  }

  return {
    foliar,
    xylem,
    phloem,
    category,
    foliarRating,
    xylemRating,
    phloemRating,
  };
}

/* ── Bioisostere Scaffold-Hopping Suggestions Engine ───────────────────────── */


interface SystemicPredictorViewProps {
  compound: {
    mol_weight?: number | null;
    logp?: number | null;
    tpsa?: number | null;
  } | null;
  expanded: boolean;
  onToggle: () => void;
}

function SystemicPredictorView({ compound, expanded, onToggle }: SystemicPredictorViewProps) {
  if (!compound) return null;
  
  const mobility = calculateSystemicMobility(compound.logp, compound.mol_weight, compound.tpsa);
  if (!mobility) return null;

  const { foliar, xylem, phloem, category, foliarRating, xylemRating, phloemRating } = mobility;

  let categoryClass = 'contact-only';
  let categoryDescription = '';
  let arrowChar = '';

  switch (category) {
    case 'Full Systemic':
      categoryClass = 'full-systemic';
      categoryDescription = 'Highly mobile compound showing active xylem (upward) and symplastic phloem (downward) translocation.';
      arrowChar = '↕';
      break;
    case 'Xylem-Mobile':
      categoryClass = 'xylem-mobile';
      categoryDescription = 'Primarily translocated upwards via xylem transpiration stream. Excellent for systemic root-to-shoot delivery.';
      arrowChar = '↑';
      break;
    case 'Phloem-Mobile':
      categoryClass = 'phloem-mobile';
      categoryDescription = 'Translocated downwards via symplastic phloem paths. Ideal for targeting root pests from foliar application.';
      arrowChar = '↓';
      break;
    case 'Contact-Only':
      categoryClass = 'contact-only';
      categoryDescription = 'Non-systemic contact compound. Remains on the outer cuticle surface providing a protective shield.';
      arrowChar = '⛨';
      break;
  }

  return (
    <div className="collapsible-section">
      <div className="section-label collapsible-header" onClick={onToggle}>
        <span>PLANT SYSTEMIC MOBILITY</span>
        <span className="chevron">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="systemic-card">
          <div className="plant-diagram-wrapper">
            <div className={`plant-diagram ${categoryClass}`}>
              <div className="plant-shoot" title="Leaves and Shoots">🌿</div>
              <div className="plant-stem">
                {category !== 'Contact-Only' && (
                  <>
                    <span className="flow-arrow arrow-1">{arrowChar}</span>
                    <span className="flow-arrow arrow-2">{arrowChar}</span>
                  </>
                )}
              </div>
              <div className="plant-roots" title="Roots">🌱</div>
              {category === 'Contact-Only' && (
                <div className="plant-shield" title="Contact Protective Shield">⛨</div>
              )}
            </div>
          </div>
          <div className="systemic-details">
            <div className={`systemic-badge badge-${categoryClass}`}>{category}</div>
            <p className="systemic-description">{categoryDescription}</p>
            
            <div className="systemic-ratings">
              <div className="systemic-rating-row">
                <span className="rating-label">Foliar Absorption</span>
                <span className={`rating-value val-${foliarRating.toLowerCase()}`}>{foliarRating} ({foliar.toFixed(2)})</span>
              </div>
              <div className="systemic-rating-row">
                <span className="rating-label">Xylem TSCF (Upward)</span>
                <span className={`rating-value val-${xylemRating.toLowerCase()}`}>{xylemRating} ({xylem.toFixed(2)})</span>
              </div>
              <div className="systemic-rating-row">
                <span className="rating-label">Phloem PMF (Downward)</span>
                <span className={`rating-value val-${phloemRating.toLowerCase()}`}>{phloemRating} ({phloem.toFixed(2)})</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface EnvironmentalFateResult {
  koc: number;
  dt50: number;
  gus: number;
  category: 'Leacher' | 'Transition' | 'Non-leacher';
}

function calculateEnvironmentalFate(
  logp: number | null | undefined,
  mw: number | null | undefined,
  tpsa: number | null | undefined
): EnvironmentalFateResult | null {
  if (logp === null || logp === undefined || mw === null || mw === undefined || tpsa === null || tpsa === undefined) {
    return null;
  }

  // 1. Organic Carbon Partition Coefficient (Koc)
  // Log Koc = 0.47 * LogP + 1.09 (EU TGD model)
  const logKoc = Math.max(0.0, Math.min(6.0, 0.47 * logp + 1.09));
  const koc = Math.pow(10, logKoc);

  // 2. Soil Half-Life (DT50) QSAR
  // Bioavailability factors based on Lipophilicity, Size, and Polar Surface Area
  const factorLogP = 1.0 + 0.3 * Math.max(0.0, logp);
  const factorMW = 1.0 + 0.2 * (Math.max(0.0, mw - 200.0) / 100.0);
  const factorTPSA = Math.exp(-tpsa / 150.0);
  
  const dt50 = Math.max(2.0, Math.min(365.0, 20.0 * factorLogP * factorMW * factorTPSA));

  // 3. Groundwater Ubiquity Score (GUS)
  // GUS = log10(DT50) * (4.0 - log10(Koc))
  const gus = Math.max(0.0, Math.log10(dt50) * (4.0 - logKoc));

  let category: 'Leacher' | 'Transition' | 'Non-leacher';
  if (gus > 2.8) {
    category = 'Leacher';
  } else if (gus >= 1.8) {
    category = 'Transition';
  } else {
    category = 'Non-leacher';
  }

  return {
    koc,
    dt50,
    gus,
    category,
  };
}

interface EnvironmentalFateViewProps {
  compound: {
    mol_weight?: number | null;
    logp?: number | null;
    tpsa?: number | null;
  } | null;
  expanded: boolean;
  onToggle: () => void;
  predictions: Record<string, Prediction | null>;
  onViewCard: (modelId: string) => void;
}

function EnvironmentalFateView({ compound, expanded, onToggle, predictions, onViewCard }: EnvironmentalFateViewProps) {
  if (!compound) return null;

  const fate = calculateEnvironmentalFate(compound.logp, compound.mol_weight, compound.tpsa);
  if (!fate) return null;

  // Use predictions if available, else fallback to calculated
  const predKoc = predictions['soil_koc'];
  const predDt50 = predictions['soil_dt50'];
  const predGus = predictions['gus_index'];

  const gusValue = predGus?.value.kind === 'numeric' ? predGus.value.numeric : fate.gus;


  // Compute marker pin position as percentage from 0 to 5 on the GUS scale
  const positionPercent = Math.max(2, Math.min(98, (gusValue / 5.0) * 100.0));

  let categoryLabel = 'Non-leacher';
  let categoryDesc = '';
  let badgeClass = 'non-leacher';

  let computedCategory: 'Leacher' | 'Transition' | 'Non-leacher' = 'Non-leacher';
  if (gusValue > 2.8) {
    computedCategory = 'Leacher';
  } else if (gusValue >= 1.8) {
    computedCategory = 'Transition';
  }

  switch (computedCategory) {
    case 'Leacher':
      categoryLabel = 'Leacher';
      categoryDesc = 'High risk of groundwater leaching. Highly mobile and persistent.';
      badgeClass = 'leacher';
      break;
    case 'Transition':
      categoryLabel = 'Transition';
      categoryDesc = 'Moderate leaching risk. Mobility is highly dependent on soil/weather.';
      badgeClass = 'transition';
      break;
    case 'Non-leacher':
      categoryLabel = 'Non-leacher';
      categoryDesc = 'Low leaching potential. Strongly adsorbed to soil or rapidly degraded.';
      badgeClass = 'non-leacher';
      break;
  }

  return (
    <div className="collapsible-section">
      <div className="section-label collapsible-header" onClick={onToggle}>
        <span>ENVIRONMENTAL FATE & LEACHING</span>
        <span className="chevron">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="fate-card">
          <div className="fate-badge-container">
            <span style={{ fontSize: '11px', fontWeight: 500, color: 'var(--color-text-600)' }}>GUS Leaching Index</span>
            <span className={`fate-badge ${badgeClass}`}>{categoryLabel}</span>
          </div>

          <p className="systemic-description" style={{ marginTop: '-4px', marginBottom: '4px' }}>
            {categoryDesc}
          </p>

          {/* Visual GUS Slider */}
          <div className="gus-gauge-container">
            <div className="gus-gauge-track">
              <div 
                className="gus-gauge-pin" 
                style={{ left: `${positionPercent}%` }}
                title={`GUS Index: ${gusValue.toFixed(2)}`}
              />
            </div>
            <div className="gus-scale-labels">
              <span>0.0 (Low risk)</span>
              <span>1.8</span>
              <span>2.8</span>
              <span>5.0+ (High risk)</span>
            </div>
          </div>

          {/* Dynamic Metric Cards with PredictionDisplay */}
          <div className="fate-details-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', borderTop: '0.5px solid var(--color-border-subtle)', paddingTop: '8px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span className="fate-metric-label" style={{ textAlign: 'center', marginBottom: '2px', fontSize: '8px', color: 'var(--color-text-400)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '2px' }}>
                <span>Soil Sorption (Koc)</span>
                <ContextualHelp topicId="fate.koc" />
              </span>
              {predKoc ? (
                <PredictionDisplay prediction={predKoc} onClick={() => onViewCard(predKoc.model_id)} />
              ) : (
                <div style={{ height: '36px', background: 'var(--color-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '6px', fontSize: '10px', color: 'var(--color-text-400)' }}>Loading...</div>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span className="fate-metric-label" style={{ textAlign: 'center', marginBottom: '2px', fontSize: '8px', color: 'var(--color-text-400)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '2px' }}>
                <span>Persistence (DT50)</span>
                <ContextualHelp topicId="fate.dt50" />
              </span>
              {predDt50 ? (
                <PredictionDisplay prediction={predDt50} onClick={() => onViewCard(predDt50.model_id)} />
              ) : (
                <div style={{ height: '36px', background: 'var(--color-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '6px', fontSize: '10px', color: 'var(--color-text-400)' }}>Loading...</div>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span className="fate-metric-label" style={{ textAlign: 'center', marginBottom: '2px', fontSize: '8px', color: 'var(--color-text-400)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '2px' }}>
                <span>GUS Index</span>
                <ContextualHelp topicId="fate.gus" />
              </span>
              {predGus ? (
                <PredictionDisplay prediction={predGus} onClick={() => onViewCard(predGus.model_id)} />
              ) : (
                <div style={{ height: '36px', background: 'var(--color-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '6px', fontSize: '10px', color: 'var(--color-text-400)' }}>Loading...</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


interface FoliarPhotolysisResult {
  halfLifeBase: number; // Daylight DT50 in hours
  category: 'Photostable' | 'Sensitive' | 'Photolabile';
}

function calculateFoliarPhotolysis(
  logp: number | null | undefined,
  mw: number | null | undefined,
  tpsa: number | null | undefined
): FoliarPhotolysisResult | null {
  if (logp === null || logp === undefined || mw === null || mw === undefined || tpsa === null || tpsa === undefined) {
    return null;
  }

  // 1. Chromophore Factor (aromaticity/UV absorption approximation)
  // Highly lipophilic, large molecules typically contain multiple conjugated aromatic chromophores.
  const factorChromophore = 1.0 + 1.5 * Math.max(0.0, logp - 1.5) * (Math.max(0.0, mw - 150.0) / 150.0);

  // 2. Cuticular Hydrolysis Factor
  // Highly polar molecules (high TPSA) are more reactive/exposed to hydrolytic or indirect aqueous decay.
  const factorHydrolysis = 1.0 + 0.5 * (tpsa / 100.0);

  // 3. Foliar Half-life in Hours
  const halfLifeBase = Math.max(0.5, Math.min(120.0, 72.0 / (factorChromophore * factorHydrolysis)));

  let category: 'Photostable' | 'Sensitive' | 'Photolabile';
  if (halfLifeBase >= 24.0) {
    category = 'Photostable';
  } else if (halfLifeBase >= 6.0) {
    category = 'Sensitive';
  } else {
    category = 'Photolabile';
  }

  return {
    halfLifeBase,
    category,
  };
}

interface PhotostabilityViewProps {
  compound: {
    mol_weight?: number | null;
    logp?: number | null;
    tpsa?: number | null;
  } | null;
  expanded: boolean;
  onToggle: () => void;
}

function PhotostabilityView({ compound, expanded, onToggle }: PhotostabilityViewProps) {
  const [uvIntensity, setUvIntensity] = useState<'overcast' | 'moderate' | 'high'>('moderate');

  if (!compound) return null;

  const result = calculateFoliarPhotolysis(compound.logp, compound.mol_weight, compound.tpsa);
  if (!result) return null;

  const { halfLifeBase, category } = result;

  // Scale half-life based on UV Intensity selection
  let uvScale = 1.0;
  if (uvIntensity === 'overcast') uvScale = 2.5;
  if (uvIntensity === 'high') uvScale = 0.4;

  const halfLifeEffective = Math.max(0.2, Math.min(300.0, halfLifeBase * uvScale));
  const decayConstant = Math.log(2) / halfLifeEffective;

  // Calculate coordinates for the SVG path representing exponential decay C(t) = 100 * e^(-lambda * t)
  const chartWidth = 220;
  const chartHeight = 80;
  const paddingLeft = 24;
  const paddingRight = 12;
  const paddingTop = 8;
  const paddingBottom = 16;

  const plotWidth = chartWidth - paddingLeft - paddingRight;
  const plotHeight = chartHeight - paddingTop - paddingBottom;

  const points: [number, number][] = [];
  const maxHours = 48;

  for (let hour = 0; hour <= maxHours; hour += 1) {
    const concentration = 100.0 * Math.exp(-decayConstant * hour);
    const x = paddingLeft + (hour / maxHours) * plotWidth;
    const y = paddingTop + plotHeight - (concentration / 100.0) * plotHeight;
    points.push([x, y]);
  }

  const dPath = `M ${points.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' L ')}`;

  // Find where DT50 intersects the curve
  const intersectX = paddingLeft + (Math.min(maxHours, halfLifeEffective) / maxHours) * plotWidth;
  const intersectY = paddingTop + 0.5 * plotHeight;

  let badgeClass = 'stable';
  let badgeLabel = 'Photostable';
  let categoryDesc = '';

  switch (category) {
    case 'Photostable':
      badgeClass = 'stable';
      badgeLabel = 'Photostable';
      categoryDesc = 'Highly stable under solar radiation. Excellent persistence on leaf canopy.';
      break;
    case 'Sensitive':
      badgeClass = 'sensitive';
      badgeLabel = 'Sensitive';
      categoryDesc = 'Moderately photolabile. Sensitive to intense sunlight; microencapsulation recommended.';
      break;
    case 'Photolabile':
      badgeClass = 'photolabile';
      badgeLabel = 'Photolabile';
      categoryDesc = 'Highly sensitive to UV degradation. Half-life measured in minutes/hours. Microencapsulation or structural chromophore edits highly advised.';
      break;
  }

  // Calculate hourly decay rate (% loss in the first hour)
  const hourlyLoss = 100.0 * (1.0 - Math.exp(-decayConstant));

  return (
    <div className="collapsible-section">
      <div className="section-label collapsible-header" onClick={onToggle}>
        <span>UV PHOTOSTABILITY SIMULATOR</span>
        <span className="chevron">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="photostability-card">
          {/* Toggle Buttons */}
          <div className="uv-toggle-container">
            <div className="uv-toggle-label">Solar UV Intensity</div>
            <div className="uv-toggle-buttons">
              {(['overcast', 'moderate', 'high'] as const).map(mode => (
                <button
                  key={mode}
                  className={`uv-toggle-btn ${uvIntensity === mode ? 'active' : ''}`}
                  onClick={() => setUvIntensity(mode)}
                >
                  {mode === 'overcast' ? 'Overcast' : mode === 'moderate' ? 'Moderate' : 'High Solar'}
                </button>
              ))}
            </div>
          </div>

          {/* Degradation Chart */}
          <div className="degradation-chart-wrapper">
            <svg className="degradation-chart-svg" viewBox={`0 0 ${chartWidth} ${chartHeight}`}>
              {/* Grid Lines */}
              <line x1={paddingLeft} y1={paddingTop} x2={chartWidth - paddingRight} y2={paddingTop} className="chart-grid" />
              <line x1={paddingLeft} y1={paddingTop + 0.5 * plotHeight} x2={chartWidth - paddingRight} y2={paddingTop + 0.5 * plotHeight} className="chart-grid" />
              <line x1={paddingLeft} y1={chartHeight - paddingBottom} x2={chartWidth - paddingRight} y2={chartHeight - paddingBottom} className="chart-grid" />
              <line x1={paddingLeft + 0.5 * plotWidth} y1={paddingTop} x2={paddingLeft + 0.5 * plotWidth} y2={chartHeight - paddingBottom} className="chart-grid" />

              {/* Coordinate Axes */}
              <line x1={paddingLeft} y1={paddingTop} x2={paddingLeft} y2={chartHeight - paddingBottom} className="chart-axis" />
              <line x1={paddingLeft} y1={chartHeight - paddingBottom} x2={chartWidth - paddingRight} y2={chartHeight - paddingBottom} className="chart-axis" />

              {/* Axis Labels */}
              <text x={paddingLeft - 4} y={paddingTop + 4} textAnchor="end" className="chart-axis-text">100%</text>
              <text x={paddingLeft - 4} y={paddingTop + 0.5 * plotHeight + 3} textAnchor="end" className="chart-axis-text">50%</text>
              <text x={paddingLeft - 4} y={chartHeight - paddingBottom + 2} textAnchor="end" className="chart-axis-text">0%</text>

              <text x={paddingLeft} y={chartHeight - 4} textAnchor="middle" className="chart-axis-text">0h</text>
              <text x={paddingLeft + 0.5 * plotWidth} y={chartHeight - 4} textAnchor="middle" className="chart-axis-text">24h</text>
              <text x={chartWidth - paddingRight} y={chartHeight - 4} textAnchor="middle" className="chart-axis-text">48h</text>

              {/* Intersection Lines for DT50 */}
              {halfLifeEffective <= maxHours && (
                <>
                  <line x1={paddingLeft} y1={intersectY} x2={intersectX} y2={intersectY} className="chart-intersect-line" />
                  <line x1={intersectX} y1={intersectY} x2={intersectX} y2={chartHeight - paddingBottom} className="chart-intersect-line" />
                  <circle cx={intersectX} cy={intersectY} r="3" className="chart-highlight-dot" />
                </>
              )}

              {/* Decay Path */}
              <path d={dPath} className="chart-decay-path" />
            </svg>
          </div>

          {/* Details Footer */}
          <div className="fate-badge-container" style={{ marginTop: '2px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-600)' }}>Foliar Photostability</span>
            <span className={`photostability-badge ${badgeClass}`}>{badgeLabel}</span>
          </div>

          <p className="systemic-description" style={{ marginTop: '-4px', marginBottom: '2px' }}>
            {categoryDesc}
          </p>

          {/* Parameter Grid */}
          <div className="fate-details-grid" style={{ marginTop: '2px' }}>
            <div className="fate-metric-card" title="Effective foliar degradation half-life under daylight">
              <span className="fate-metric-label">Foliar DT50</span>
              <span className="fate-metric-value" style={{ color: 'var(--color-brand-700)' }}>
                {halfLifeEffective >= 24.0 ? `${(halfLifeEffective / 24.0).toFixed(1)}d` : `${halfLifeEffective.toFixed(1)}h`}
              </span>
              <span className="fate-metric-sub">Half-Life</span>
            </div>

            <div className="fate-metric-card" title="Hourly degradation loss percentage in early decay">
              <span className="fate-metric-label">Hourly Decay</span>
              <span className="fate-metric-value">
                {hourlyLoss >= 10.0 ? `${hourlyLoss.toFixed(0)}%` : `${hourlyLoss.toFixed(1)}%`}
              </span>
              <span className="fate-metric-sub">Loss / Hour</span>
            </div>

            <div className="fate-metric-card" title="UV Intensity Scaling multiplier">
              <span className="fate-metric-label">Daylight UV</span>
              <span className="fate-metric-value">
                {uvIntensity === 'overcast' ? '0.4×' : uvIntensity === 'moderate' ? '1.0×' : '2.5×'}
              </span>
              <span className="fate-metric-sub">Solar Load</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface BeneficialSelectivityResult {
  bee: number;         // Honeybee acute contact LD50 (ug/bee)
  worm: number;        // Earthworm soil LC50 (mg/kg)
  daphnia: number;     // Daphnia runoff EC50 (mg/L)
  trout: number;       // Rainbow Trout runoff LC50 (mg/L)
  duck: number;        // Mallard Duck oral/dietary LD50 (mg/kg)
  algae: number;       // Algae (Raphidocelis) EC50 (mg/L)
  fish: number;        // Fish (Rainbow Trout, 96h) LC50 (mg/L)
  aq: number;          // Agrochemical Safety Quotient (0-100)
  profile: 'Green Profile' | 'Yellow Profile' | 'Red Profile';
}

function calculateBeneficialSelectivity(
  logp: number | null | undefined,
  mw: number | null | undefined,
  tpsa: number | null | undefined
): BeneficialSelectivityResult | null {
  if (logp === null || logp === undefined || mw === null || mw === undefined || tpsa === null || tpsa === undefined) {
    return null;
  }

  // 1. Logarithmic QSAR Endpoints
  // Honeybees (ug/bee)
  const bee = Math.max(0.01, Math.min(100.0, Math.pow(10, 2.5 - 0.5 * logp)));
  // Earthworms (mg/kg)
  const worm = Math.max(0.1, Math.min(1000.0, Math.pow(10, 3.0 - 0.4 * logp)));
  // Daphnia (mg/L)
  const daphnia = Math.max(0.001, Math.min(100.0, Math.pow(10, 1.5 - 0.6 * logp)));
  // Rainbow Trout Runoff (mg/L)
  const trout = Math.max(0.001, Math.min(100.0, Math.pow(10, 2.0 - 0.7 * logp)));
  // Mallard Duck (mg/kg)
  const duck = Math.max(1.0, Math.min(5000.0, Math.pow(10, 3.5 - 0.3 * logp)));
  // Algae (Raphidocelis) EC50 (mg/L)
  const algae = Math.max(0.001, Math.min(100.0, Math.pow(10, 2.2 - 0.5 * logp - 0.002 * mw)));
  // Fish (Rainbow Trout, 96h) LC50 (mg/L)
  const fish = Math.max(0.001, Math.min(100.0, Math.pow(10, 1.6 - 0.55 * logp - 0.001 * mw)));

  // 2. Normalized Sub-scores (0.0 to 1.0)
  const sBee = (Math.log10(bee) + 2.0) / 4.0;
  const sWorm = (Math.log10(worm) + 1.0) / 4.0;
  const sDaphnia = (Math.log10(daphnia) + 3.0) / 5.0;
  const sTrout = (Math.log10(trout) + 3.0) / 5.0;
  const sDuck = Math.log10(duck) / 3.7;
  const sAlgae = (Math.log10(algae) + 3.0) / 5.0;
  const sFish = (Math.log10(fish) + 3.0) / 5.0;

  // 3. Composite AQ Score (0-100)
  const aq = Math.max(0, Math.min(100, Math.round(((sBee + sWorm + sDaphnia + sTrout + sDuck + sAlgae + sFish) / 7.0) * 100.0)));

  let profile: 'Green Profile' | 'Yellow Profile' | 'Red Profile';
  if (aq >= 75) {
    profile = 'Green Profile';
  } else if (aq >= 50) {
    profile = 'Yellow Profile';
  } else {
    profile = 'Red Profile';
  }

  return {
    bee,
    worm,
    daphnia,
    trout,
    duck,
    algae,
    fish,
    aq,
    profile,
  };
}

interface BeneficialSelectivityViewProps {
  compound: {
    mol_weight?: number | null;
    logp?: number | null;
    tpsa?: number | null;
  } | null;
  expanded: boolean;
  onToggle: () => void;
  predictions: Record<string, Prediction | null>;
  onViewCard: (modelId: string) => void;
}

function BeneficialSelectivityView({ compound, expanded, onToggle, predictions, onViewCard }: BeneficialSelectivityViewProps) {
  if (!compound) return null;

  const selectivity = calculateBeneficialSelectivity(compound.logp, compound.mol_weight, compound.tpsa);
  if (!selectivity) return null;

  const { aq, profile } = selectivity;

  let profileClass = 'profile-green';
  let profileDesc = '';
  switch (profile) {
    case 'Green Profile':
      profileClass = 'profile-green';
      profileDesc = 'Excellent ecological safety margins. Safe for non-target pollinators and aquatic life.';
      break;
    case 'Yellow Profile':
      profileClass = 'profile-yellow';
      profileDesc = 'Moderate selective boundaries. Formulation stabilizers or direct canopy timing advised.';
      break;
    case 'Red Profile':
      profileClass = 'profile-red';
      profileDesc = 'High ecotoxicological footprint. Bioaccumulative potential or high acute contact risk.';
      break;
  }

  const items = [
    { label: 'Honeybee (Oral)', ep: 'bee_acute_oral_ld50', icon: '🐝', topic: 'tox.bee_oral' },
    { label: 'Honeybee (Contact)', ep: 'bee_acute_contact_ld50', icon: '🐝', topic: 'tox.bee_contact' },
    { label: 'Earthworm LC50', ep: 'earthworm_acute_lc50', icon: '🪱', topic: 'tox.earthworm' },
    { label: 'Algae EC50', ep: 'algae_growth_ec50', icon: '🌱', topic: 'tox.algae' },
    { label: 'Daphnia EC50', ep: 'daphnia_acute_ec50', icon: '🦐', topic: 'tox.daphnia' },
    { label: 'Fish LC50', ep: 'fish_acute_lc50', icon: '🐟', topic: 'tox.fish' },
    { label: 'Bird LD50', ep: 'bird_acute_oral_ld50', icon: '🦆', topic: 'tox.bird' },
  ];

  return (
    <div className="collapsible-section">
      <div className="section-label collapsible-header" onClick={onToggle}>
        <span>BENEFICIAL SELECTIVITY</span>
        <span className="chevron">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="honeycomb-card">
          <div className="fate-badge-container">
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-600)' }}>Safety Quotient (AQ)</span>
            <span className={`aq-badge ${profileClass}`}>{aq}% AQ</span>
          </div>

          <p className="systemic-description" style={{ marginTop: '-4px', marginBottom: '4px' }}>
            {profileDesc}
          </p>

          {/* Grid Layout replacing the Hexagons */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '8px' }}>
            {items.map((item) => {
              const pred = predictions[item.ep];
              return (
                <div key={item.ep} style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  <div style={{ fontSize: '9px', fontWeight: 600, color: 'var(--color-text-600)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span>{item.icon}</span>
                    <span>{item.label}</span>
                    <ContextualHelp topicId={item.topic} />
                  </div>
                  {pred ? (
                    <PredictionDisplay prediction={pred} onClick={() => onViewCard(pred.model_id)} />
                  ) : (
                    <div style={{ height: '36px', background: 'var(--color-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '6px', fontSize: '9px', color: 'var(--color-text-400)' }}>Loading...</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}


/** MCS info banner shown when MCS mode is active. */
function McsBanner() {
  const mcsResult = useUIStore((s) => s.mcsResult);
  const mcsActive = useUIStore((s) => s.mcsActive);
  const clearMcs = useUIStore((s) => s.clearMcs);

  if (!mcsActive || !mcsResult) return null;

  return (
    <div className="mcs-banner">
      <div className="mcs-banner-header">
        <span className="mcs-banner-title">MCS Active</span>
        <button className="mcs-banner-close" onClick={clearMcs} title="Clear MCS">✕</button>
      </div>
      <div className="mcs-banner-stats">
        <span>{mcsResult.num_atoms} atoms</span>
        <span> · </span>
        <span>{mcsResult.num_bonds} bonds</span>
        <span> · </span>
        <span>{mcsResult.num_molecules} molecules</span>
      </div>
      {mcsResult.mcs_smarts && (
        <div className="mcs-banner-smarts selectable">
          {mcsResult.mcs_smarts}
        </div>
      )}
    </div>
  );
}

export function Inspector() {
  const activeView = useUIStore((s) => s.activeView);
  const selectedCompoundId = useUIStore((s) => s.selectedCompoundId);
  const libraryCompounds = useCompoundStore((s) => s.compounds);
  const workflowResults = useWorkflowStore((s) => s.results);
  const [predictions, setPredictions] = useState<Record<string, Prediction | null>>({});
  const [activeModelCardId, setActiveModelCardId] = useState<string | null>(null);

  const matchingPrediction = Object.values(predictions).find(
    (p) => p && p.model_id === activeModelCardId
  );

  // Detail & Compare modal state
  const showDetailModal = useUIStore((s) => s.showDetailModal);
  const showCompareModal = useUIStore((s) => s.showCompareModal);
  const compareCompoundIds = useUIStore((s) => s.compareCompoundIds);
  const setShowDetailModal = useUIStore((s) => s.setShowDetailModal);
  const setShowCompareModal = useUIStore((s) => s.setShowCompareModal);
  const setCompareCompoundIds = useUIStore((s) => s.setCompareCompoundIds);


  const mapOrganismToEndpoint = (organism: string): string => {
    const norm = organism.toLowerCase();
    if (norm.includes('bee')) return 'bee_acute_oral_ld50';
    if (norm.includes('fish')) return 'fish_acute_lc50';
    if (norm.includes('bird') || norm.includes('quail')) return 'bird_acute_oral_ld50';
    if (norm.includes('mammal') || norm.includes('rat')) return 'rat_acute_oral_ld50';
    if (norm.includes('daphnia')) return 'daphnia_acute_ec50';
    return '';
  };

  const mapEndpointToTopic = (ep: string): string => {
    switch (ep) {
      case 'bee_acute_oral_ld50': return 'tox.bee_oral';
      case 'bee_acute_contact_ld50': return 'tox.bee_contact';
      case 'fish_acute_lc50': return 'tox.fish';
      case 'bird_acute_oral_ld50': return 'tox.bird';
      case 'rat_acute_oral_ld50': return 'tox.mammalian_oral';
      case 'daphnia_acute_ec50': return 'tox.daphnia';
      default: return '';
    }
  };

  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    systemic: false,  // Minimized by default
    fate: false,      // Minimized by default
    photo: false,     // Minimized by default
    beneficial: false, // Minimized by default
    toxicity: false,   // Minimized by default
    selectivity: false, // Minimized by default
    resistance: false, // Minimized by default
    bioisostere: false, // Minimized by default
  });

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const allExpanded = expandedSections.systemic && expandedSections.fate && expandedSections.photo && expandedSections.beneficial && expandedSections.toxicity && expandedSections.selectivity && expandedSections.resistance && expandedSections.bioisostere;

  const toggleAll = () => {
    if (allExpanded) {
      setExpandedSections({ systemic: false, fate: false, photo: false, beneficial: false, toxicity: false, selectivity: false, resistance: false, bioisostere: false });
    } else {
      setExpandedSections({ systemic: true, fate: true, photo: true, beneficial: true, toxicity: true, selectivity: true, resistance: true, bioisostere: true });
    }
  };

  const selectedResultId = useKnowledgeStore((s) => s.selectedResultId);
  const knowledgeResults = useKnowledgeStore((s) => s.results);

  // Scroll reset & highlight pulse effect on compound change
  const [isPulsing, setIsPulsing] = useState(false);
  const inspectorRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (inspectorRef.current) {
      inspectorRef.current.scrollTop = 0;
    }
    setIsPulsing(true);
    const timer = setTimeout(() => setIsPulsing(false), 500);
    return () => clearTimeout(timer);
  }, [selectedCompoundId, selectedResultId, activeView]);

  // IMPORTANT: All hooks must be called unconditionally at the top level
  // to satisfy React's Rules of Hooks. Never call hooks inside if/else blocks.
  const selectedModelId = useModelStore((s) => s.selectedModelId);
  const modelsForInspector = useModelStore((s) => s.models) || [];

  const workflowCompound = activeView === 'workflows'
    ? workflowResults.find((c) => c.id === selectedCompoundId)
    : null;
  const libraryCompound = libraryCompounds.find((c) => c.id === selectedCompoundId) || null;
  const knowledgeCompound = activeView === 'knowledge'
    ? knowledgeResults.find((c) => c.id === selectedResultId)
    : null;

  const effectiveWorkflowCompound = workflowCompound || (activeView === 'workflows' && libraryCompound ? {
    id: libraryCompound.id,
    name: libraryCompound.name,
    smiles: libraryCompound.smiles,
    mol_weight: libraryCompound.mol_weight,
    logp: libraryCompound.logp,
    tpsa: libraryCompound.tpsa,
    hbd: libraryCompound.hbd,
    hba: libraryCompound.hba,
    rotatable_bonds: libraryCompound.rotatable_bonds,
    pesticide_likeness: null,
    tice_violations: null,
    selectivity: null,
    resistance: null,
    toxicity: null,
    mpo: null,
    score: null,
  } as WorkflowResultRecord : null);

  const selectedSmiles = effectiveWorkflowCompound?.smiles ?? libraryCompound?.smiles ?? knowledgeCompound?.smiles;
  const { svg, loading, error } = useStructureSvg(selectedSmiles);

  useEffect(() => {
    if (!selectedSmiles) {
      setPredictions({});
      return;
    }

    let active = true;

    const fetchAllPredictions = async () => {
      const ENDPOINTS = [
        'bee_acute_oral_ld50',
        'bee_acute_contact_ld50',
        'earthworm_acute_lc50',
        'algae_growth_ec50',
        'daphnia_acute_ec50',
        'fish_acute_lc50',
        'bird_acute_oral_ld50',
        'rat_acute_oral_ld50',
        'soil_koc',
        'soil_dt50',
        'gus_index',
      ];

      try {
        const results: Record<string, Prediction | null> = {};
        
        await Promise.all(
          ENDPOINTS.map(async (ep) => {
            try {
              const response = await invoke<Prediction[]>('model_predict', {
                endpoint: ep,
                smiles: [selectedSmiles],
                preferredTier: null,
              });
              if (response && response.length > 0) {
                results[ep] = response[0];
              } else {
                results[ep] = null;
              }
            } catch (err) {
              console.error(`[Inspector] Failed to fetch prediction for ${ep}:`, err);
              results[ep] = null;
            }
          })
        );

        if (active) {
          setPredictions(results);
        }
      } catch (err) {
        console.error('[Inspector] Error in fetchAllPredictions:', err);
      }
    };


    fetchAllPredictions();

    return () => {
      active = false;
    };
  }, [selectedSmiles]);


  // ── Knowledge View ──────────────────────────────────────────
  if (activeView === 'knowledge') {
    if (!knowledgeCompound) {
      return (
        <aside ref={inspectorRef} className={`inspector ${isPulsing ? 'pulse' : ''}`}>
          <div style={{ padding: '24px', display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
            <EmptyState
              icon="🌿"
              title="No Compound Selected"
              description="Select a pesticide record from the registry database list to view its profile, hazard classifications, and ecotox safety properties."
            />
          </div>
        </aside>
      );
    }

    const compound = knowledgeCompound;

    return (
      <aside ref={inspectorRef} className={`inspector ${isPulsing ? 'pulse' : ''}`}>
        {/* Header */}
        <div>
          <div className="section-label">REGISTRY PROFILE</div>
          <div className="inspector-compound-name">{compound.name}</div>
          <div className="inspector-compound-smiles selectable">
            CAS: {compound.cas_number} · {compound.formula}
          </div>
        </div>

        {/* 2D Structure */}
        <StructureView svg={svg} loading={loading} error={error} />

        {/* Class and MoA */}
        <div>
          <div className="section-label">CLASSIFICATION & MOA</div>
          <div className="inspector-props">
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Pesticide Class</span>
              <span className="inspector-prop-value" style={{ fontWeight: 600 }}>{compound.class}</span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Mechanism of Action</span>
              <span className="inspector-prop-value" style={{ fontSize: '10px', textAlign: 'right', wordBreak: 'break-word', maxWidth: '140px' }}>{compound.moa}</span>
            </div>
          </div>
        </div>

        {/* Regulatory Status */}
        <div>
          <div className="section-label">REGULATORY STATUS</div>
          <div className="inspector-props">
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">EU Approval</span>
              <span className="inspector-prop-value" style={{
                color: compound.regulatory_status.eu_status.toLowerCase().includes('approved') ? 'var(--color-brand-700)' : 'var(--color-red-700)',
                fontWeight: 600
              }}>
                {compound.regulatory_status.eu_status}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">US EPA Status</span>
              <span className="inspector-prop-value" style={{ fontWeight: 600 }}>
                {compound.regulatory_status.us_epa}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Approval Period</span>
              <span className="inspector-prop-value" style={{ fontSize: '10px' }}>
                {compound.regulatory_status.approval_period}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">EU MRL</span>
              <span className="inspector-prop-value" style={{ fontSize: '10px' }}>{compound.regulatory_status.mrl_eu}</span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">US MRL</span>
              <span className="inspector-prop-value" style={{ fontSize: '10px' }}>{compound.regulatory_status.mrl_us}</span>
            </div>
          </div>
          {compound.regulatory_status.hazard_classification && (
            <div className="ad-warning ad-borderline" style={{ marginTop: '6px' }}>
              <span className="ad-warning-icon">⚠</span>
              <div className="ad-warning-content">
                <div className="ad-warning-title">GHS Hazard Classification</div>
                <div className="ad-warning-details" style={{ fontSize: '10px', marginTop: '2px', wordBreak: 'break-word', whiteSpace: 'normal' }}>
                  {compound.regulatory_status.hazard_classification}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Ecotoxicity Profile */}
        <div>
          <div className="section-label">ECOTOXICOLOGICAL ENDPOINTS</div>
          <div className="inspector-toxicity-grid">
            {[
              { organism: 'Honeybees', value: compound.ecotox_endpoints.honeybee_ld50, topic: 'tox.bee_oral' },
              { organism: 'Fish', value: compound.ecotox_endpoints.fish_lc50, topic: 'tox.fish' },
              { organism: 'Birds', value: compound.ecotox_endpoints.bird_ld50, topic: 'tox.bird' },
              { organism: 'Mammals', value: compound.ecotox_endpoints.mammal_ld50, topic: 'tox.mammalian_oral' },
              { organism: 'Daphnia', value: compound.ecotox_endpoints.daphnia_ec50, topic: 'tox.daphnia' },
            ].map((tox) => {
              const isHigh = tox.value.toLowerCase().includes('high risk');
              const isMed = tox.value.toLowerCase().includes('medium risk');
              const isLow = tox.value.toLowerCase().includes('low risk');
              const levelStr = isHigh ? 'High' : isMed ? 'Med' : isLow ? 'Low' : '—';
              const levelClass = isHigh ? 'high' : isMed ? 'med' : isLow ? 'low' : 'unknown';

              return (
                <div key={tox.organism} className={`toxicity-card toxicity-${levelClass}`}>
                  <div className="toxicity-card-organism" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span>{tox.organism}</span>
                    <ContextualHelp topicId={tox.topic} />
                  </div>
                  <div className="toxicity-card-level">{levelStr} Risk</div>
                  <div className="toxicity-card-detail" style={{ fontSize: '9px', whiteSpace: 'normal', height: 'auto', WebkitLineClamp: 'unset', wordBreak: 'break-word' }}>{tox.value}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Resistance Management */}
        <div>
          <div className="section-label">RESISTANCE & CROPS</div>
          <div className="inspector-props">
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Resistance Risk</span>
              <span className="inspector-prop-value" style={{
                color: compound.resistance_factors.risk.toLowerCase().includes('low') ? 'var(--color-brand-700)' : compound.resistance_factors.risk.toLowerCase().includes('medium') ? 'var(--color-amber-700)' : 'var(--color-red-700)',
                fontWeight: 600
              }}>{compound.resistance_factors.risk}</span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Classification Group</span>
              <span className="inspector-prop-value">{compound.resistance_factors.hrac_irac}</span>
            </div>
          </div>
          {compound.resistance_factors.known_mutations && (
            <div className="inspector-notice" style={{ marginTop: '6px', fontSize: '9px', lineHeight: '1.3', whiteSpace: 'normal', wordBreak: 'break-word' }}>
              <span className="inspector-notice-icon">🧬</span>
              <strong>Known Mechanisms:</strong> {compound.resistance_factors.known_mutations}
            </div>
          )}
        </div>
      </aside>
    );
  }

  // ── Workflow View ─────────────────────────────────────────
  if (activeView === 'workflows') {
    if (!effectiveWorkflowCompound) {
      return (
        <aside ref={inspectorRef} className={`inspector ${isPulsing ? 'pulse' : ''}`}>
          <McsBanner />
          <div style={{ padding: '24px', display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
            <EmptyState
              icon="🔬"
              title="No Results Selected"
              description="Select a computed compound row from the workflow assessment results table to inspect detailed multi-parameter endpoints and model confidence scores."
            />
          </div>
        </aside>
      );
    }

    const compound = effectiveWorkflowCompound;

    return (
      <aside ref={inspectorRef} className={`inspector ${isPulsing ? 'pulse' : ''}`}>
        <McsBanner />

        {/* Header */}
        <div>
          <div className="section-label">SELECTED COMPOUND</div>
          <div className="inspector-compound-name">{compound.name}</div>
          <div className="inspector-compound-smiles selectable">{compound.smiles}</div>
        </div>

        {/* 2D Structure */}
        <StructureView svg={svg} loading={loading} error={error} />

        {/* Rank badge */}
        {compound.mpo && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', background: 'var(--color-bg-light)', padding: '10px', borderRadius: '8px', border: '0.5px solid var(--color-border)' }}>
            <div className={`inspector-rank rank-${compound.mpo.rank_category.toLowerCase()}`} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', margin: 0, width: '100%' }}>
              <span>{compound.mpo.rank_category} · Score {compound.score?.toFixed(1)}</span>
              {compound.uq?.score && (compound.uq.score.lower !== null || (compound.uq.score as any).ci_lower !== null) && (
                <IntervalBar
                  value={compound.score ?? 0}
                  lower={compound.uq.score.lower !== null ? compound.uq.score.lower : (compound.uq.score as any).ci_lower}
                  upper={compound.uq.score.upper !== null ? compound.uq.score.upper : (compound.uq.score as any).ci_upper}
                  minVal={0}
                  maxVal={10}
                />
              )}
            </div>
            
            {compound.uq && Object.keys(compound.uq).length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', borderTop: '0.5px solid var(--color-border-subtle)', paddingTop: '6px', marginTop: '2px' }}>
                {Object.entries(compound.uq).map(([key, envelope]) => (
                  <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ fontSize: '9px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--color-text-500)' }}>{key}:</span>
                    <UqBadge
                      status={envelope.ad_status}
                      score={envelope.ad_score}
                      coverage={envelope.coverage}
                      modelId={envelope.model_id}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Key Properties */}
        <div>
          <div className="section-label">KEY PROPERTIES</div>
          <div className="inspector-props">
            {[
              ['MW', compound.mol_weight != null ? `${compound.mol_weight.toFixed(2)} g/mol` : '—'],
              ['LogP', compound.logp != null ? compound.logp.toFixed(2) : '—'],
              ['TPSA', compound.tpsa != null ? `${compound.tpsa.toFixed(1)} Å²` : '—'],
              ['HBD', compound.hbd != null ? String(compound.hbd) : '—'],
              ['HBA', compound.hba != null ? String(compound.hba) : '—'],
              ['RotBonds', compound.rotatable_bonds != null ? String(compound.rotatable_bonds) : '—'],
            ].map(([label, value]) => (
              <div key={label} className="inspector-prop-row">
                <span className="inspector-prop-label">{label}</span>
                <span className="inspector-prop-value">{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Predictive Workflows Accordion Toolbar */}
        <div className="inspector-predictors-toolbar">
          <span className="predictors-toolbar-title">PREDICTIVE WORKFLOWS</span>
          <button className="predictors-toolbar-btn" onClick={toggleAll}>
            {allExpanded ? 'Collapse All' : 'Expand All'}
          </button>
        </div>

        {/* Plant Systemic Predictor */}
        <SystemicPredictorView 
          compound={compound} 
          expanded={expandedSections.systemic} 
          onToggle={() => toggleSection('systemic')} 
        />

        {/* Environmental Fate & Leaching Index */}
        <EnvironmentalFateView 
          compound={compound} 
          expanded={expandedSections.fate} 
          onToggle={() => toggleSection('fate')} 
          predictions={predictions}
          onViewCard={setActiveModelCardId}
        />

        {/* UV Photostability & Foliar Degradation */}
        <PhotostabilityView 
          compound={compound} 
          expanded={expandedSections.photo} 
          onToggle={() => toggleSection('photo')} 
        />

        {/* Beneficial Organism Selectivity Honeycomb Dashboard */}
        <BeneficialSelectivityView 
          compound={compound} 
          expanded={expandedSections.beneficial} 
          onToggle={() => toggleSection('beneficial')} 
          predictions={predictions}
          onViewCard={setActiveModelCardId}
        />


        {/* Bioisostere Scaffold-Hopping Suggestions Engine */}
        <BioisostereCarousel 
          compound={compound} 
          expanded={expandedSections.bioisostere} 
          onToggle={() => toggleSection('bioisostere')} 
        />

        {/* Selectivity Profile */}
        {compound.selectivity && (
          <div className="collapsible-section">
            <div className="section-label collapsible-header" onClick={() => toggleSection('selectivity')} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>SELECTIVITY PROFILE</span>
                {compound.uq?.selectivity && (
                  <UqBadge
                    status={compound.uq.selectivity.ad_status}
                    score={compound.uq.selectivity.ad_score}
                    coverage={compound.uq.selectivity.coverage}
                    modelId={compound.uq.selectivity.model_id}
                  />
                )}
              </div>
              <span className="chevron">{expandedSections.selectivity ? '▲' : '▼'}</span>
            </div>
            {expandedSections.selectivity && (
              compound.selectivity.disabled ? (
                <div className="inspector-notice" style={{ background: 'var(--color-sidebar)', border: '1px dashed var(--color-border-subtle)', marginTop: '4px' }}>
                  <span className="inspector-notice-icon">✕</span>
                  <strong>Excluded:</strong> Stage was excluded from optimization.
                </div>
              ) : (
                <div className="inspector-selectivity-grid">
                  {compound.selectivity.profiles.map((sel) => (
                    <div key={sel.organism} className={`selectivity-card selectivity-card-${sel.level} ${sel.ad_status === 'out' || sel.ad_status === 'out_of_domain' ? 'ood' : ''}`}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div className="selectivity-card-label" style={{ fontWeight: 600 }}>{sel.organism}</div>
                        {sel.ad_status && (sel.ad_status === 'out' || sel.ad_status === 'out_of_domain') && (
                          <span style={{ fontSize: '8px', fontWeight: 700, padding: '1px 3px', borderRadius: '3px', background: 'var(--color-red-600)', color: '#fff', lineHeight: 1, textTransform: 'uppercase' }}>OOD</span>
                        )}
                      </div>
                      <div className="selectivity-card-value" style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                        <span>{sel.selectivity_index}×</span>
                        {sel.ci_lower !== undefined && sel.ci_upper !== undefined && (
                          <span style={{ fontSize: '9px', fontWeight: 400, opacity: 0.8, fontFamily: 'var(--font-mono)' }}>
                            [{sel.ci_lower}–{sel.ci_upper}]
                          </span>
                        )}
                      </div>
                      <div className="selectivity-card-sub">{sel.detail}</div>
                    </div>
                  ))}
                </div>
              )
            )}
          </div>
        )}

        {/* Resistance */}
        {compound.resistance && (
          <div className="collapsible-section">
            <div className="section-label collapsible-header" onClick={() => toggleSection('resistance')} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>RESISTANCE RISK</span>
                {compound.uq?.resistance && (
                  <UqBadge
                    status={compound.uq.resistance.ad_status}
                    score={compound.uq.resistance.ad_score}
                    coverage={compound.uq.resistance.coverage}
                    modelId={compound.uq.resistance.model_id}
                  />
                )}
              </div>
              <span className="chevron">{expandedSections.resistance ? '▲' : '▼'}</span>
            </div>
            {expandedSections.resistance && (
              compound.resistance.disabled ? (
                <div className="inspector-notice" style={{ background: 'var(--color-sidebar)', border: '1px dashed var(--color-border-subtle)', marginTop: '4px' }}>
                  <span className="inspector-notice-icon">✕</span>
                  <strong>Excluded:</strong> Stage was excluded from optimization.
                </div>
              ) : (
                <>
                  <div className="inspector-props">
                    <div className="inspector-prop-row">
                      <span className="inspector-prop-label">Risk level</span>
                      <span className="inspector-prop-value" style={{
                        color: compound.resistance.level === 'Low'
                          ? 'var(--color-brand-700)'
                          : compound.resistance.level === 'Med'
                            ? 'var(--color-amber-700)'
                            : 'var(--color-red-700)',
                        fontWeight: 500,
                      }}>
                        {compound.resistance.level} ({compound.resistance.risk_score}/10)
                      </span>
                    </div>
                    {compound.resistance.factors.map((f, i) => (
                      <div key={i} className="inspector-prop-row">
                        <span className="inspector-prop-label">{f.factor}</span>
                        <span className="inspector-prop-value" style={{ fontSize: '10px' }}>
                          {f.assessment}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* MoA Classification */}
                  {compound.resistance.moa_classification && (
                    <div className="moa-classification">
                      <div className="moa-badge">
                        <span className="moa-badge-tag">
                          {compound.resistance.moa_classification.classification}
                        </span>
                        <span className="moa-badge-group">
                          Group {compound.resistance.moa_classification.group}
                        </span>
                      </div>
                      <div className="moa-name">
                        {compound.resistance.moa_classification.group_name}
                      </div>
                      {compound.resistance.moa_classification.resistance_prevalence && (
                        <div className="moa-prevalence">
                          {compound.resistance.moa_classification.resistance_prevalence}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Cross-Resistance */}
                  {compound.resistance.cross_resistance && (
                    <div className="inspector-props" style={{ marginTop: '6px' }}>
                      <div className="inspector-prop-row">
                        <span className="inspector-prop-label">Cross-resistance</span>
                        <span className="inspector-prop-value" style={{
                          color: compound.resistance.cross_resistance.level === 'Low'
                            ? 'var(--color-brand-700)'
                            : compound.resistance.cross_resistance.level === 'Med'
                              ? 'var(--color-amber-700)'
                              : 'var(--color-red-700)',
                          fontSize: '10px',
                          fontWeight: 500,
                        }}>
                          {compound.resistance.cross_resistance.level}
                        </span>
                      </div>
                    </div>
                  )}
                </>
              )
            )}
          </div>
        )}

        {/* Toxicity Profile */}
        {compound.toxicity && (
          <div className="collapsible-section">
            <div className="section-label collapsible-header" onClick={() => toggleSection('toxicity')} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>TOXICITY PROFILE</span>
                {compound.uq?.toxicity && (
                  <UqBadge
                    status={compound.uq.toxicity.ad_status}
                    score={compound.uq.toxicity.ad_score}
                    coverage={compound.uq.toxicity.coverage}
                    modelId={compound.uq.toxicity.model_id}
                  />
                )}
              </div>
              <span className="chevron">{expandedSections.toxicity ? '▲' : '▼'}</span>
            </div>
            {expandedSections.toxicity && (
              compound.toxicity.disabled ? (
                <div className="inspector-notice" style={{ background: 'var(--color-sidebar)', border: '1px dashed var(--color-border-subtle)', marginTop: '4px' }}>
                  <span className="inspector-notice-icon">✕</span>
                  <strong>Excluded:</strong> Stage was excluded from optimization.
                </div>
              ) : (
                <>
                  <div className="inspector-toxicity-grid">
                    {compound.toxicity.predictions.map((tox) => {
                      const ep = mapOrganismToEndpoint(tox.organism);
                      const pred = ep ? predictions[ep] : null;

                      return (
                        <div key={tox.organism} style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                          <div style={{ fontSize: '9px', fontWeight: 600, color: 'var(--color-text-600)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <span>{tox.organism} {tox.organism_latin ? `(${tox.organism_latin})` : ''}</span>
                            <ContextualHelp topicId={ep ? mapEndpointToTopic(ep) : ''} />
                          </div>
                          {pred ? (
                            <PredictionDisplay prediction={pred} onClick={() => setActiveModelCardId(pred.model_id)} />
                          ) : (
                            <div className={`toxicity-card toxicity-${tox.level.toLowerCase()}`} style={{ margin: 0, width: '100%' }}>
                              <div className="toxicity-card-level">{tox.level}</div>
                              <div className="toxicity-card-detail">{tox.detail}</div>
                              <div className="toxicity-card-threshold">{tox.threshold}</div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Applicability Domain Warning */}
                  {compound.toxicity.applicability_domain &&
                    compound.toxicity.applicability_domain.status !== 'in_domain' && (
                    <div className={`ad-warning ad-${compound.toxicity.applicability_domain.status.replace('_', '-')}`}>
                      <span className="ad-warning-icon">
                        {compound.toxicity.applicability_domain.status === 'out_of_domain' ? '⚠' : 'ℹ'}
                      </span>
                      <div className="ad-warning-content">
                        <div className="ad-warning-title" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span>
                            {compound.toxicity.applicability_domain.status === 'out_of_domain'
                              ? 'Outside Applicability Domain'
                              : 'Borderline Applicability Domain'}
                          </span>
                          <ContextualHelp topicId="ad.status" />
                        </div>
                        <div className="ad-warning-confidence">
                          Confidence: {(compound.toxicity.applicability_domain.confidence * 100).toFixed(0)}%
                        </div>
                        {compound.toxicity.applicability_domain.warnings.length > 0 && (
                          <div className="ad-warning-details">
                            {compound.toxicity.applicability_domain.warnings.slice(0, 3).map((w, i) => (
                              <div key={i} className="ad-warning-item">• {w}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )
            )}
          </div>
        )}


        {/* MPO Breakdown */}
        {compound.mpo && (
          <div>
            <div className="section-label">MPO BREAKDOWN</div>
            <div className="inspector-props">
              {Object.entries(compound.mpo.breakdown).map(([key, val]) => (
                <div key={key} className="inspector-prop-row">
                  <span className="inspector-prop-label">{key.replace(/_/g, ' ')}</span>
                  <span className="inspector-prop-value">{val}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="inspector-actions">
          <div className="inspector-action-row">
            <button
              className="inspector-btn"
              onClick={() => setShowDetailModal(true)}
            >
              Detail view
            </button>
            <button
              className="inspector-btn"
              onClick={() => {
                // If no compare set, seed with current compound
                if (compareCompoundIds.length < 2) {
                  setCompareCompoundIds([compound.id]);
                }
                setShowCompareModal(true);
              }}
            >
              Compare
            </button>
          </div>
          <button className="inspector-btn-primary">
            Add to candidates list →
          </button>
        </div>

        {activeModelCardId && (
          <ModelCardViewer 
            modelId={activeModelCardId} 
            onClose={() => setActiveModelCardId(null)} 
            queryDistance={matchingPrediction?.ad_score ?? undefined}
            queryStatus={matchingPrediction?.ad_status ?? undefined}
          />
        )}

        {/* Detail Modal */}
        {showDetailModal && (
          <CompoundDetailModal
            compound={compound}
            onClose={() => setShowDetailModal(false)}
          />
        )}

        {/* Compare Modal */}
        {showCompareModal && (
          <CompoundCompareModal
            compounds={
              compareCompoundIds.length >= 2
                ? workflowResults.filter(r => compareCompoundIds.includes(r.id))
                : [compound]
            }
            allResults={workflowResults}
            onClose={() => setShowCompareModal(false)}
          />
        )}
      </aside>
    );
  }


  // ── Library View ──────────────────────────────────────────
  if (activeView === 'library') {
    if (!libraryCompound) {
      return (
        <aside ref={inspectorRef} className={`inspector ${isPulsing ? 'pulse' : ''}`}>
          <McsBanner />
          <div style={{ padding: '24px', display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
            <EmptyState
              icon="🔬"
              title="No Compound Selected"
              description="Select a compound card from the active project library grid to view molecular properties and start modeling analysis."
            />
          </div>
        </aside>
      );
    }

    const compound = libraryCompound;

    return (
      <aside ref={inspectorRef} className={`inspector ${isPulsing ? 'pulse' : ''}`}>
        <McsBanner />

        <div>
          <div className="section-label">SELECTED COMPOUND</div>
          <div className="inspector-compound-name">{compound.name}</div>
          <div className="inspector-compound-smiles selectable">{compound.smiles}</div>
        </div>

        {/* 2D Structure */}
        <StructureView svg={svg} loading={loading} error={error} />

        <div>
          <div className="section-label">PROPERTIES</div>
          <div className="inspector-props">
            {[
              ['MW', compound.mol_weight != null ? `${compound.mol_weight.toFixed(2)} g/mol` : '—'],
              ['LogP', compound.logp != null ? compound.logp.toFixed(2) : '—'],
              ['TPSA', compound.tpsa != null ? `${compound.tpsa.toFixed(1)} Å²` : '—'],
              ['HBD', compound.hbd != null ? String(compound.hbd) : '—'],
              ['HBA', compound.hba != null ? String(compound.hba) : '—'],
              ['RotBonds', compound.rotatable_bonds != null ? String(compound.rotatable_bonds) : '—'],
            ].map(([label, value]) => (
              <div key={label} className="inspector-prop-row">
                <span className="inspector-prop-label">{label}</span>
                <span className="inspector-prop-value">{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Predictive Workflows Accordion Toolbar */}
        <div className="inspector-predictors-toolbar">
          <span className="predictors-toolbar-title">PREDICTIVE WORKFLOWS</span>
          <button className="predictors-toolbar-btn" onClick={toggleAll}>
            {allExpanded ? 'Collapse All' : 'Expand All'}
          </button>
        </div>

        {/* Plant Systemic Predictor */}
        <SystemicPredictorView 
          compound={compound} 
          expanded={expandedSections.systemic} 
          onToggle={() => toggleSection('systemic')} 
        />

        {/* Environmental Fate & Leaching Index */}
        <EnvironmentalFateView 
          compound={compound} 
          expanded={expandedSections.fate} 
          onToggle={() => toggleSection('fate')} 
          predictions={predictions}
          onViewCard={setActiveModelCardId}
        />

        {/* UV Photostability & Foliar Degradation */}
        <PhotostabilityView 
          compound={compound} 
          expanded={expandedSections.photo} 
          onToggle={() => toggleSection('photo')} 
        />

        {/* Beneficial Organism Selectivity Honeycomb Dashboard */}
        <BeneficialSelectivityView 
          compound={compound} 
          expanded={expandedSections.beneficial} 
          onToggle={() => toggleSection('beneficial')} 
          predictions={predictions}
          onViewCard={setActiveModelCardId}
        />

        {/* Bioisostere Scaffold-Hopping Suggestions Engine */}
        <BioisostereCarousel 
          compound={compound} 
          expanded={expandedSections.bioisostere} 
          onToggle={() => toggleSection('bioisostere')} 
        />

        <div className="inspector-notice">
          <span className="inspector-notice-icon">ℹ</span>
          Run a workflow to compute full analysis.
        </div>

        {activeModelCardId && (
          <ModelCardViewer 
            modelId={activeModelCardId} 
            onClose={() => setActiveModelCardId(null)} 
            queryDistance={matchingPrediction?.ad_score ?? undefined}
            queryStatus={matchingPrediction?.ad_status ?? undefined}
          />
        )}
      </aside>
    );

  }

  // ── Models View ───────────────────────────────────────────
  if (activeView === 'models') {
    const activeModel = selectedModelId ? modelsForInspector.find((m) => m.id === selectedModelId) : undefined;

    if (!activeModel) {
      return (
        <aside ref={inspectorRef} className={`inspector ${isPulsing ? 'pulse' : ''}`}>
          <div style={{ padding: '24px', display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
            <EmptyState
              icon="🤖"
              title="No Model Selected"
              description="Choose a custom QSAR machine learning model from the model manager list to inspect validation metrics, features, and SHAP feature attributions."
            />
          </div>
        </aside>
      );
    }

    let features: string[] = [];
    let metrics: Record<string, number> = {};
    let importances: Record<string, number> = {};

    try {
      features = JSON.parse(activeModel.features || '[]') as string[];
      if (!Array.isArray(features)) {
        features = [];
      }
    } catch (e) {
      console.error('[ERROR] Failed to parse features for model', activeModel.id, e);
    }

    try {
      metrics = JSON.parse(activeModel.metrics || '{}') as Record<string, number>;
      if (!metrics || typeof metrics !== 'object') {
        metrics = {};
      }
    } catch (e) {
      console.error('[ERROR] Failed to parse metrics for model', activeModel.id, e);
    }

    try {
      importances = JSON.parse(activeModel.importances || '{}') as Record<string, number>;
      if (!importances || typeof importances !== 'object') {
        importances = {};
      }
    } catch (e) {
      console.error('[ERROR] Failed to parse importances for model', activeModel.id, e);
    }

    const sortedImportances = Object.entries(importances).sort((a, b) => b[1] - a[1]);

    return (
      <aside ref={inspectorRef} className={`inspector ${isPulsing ? 'pulse' : ''}`}>
        <div>
          <div className="section-label">SELECTED MODEL</div>
          <div className="inspector-compound-name">{activeModel.name}</div>
          <div className="inspector-compound-smiles selectable">
            {activeModel.algorithm} · {activeModel.type === 'regression' ? 'Regression' : 'Classification'}
          </div>
        </div>

        <div>
          <div className="section-label">PERFORMANCE METRICS</div>
          <div className="inspector-props">
            {activeModel.type === 'regression' ? (
              <>
                <div className="inspector-prop-row">
                  <span className="inspector-prop-label">R² Validation</span>
                  <span className="inspector-prop-value" style={{ color: 'var(--color-brand-700)', fontWeight: 600 }}>
                    {metrics.r2_val?.toFixed(3) ?? '—'}
                  </span>
                </div>
                <div className="inspector-prop-row">
                  <span className="inspector-prop-label">R² Training</span>
                  <span className="inspector-prop-value">{metrics.r2_train?.toFixed(3) ?? '—'}</span>
                </div>
                <div className="inspector-prop-row">
                  <span className="inspector-prop-label">RMSE Validation</span>
                  <span className="inspector-prop-value">{metrics.rmse_val?.toFixed(3) ?? '—'}</span>
                </div>
                <div className="inspector-prop-row">
                  <span className="inspector-prop-label">MAE Validation</span>
                  <span className="inspector-prop-value">{metrics.mae_val?.toFixed(3) ?? '—'}</span>
                </div>
              </>
            ) : (
              <>
                <div className="inspector-prop-row">
                  <span className="inspector-prop-label">Accuracy Val</span>
                  <span className="inspector-prop-value" style={{ color: 'var(--color-brand-700)', fontWeight: 600 }}>
                    {metrics.accuracy_val?.toFixed(3) ?? '—'}
                  </span>
                </div>
                <div className="inspector-prop-row">
                  <span className="inspector-prop-label">Accuracy Train</span>
                  <span className="inspector-prop-value">{metrics.accuracy_train?.toFixed(3) ?? '—'}</span>
                </div>
                <div className="inspector-prop-row">
                  <span className="inspector-prop-label">Precision Val</span>
                  <span className="inspector-prop-value">{metrics.precision?.toFixed(3) ?? '—'}</span>
                </div>
                <div className="inspector-prop-row">
                  <span className="inspector-prop-label">Recall Val</span>
                  <span className="inspector-prop-value">{metrics.recall?.toFixed(3) ?? '—'}</span>
                </div>
                <div className="inspector-prop-row">
                  <span className="inspector-prop-label">F1 Score Val</span>
                  <span className="inspector-prop-value">{metrics.f1_score?.toFixed(3) ?? '—'}</span>
                </div>
                <div className="inspector-prop-row">
                  <span className="inspector-prop-label">AUC-ROC Val</span>
                  <span className="inspector-prop-value">{metrics.auc_roc?.toFixed(3) ?? '—'}</span>
                </div>
              </>
            )}
          </div>
        </div>

        <div>
          <div className="section-label">MODEL CONFIGURATION</div>
          <div className="inspector-props">
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Features Used</span>
              <span className="inspector-prop-value" style={{ fontSize: '10px', maxWidth: '160px', textAlign: 'right', wordBreak: 'break-word' }}>
                {features.map(f => f === 'MorganFingerprints' ? 'Morgan FP' : f).join(', ')}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Trained On</span>
              <span className="inspector-prop-value" style={{ fontSize: '10px' }}>
                {activeModel.created_at ? new Date(activeModel.created_at).toLocaleDateString() : '—'}
              </span>
            </div>
          </div>
        </div>

        {sortedImportances.length > 0 && (
          <div>
            <div className="section-label">FEATURE IMPORTANCES</div>
            <div className="feature-importances-inspector">
              {sortedImportances.map(([feat, val]) => (
                <div key={feat} className="inspector-feature-row">
                  <div className="inspector-feature-header">
                    <span className="inspector-feature-label">{feat === 'Morgan Fingerprints' ? 'Morgan FP' : feat}</span>
                    <span className="inspector-feature-val">{(val * 100).toFixed(1)}%</span>
                  </div>
                  <div className="inspector-feature-bar-bg">
                    <div
                      className="inspector-feature-bar-fill"
                      style={{ width: `${Math.max(1, val * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>
    );
  }

  // ── Default ───────────────────────────────────────────────
  return (
    <aside ref={inspectorRef} className={`inspector ${isPulsing ? 'pulse' : ''}`}>
      <div style={{ padding: '24px', display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
        <EmptyState
          icon="📋"
          title="Inspector Panel Empty"
          description="Select any active project compound, dossier report, or algorithm configuration to load details here."
        />
      </div>
    </aside>
  );
}
