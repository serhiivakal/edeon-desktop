import { useEffect, useState } from 'react';
import { useProjectStore } from '../store/projectStore';
import { useCompoundStore } from '../store/compoundStore';
import { useFateStore } from '../store/fateStore';
import { UqBadge, AdStatus } from '../components/uq/UqBadge';
import { PathwayTree } from '../components/fate/PathwayTree';
import { Scorecard } from '../components/regulatory/Scorecard';
import { SpeciesBadge } from '../components/speciation/SpeciesBadge';
import { SpeciationCurve } from '../components/speciation/SpeciationCurve';
import { MobilityCard } from '../components/fate/MobilityCard';
import type { PredictorAdStatus, Prediction } from '../types';

// Map the internal PredictorAdStatus to UqBadge's AdStatus format
function mapAdStatus(status: PredictorAdStatus | undefined): AdStatus {
  if (!status) return 'unknown';
  switch (status) {
    case 'in': return 'in_domain';
    case 'out': return 'out_of_domain';
    case 'borderline': return 'borderline';
    default: return 'unknown';
  }
}

export function FateView() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);

  const getNumeric = (pred: any): number | null => {
    if (pred && pred.value && pred.value.kind === 'numeric') {
      return pred.value.numeric;
    }
    return null;
  };

  const compounds = useCompoundStore((s) => s.compounds);
  const fetchCompounds = useCompoundStore((s) => s.fetchCompounds);
  
  const fatePredictions = useFateStore((s) => s.predictions);
  const computeFate = useFateStore((s) => s.computeEnvironmentalFate);
  const fateLoading = useFateStore((s) => s.loading);

  const tpGraphs = useFateStore((s) => s.tpGraphs);
  const tpLoading = useFateStore((s) => s.loadingTP);
  const tpError = useFateStore((s) => s.errorTP);
  const predictTP = useFateStore((s) => s.predictTransformationProducts);

  const [selectedSmiles, setSelectedSmiles] = useState<string | null>(null);
  const [selectedName, setSelectedName] = useState<string>('');
  const [calcError, setCalcError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'parent' | 'transformation' | 'regulatory'>('parent');

  const [routes, setRoutes] = useState<string[]>(['abiotic', 'metabolic']);
  const [sources, setSources] = useState<string[]>(['soil_microbial', 'hydrolysis']);
  const [maxDepth, setMaxDepth] = useState<number>(2);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useEffect(() => {
    if (activeProjectId) {
      fetchCompounds(activeProjectId);
    }
  }, [activeProjectId, fetchCompounds]);

  useEffect(() => {
    if (compounds.length > 0 && !selectedSmiles) {
      setSelectedSmiles(compounds[0].smiles);
      setSelectedName(compounds[0].name);
    }
  }, [compounds, selectedSmiles]);

  useEffect(() => {
    if (selectedSmiles) {
      setCalcError(null);
      computeFate([selectedSmiles]).catch((err) => {
        console.error(err);
        setCalcError(String(err));
      });
    }
  }, [selectedSmiles, computeFate]);

  const tpKey = `${selectedSmiles}_${routes.join(',')}_${maxDepth}_${sources.join(',')}_${useFateStore.getState().phTarget}`;
  const currentTpGraph = selectedSmiles ? tpGraphs[tpKey] : null;

  useEffect(() => {
    if (activeTab === 'transformation' && selectedSmiles && !currentTpGraph && !tpLoading) {
      predictTP(selectedSmiles, routes, maxDepth, sources).catch(console.error);
    }
  }, [activeTab, selectedSmiles, tpKey, tpGraphs, tpLoading, predictTP, routes, maxDepth, sources]);

  useEffect(() => {
    setSelectedNodeId(null);
  }, [selectedSmiles, routes, maxDepth]);

  if (!activeProjectId) {
    return (
      <div className="main-content">
        <div className="library-empty-state">
          <div className="library-empty-icon">&#128194;</div>
          <h2>No project selected</h2>
          <p>Select a project from the sidebar to inspect environmental fate.</p>
        </div>
      </div>
    );
  }

  if (compounds.length === 0) {
    return (
      <div className="main-content">
        <div className="library-empty-state">
          <div className="library-empty-icon">&#129514;</div>
          <h2>No compounds in library</h2>
          <p>Please import or add compounds first in the Library view.</p>
        </div>
      </div>
    );
  }

  const selectedFate = selectedSmiles ? fatePredictions[selectedSmiles] : null;

  const selectedNodeDetails = selectedNodeId && currentTpGraph
    ? currentTpGraph.nodes.find(n => n.id === selectedNodeId)
    : null;

  const renderThresholdBar = (
    label: string,
    value: number,
    threshold: number,
    unit: string,
    inverse = false
  ) => {
    const ratio = Math.min(100, Math.max(0, (value / (threshold * 2)) * 100));
    const exceeds = inverse ? value < threshold : value > threshold;

    return (
      <div style={{ marginTop: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
          <span style={{ color: 'var(--color-text-500)', fontWeight: 500 }}>{label} Comparison</span>
          <span style={{ 
            color: exceeds ? 'var(--color-red-600)' : 'var(--color-brand-600)',
            fontWeight: 600
          }}>
            {exceeds ? 'Exceeds Trigger' : 'Safe / Below Trigger'} ({threshold} {unit})
          </span>
        </div>
        <div style={{ 
          height: '6px', 
          width: '100%', 
          background: 'rgba(0,0,0,0.06)', 
          borderRadius: '3px',
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{ 
            position: 'absolute', 
            left: '50%', 
            top: 0, 
            bottom: 0, 
            width: '2px', 
            background: 'var(--color-text-400)',
            zIndex: 2
          }} />
          <div style={{ 
            height: '100%', 
            width: `${ratio}%`, 
            background: exceeds 
              ? 'linear-gradient(90deg, var(--color-red-400), var(--color-red-600))'
              : 'linear-gradient(90deg, var(--color-brand-400), var(--color-brand-600))',
            borderRadius: '3px',
            transition: 'width 0.4s ease'
          }} />
        </div>
      </div>
    );
  };

  const renderUqBadge = (pred: Prediction | undefined) => {
    if (!pred) return null;
    return <UqBadge status={mapAdStatus(pred.ad_status)} score={pred.ad_score} />;
  };

  return (
    <div className="main-content" style={{ display: 'flex', height: '100%', overflow: 'hidden', boxSizing: 'border-box', padding: '16px', gap: '16px' }}>
      
      {/* Left panel: Compound selection list */}
      <div className="card" style={{ 
        width: '260px', 
        display: 'flex', 
        flexDirection: 'column', 
        minHeight: 0,
        background: 'var(--color-surface)',
        border: '0.5px solid var(--color-border)',
        borderRadius: '8px',
        padding: '12px'
      }}>
        <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase', marginBottom: '12px', letterSpacing: '0.05em' }}>
          Compounds
        </div>
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {compounds.map((c) => {
            const isSelected = c.smiles === selectedSmiles;
            const fateResult = fatePredictions[c.smiles];
            
            return (
              <div
                key={c.id}
                onClick={() => {
                  setSelectedSmiles(c.smiles);
                  setSelectedName(c.name);
                }}
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  background: isSelected ? 'var(--color-brand-50)' : 'transparent',
                  border: isSelected ? '0.5px solid var(--color-brand-200)' : '0.5px solid transparent',
                  transition: 'all 0.15s ease'
                }}
                className={isSelected ? 'active' : ''}
              >
                <div style={{ 
                  fontSize: '12px', 
                  fontWeight: 600, 
                  color: isSelected ? 'var(--color-brand-900)' : 'var(--color-text-900)',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap'
                }}>
                  {c.name}
                </div>
                <div style={{ 
                  fontSize: '10px', 
                  color: 'var(--color-text-400)',
                  fontFamily: 'monospace',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap',
                  marginTop: '2px'
                }}>
                  {c.smiles}
                </div>
                {fateResult && (
                  <div style={{ display: 'flex', gap: '6px', marginTop: '6px', alignItems: 'center' }}>
                    <span className={`rank-badge rank-${
                      fateResult.pbt.verdict === 'Not PBT/vPvB' || fateResult.pbt.verdict === 'Low Risk' ? 'candidate' : 'deprioritize'
                    }`} style={{ fontSize: '8px', padding: '1px 3px' }}>
                      {fateResult.pbt.verdict}
                    </span>
                    <span style={{ 
                      fontSize: '8px', 
                      color: fateResult.gus.class === 'leacher' ? 'var(--color-red-600)' : fateResult.gus.class === 'transition' ? 'var(--color-amber-600)' : 'var(--color-brand-600)',
                      fontWeight: 600
                    }}>
                      GUS: {fateResult.gus.value.kind === 'numeric' && fateResult.gus.value.numeric != null ? fateResult.gus.value.numeric.toFixed(1) : '\u2014'}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Right panel */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, gap: '16px', overflowY: 'auto' }}>
        
        {/* Header card */}
        <div className="card" style={{ 
          background: 'var(--color-surface)',
          border: '0.5px solid var(--color-border)',
          borderRadius: '8px',
          padding: '16px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <h1 style={{ fontSize: '20px', fontWeight: 700, margin: 0, color: 'var(--color-text-900)' }}>
                  {selectedName}
                </h1>
                {selectedSmiles && <SpeciesBadge smiles={selectedSmiles} />}
              </div>
              <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--color-text-500)', marginTop: '4px', wordBreak: 'break-all' }}>
                {selectedSmiles}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--color-surface-hover)', padding: '6px 12px', borderRadius: '6px', border: '0.5px solid var(--color-border)' }}>
              <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-600)' }}>Target Soil pH:</span>
              <input
                type="range"
                min="4.0"
                max="9.0"
                step="0.1"
                value={useFateStore((s) => s.phTarget)}
                onChange={(e) => useFateStore.getState().setPhTarget(parseFloat(e.target.value))}
                style={{ cursor: 'pointer', width: '80px' }}
              />
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-brand-600)', minWidth: '28px' }}>
                {useFateStore((s) => s.phTarget).toFixed(1)}
              </span>
            </div>
            {(fateLoading || tpLoading) && (
              <span style={{ 
                fontSize: '12px', 
                color: 'var(--color-brand-700)', 
                background: 'var(--color-brand-50)', 
                padding: '4px 8px', 
                borderRadius: '6px',
                fontWeight: 500,
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <span className="spinner" style={{ display: 'inline-block', width: '10px', height: '10px', border: '2px solid var(--color-brand-700)', borderTopColor: 'transparent', borderRadius: '50%' }} />
                Predicting...
              </span>
            )}
          </div>

          {calcError && (
            <div style={{ 
              marginTop: '12px', 
              padding: '12px', 
              background: 'rgba(239, 68, 68, 0.08)', 
              border: '0.5px solid rgba(239, 68, 68, 0.25)', 
              color: 'var(--color-red-700)',
              borderRadius: '6px',
              fontSize: '12px'
            }}>
              Error executing models: {calcError}
            </div>
          )}

          {/* Tabs Bar */}
          <div className="dashboard-tabs" style={{ display: 'flex', gap: '16px', borderBottom: '1px solid var(--color-border)', marginTop: '16px' }}>
            <button
              className={`tab-btn ${activeTab === 'parent' ? 'active' : ''}`}
              onClick={() => setActiveTab('parent')}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: activeTab === 'parent' ? '2px solid var(--color-brand-600)' : '2px solid transparent',
                padding: '8px 16px',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                color: activeTab === 'parent' ? 'var(--color-brand-600)' : 'var(--color-text-500)',
                transition: 'all 0.15s ease'
              }}
            >
              Parent Compound Fate
            </button>
            <button
              className={`tab-btn ${activeTab === 'transformation' ? 'active' : ''}`}
              onClick={() => setActiveTab('transformation')}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: activeTab === 'transformation' ? '2px solid var(--color-brand-600)' : '2px solid transparent',
                padding: '8px 16px',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                color: activeTab === 'transformation' ? 'var(--color-brand-600)' : 'var(--color-text-500)',
                transition: 'all 0.15s ease'
              }}
            >
              Transformation Products
            </button>
            <button
              className={`tab-btn ${activeTab === 'regulatory' ? 'active' : ''}`}
              onClick={() => setActiveTab('regulatory')}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: activeTab === 'regulatory' ? '2px solid var(--color-brand-600)' : '2px solid transparent',
                padding: '8px 16px',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                color: activeTab === 'regulatory' ? 'var(--color-brand-600)' : 'var(--color-text-500)',
                transition: 'all 0.15s ease'
              }}
            >
              Registration Risk
            </button>
          </div>
        </div>

        {/* Tab 1: Parent Fate Profile */}
        {activeTab === 'parent' && selectedFate && (
          <>
            {/* PBT/vPvB scorecard */}
            <div className="card" style={{ 
              background: 'var(--color-surface)',
              border: '0.5px solid var(--color-border)',
              borderRadius: '8px',
              padding: '16px'
            }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase', marginBottom: '12px', letterSpacing: '0.05em' }}>
                REACH Annex XIII PBT & vPvB Scorecard
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', marginBottom: '16px' }}>
                {[
                  { name: 'P (Persistent)', active: selectedFate.pbt.p, desc: 'DT50 soil > 120 days' },
                  { name: 'vP (very Persistent)', active: selectedFate.pbt.vp, desc: 'DT50 soil > 180 days' },
                  { name: 'B (Bioaccumulative)', active: selectedFate.pbt.b, desc: 'BCF > 2000 or Kow > 4.5' },
                  { name: 'vB (very Bioaccumulative)', active: selectedFate.pbt.vb, desc: 'BCF > 5000' },
                  { name: 'T (Toxic)', active: selectedFate.pbt.t, desc: 'Aquatic EC50/LC50 < 0.1 mg/L' }
                ].map((item, idx) => (
                  <div key={idx} style={{ 
                    padding: '10px', 
                    borderRadius: '6px', 
                    background: item.active ? 'rgba(239, 68, 68, 0.06)' : 'rgba(16, 185, 129, 0.04)',
                    border: item.active ? '0.5px solid rgba(239, 68, 68, 0.2)' : '0.5px solid rgba(16, 185, 129, 0.15)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    textAlign: 'center'
                  }}>
                    <span style={{ 
                       fontSize: '11px', 
                       fontWeight: 700, 
                       color: item.active ? 'var(--color-red-700)' : 'var(--color-brand-700)' 
                    }}>
                      {item.active ? 'ACTIVE' : 'CLEAR'}
                    </span>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)', marginTop: '4px' }}>
                      {item.name}
                    </span>
                    <span style={{ fontSize: '9px', color: 'var(--color-text-400)', marginTop: '2px' }}>
                      {item.desc}
                    </span>
                  </div>
                ))}
              </div>

              <div style={{ 
                padding: '10px 14px', 
                borderRadius: '6px', 
                background: selectedFate.pbt.verdict === 'Not PBT/vPvB' || selectedFate.pbt.verdict === 'Low Risk'
                  ? 'rgba(16, 185, 129, 0.06)'
                  : 'rgba(239, 68, 68, 0.06)',
                border: selectedFate.pbt.verdict === 'Not PBT/vPvB' || selectedFate.pbt.verdict === 'Low Risk'
                  ? '0.5px solid rgba(16, 185, 129, 0.2)'
                  : '0.5px solid rgba(239, 68, 68, 0.2)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-700)' }}>
                  Overall PBT Verdict
                </span>
                <span style={{ 
                  fontSize: '12px', 
                  fontWeight: 700, 
                  color: selectedFate.pbt.verdict === 'Not PBT/vPvB' || selectedFate.pbt.verdict === 'Low Risk'
                    ? 'var(--color-brand-700)'
                    : 'var(--color-red-700)'
                }}>
                  {selectedFate.pbt.verdict}
                </span>
              </div>
            </div>

            {/* Mechanistic Systemic Mobility Card */}
            {selectedSmiles && <MobilityCard smiles={selectedSmiles} />}

            {/* Fate endpoint cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
              {/* DT50 Soil */}
              <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '14px' }}>
                <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-400)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Soil DT50
                </div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--color-text-900)', marginTop: '4px' }}>
                  {getNumeric(selectedFate.dt50_soil)?.toFixed(1) ?? '\u2014'} <span style={{ fontSize: '12px', fontWeight: 400 }}>days</span>
                </div>
                {renderUqBadge(selectedFate.dt50_soil)}
                {getNumeric(selectedFate.dt50_soil) != null && renderThresholdBar('Persistence', getNumeric(selectedFate.dt50_soil)!, 120, 'days')}
              </div>

              {/* Koc */}
              <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '14px' }}>
                <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-400)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Koc (Sorption)
                </div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--color-text-900)', marginTop: '4px' }}>
                  {getNumeric(selectedFate.koc)?.toFixed(0) ?? '\u2014'} <span style={{ fontSize: '12px', fontWeight: 400 }}>L/kg</span>
                </div>
                {renderUqBadge(selectedFate.koc)}
              </div>

              {/* BCF */}
              <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '14px' }}>
                <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-400)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  BCF (Bioconcentration)
                </div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--color-text-900)', marginTop: '4px' }}>
                  {getNumeric(selectedFate.bcf)?.toFixed(0) ?? '\u2014'} <span style={{ fontSize: '12px', fontWeight: 400 }}>L/kg</span>
                </div>
                {renderUqBadge(selectedFate.bcf)}
                {getNumeric(selectedFate.bcf) != null && renderThresholdBar('Bioaccumulation', getNumeric(selectedFate.bcf)!, 2000, 'L/kg')}
              </div>

              {/* Log Kow */}
              <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '14px' }}>
                <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-400)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Log Kow
                </div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--color-text-900)', marginTop: '4px' }}>
                  {getNumeric(selectedFate.log_kow)?.toFixed(2) ?? '\u2014'}
                </div>
                {renderUqBadge(selectedFate.log_kow)}
              </div>

              {/* Henry's Law */}
              <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '14px' }}>
                <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-400)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {"Henry's Law Constant"}
                </div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--color-text-900)', marginTop: '4px' }}>
                  {getNumeric(selectedFate.henry) != null ? getNumeric(selectedFate.henry)!.toExponential(2) : '\u2014'} <span style={{ fontSize: '12px', fontWeight: 400 }}>Pa m3/mol</span>
                </div>
                {renderUqBadge(selectedFate.henry)}
              </div>

              {/* GUS Leaching */}
              <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '14px' }}>
                <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-400)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  GUS Leaching Index
                </div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--color-text-900)', marginTop: '4px' }}>
                  {getNumeric(selectedFate.gus)?.toFixed(2) ?? '\u2014'}
                </div>
                <div style={{ 
                  marginTop: '6px',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: selectedFate.gus.class === 'leacher' ? 'var(--color-red-600)' 
                    : selectedFate.gus.class === 'transition' ? 'var(--color-amber-600)' 
                    : 'var(--color-brand-600)'
                }}>
                  {selectedFate.gus.class === 'leacher' ? 'Leacher (GUS > 2.8)'
                   : selectedFate.gus.class === 'transition' ? 'Transitional (1.8\u20132.8)'
                   : 'Non-leacher (GUS < 1.8)'}
                </div>
                {getNumeric(selectedFate.gus) != null && renderThresholdBar('Leaching', getNumeric(selectedFate.gus)!, 2.8, '')}
              </div>
            </div>

            {/* Speciation Curve Chart */}
            {selectedSmiles && (
              <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '16px' }}>
                <SpeciationCurve smiles={selectedSmiles} />
              </div>
            )}
          </>
        )}

        {activeTab === 'parent' && !selectedFate && !fateLoading && (
          <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '40px', textAlign: 'center' }}>
            <div style={{ fontSize: '14px', color: 'var(--color-text-400)' }}>
              Select a compound to view environmental fate predictions.
            </div>
          </div>
        )}

        {/* Tab 2: Transformation Products */}
        {activeTab === 'transformation' && (
          <>
            <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '14px' }}>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-600)' }}>Routes:</div>
                {['abiotic', 'metabolic'].map(route => (
                  <label key={route} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={routes.includes(route)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setRoutes([...routes, route]);
                        } else {
                          setRoutes(routes.filter(r => r !== route));
                        }
                      }}
                    />
                    {route.charAt(0).toUpperCase() + route.slice(1)}
                  </label>
                ))}
                {['soil_microbial', 'photolysis', 'hydrolysis'].map((src) => (
                  <label key={src} style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={sources.includes(src)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSources([...sources, src]);
                        } else {
                          setSources(sources.filter(s => s !== src));
                        }
                      }}
                    />
                    {src.replace('_', ' ')}
                  </label>
                ))}
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-600)', marginLeft: '16px' }}>Max depth:</div>
                <select 
                  value={maxDepth} 
                  onChange={(e) => setMaxDepth(Number(e.target.value))}
                  style={{ fontSize: '12px', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--color-border)' }}
                >
                  <option value={1}>1</option>
                  <option value={2}>2</option>
                  <option value={3}>3</option>
                </select>
                <button
                  onClick={() => {
                    if (selectedSmiles) {
                      predictTP(selectedSmiles, routes, maxDepth, sources).catch(console.error);
                    }
                  }}
                  disabled={tpLoading || !selectedSmiles}
                  style={{
                    fontSize: '12px',
                    padding: '4px 12px',
                    borderRadius: '6px',
                    border: 'none',
                    background: 'var(--color-brand-600)',
                    color: 'white',
                    cursor: tpLoading ? 'wait' : 'pointer',
                    fontWeight: 600,
                    opacity: tpLoading ? 0.6 : 1
                  }}
                >
                  {tpLoading ? 'Running...' : 'Run Prediction'}
                </button>
              </div>
            </div>

            {tpError && (
              <div style={{ padding: '12px', background: 'rgba(239,68,68,0.08)', border: '0.5px solid rgba(239,68,68,0.25)', color: 'var(--color-red-700)', borderRadius: '6px', fontSize: '12px' }}>
                {tpError}
              </div>
            )}

            {currentTpGraph && (
              <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '16px', minHeight: '400px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase', marginBottom: '12px', letterSpacing: '0.05em' }}>
                  Transformation Pathway ({currentTpGraph.nodes.length} products)
                </div>
                <PathwayTree
                  graph={currentTpGraph}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={(node) => setSelectedNodeId(node.id)}
                />
              </div>
            )}

            {selectedNodeDetails && (
              <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '16px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase', marginBottom: '12px', letterSpacing: '0.05em' }}>
                  Metabolite Inspector
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--color-text-400)' }}>SMILES</div>
                    <div style={{ fontSize: '11px', fontFamily: 'monospace', wordBreak: 'break-all', marginTop: '2px' }}>{selectedNodeDetails.smiles}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--color-text-400)' }}>Formation Rule</div>
                    <div style={{ fontSize: '11px', marginTop: '2px' }}>{selectedNodeDetails.rule}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--color-text-400)' }}>Probability</div>
                    <div style={{ fontSize: '11px', marginTop: '2px' }}>{(selectedNodeDetails.probability * 100).toFixed(1)}%</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--color-text-400)' }}>Risk Flag</div>
                    <div style={{ fontSize: '11px', marginTop: '2px', fontWeight: 600, color: selectedNodeDetails.risk_flag ? 'var(--color-red-600)' : 'var(--color-brand-600)' }}>
                      {selectedNodeDetails.risk_flag ? 'Flagged (exceeds parent)' : 'OK'}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {!currentTpGraph && !tpLoading && (
              <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '40px', textAlign: 'center' }}>
                <div style={{ fontSize: '14px', color: 'var(--color-text-400)' }}>
                  Click "Run Prediction" to generate transformation products.
                </div>
              </div>
            )}
          </>
        )}

        {/* Tab 3: Registration Risk Scorecard */}
        {activeTab === 'regulatory' && (
          <div className="card" style={{ 
            background: 'var(--color-surface)',
            border: '0.5px solid var(--color-border)',
            borderRadius: '8px',
            overflow: 'hidden'
          }}>
            <Scorecard smiles={selectedSmiles || undefined} autoFetch={true} compact={false} />
          </div>
        )}
      </div>
    </div>
  );
}
