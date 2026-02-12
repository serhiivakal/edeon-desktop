import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useUIStore } from '../../store/uiStore';
import { useCompoundStore } from '../../store/compoundStore';
import { useProjectStore } from '../../store/projectStore';

interface EndpointDelta {
  endpoint: string;
  original_value: number;
  original_ci_lower?: number;
  original_ci_upper?: number;
  original_ad_status: string;
  transformed_value: number;
  transformed_ci_lower?: number;
  transformed_ci_upper?: number;
  transformed_ad_status: string;
  delta: number;
  ad_warning: boolean;
}

interface BioisostereSuggestion {
  rule: {
    rule_id: string;
    pattern_smarts: string;
    replacement_smarts: string;
    reaction_smarts: string;
    source: string;
    source_reference?: string;
    direction_notes?: string;
    occurrence_frequency: number;
  };
  original_smiles: string;
  transformed_smiles: string;
  composite_score: number;
  deltas: EndpointDelta[];
}

interface Props {
  compound: any;
  expanded: boolean;
  onToggle: () => void;
}

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

export const BioisostereCarousel: React.FC<Props> = ({ compound, expanded, onToggle }) => {
  const [suggestions, setSuggestions] = useState<BioisostereSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const [isApplying, setIsApplying] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    setActiveIndex(0);
  }, [compound?.id]);

  useEffect(() => {
    if (!compound || !compound.smiles || !expanded) {
      return;
    }
    
    let active = true;
    setLoading(true);
    setError(null);
    
    const weights = {
      bee_acute_oral_ld50: 0.20,
      fish_acute_lc50: 0.15,
      rat_acute_oral_ld50: 0.15,
      mutagenicity_ames: -0.10,
      skin_sensitization: -0.05,
      soil_dt50: -0.10,
      bcf: -0.10,
    };
    
    invoke<BioisostereSuggestion[]>('bioisostere_suggest', {
      smiles: compound.smiles,
      topN: 30,
      sortBy: 'composite',
      weights
    })
      .then((res) => {
        if (active) {
          setSuggestions(res || []);
          setError(null);
        }
      })
      .catch((err) => {
        console.error('[BioisostereCarousel] Suggestion failed:', err);
        if (active) {
          setSuggestions([]);
          setError(String(err));
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
      
    return () => {
      active = false;
    };
  }, [compound?.smiles, expanded]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  const activeSuggestion = suggestions[activeIndex];
  const { svg: suggestionSvg, loading: suggestionLoading, error: suggestionError } = useStructureSvg(activeSuggestion?.transformed_smiles);

  if (!compound) return null;

  const handleApply = async (suggestion: BioisostereSuggestion) => {
    if (!activeProjectId || isApplying || !suggestion) return;
    setIsApplying(true);
    try {
      const name = `${compound.name} Analog ${activeIndex + 1}`;
      const added = await invoke<any>('add_compound', {
        projectId: activeProjectId,
        name,
        smiles: suggestion.transformed_smiles,
      });
      
      // Refresh library in compoundStore
      await useCompoundStore.getState().fetchCompounds(activeProjectId);
      
      // Select the new compound
      useUIStore.getState().setSelectedCompound(added.id);
      
      setToast({ message: `Successfully added ${name} to project library!`, type: 'success' });
    } catch (err) {
      console.error('[BioisostereCarousel] Apply failed:', err);
      setToast({ message: `Failed to add analog: ${String(err)}`, type: 'error' });
    } finally {
      setIsApplying(false);
    }
  };

  const getFriendlyEndpointName = (ep: string): string => {
    const norm = ep.toLowerCase();
    if (norm.includes('bee_acute_oral')) return 'Bee Oral';
    if (norm.includes('bee_acute_contact')) return 'Bee Contact';
    if (norm.includes('fish_acute_lc50')) return 'Fish LC50';
    if (norm.includes('daphnia_acute_ec50')) return 'Daphnia EC50';
    if (norm.includes('rat_acute_oral_ld50')) return 'Rat Oral LD50';
    if (norm.includes('soil_dt50')) return 'Soil DT50';
    if (norm.includes('bcf')) return 'BCF (Bioaccum)';
    if (norm.includes('mutagenicity_ames')) return 'Ames Mutagen';
    if (norm.includes('skin_sensitization')) return 'Skin Sens';
    if (norm.includes('photostability_class')) return 'Photostability';
    if (norm.includes('logp')) return 'LogP';
    if (norm.includes('tpsa')) return 'TPSA';
    if (norm.includes('mol_weight')) return 'MW';
    return ep;
  };

  const formatValue = (endpoint: string, val: number): string => {
    if (val === null || val === undefined) return '—';
    const norm = endpoint.toLowerCase();
    if (norm.includes('logp')) return val.toFixed(2);
    if (norm.includes('tpsa')) return `${val.toFixed(1)} Å²`;
    if (norm.includes('mol_weight')) return `${val.toFixed(1)} g/mol`;
    if (norm.includes('soil_dt50')) return `${val.toFixed(1)} d`;
    if (norm.includes('bcf')) return `${val.toFixed(1)} L/kg`;
    
    if (norm.includes('ld50') || norm.includes('lc50') || norm.includes('ec50')) {
      if (val < 0.01) return val.toExponential(2);
      return val.toFixed(2);
    }
    
    if (norm.includes('ames') || norm.includes('sensitization')) {
      return `${(val * 100).toFixed(0)}%`;
    }
    
    return val.toFixed(2);
  };

  const formatDelta = (endpoint: string, delta: number): string => {
    if (delta === 0) return '0.0';
    const norm = endpoint.toLowerCase();
    const prefix = delta > 0 ? '+' : '';
    
    const isLog = norm.includes('ld50') || norm.includes('lc50') || norm.includes('ec50') || norm.includes('dt50');
    if (isLog) {
      return `${prefix}${delta.toFixed(2)} log`;
    }
    
    if (norm.includes('ames') || norm.includes('sensitization')) {
      return `${prefix}${(delta * 100).toFixed(0)}%`;
    }
    
    return `${prefix}${delta.toFixed(2)}`;
  };

  const isBetter = (endpoint: string, delta: number): boolean => {
    if (Math.abs(delta) < 0.01) return false;
    const norm = endpoint.toLowerCase();
    if (norm.includes('ld50') || norm.includes('lc50') || norm.includes('ec50')) {
      return delta > 0.01;
    }
    if (norm.includes('dt50') || norm.includes('bcf') || norm.includes('ames') || norm.includes('sensitization')) {
      return delta < -0.01;
    }
    if (norm === 'logp') {
      return delta < -0.01;
    }
    return false;
  };

  const isWorse = (endpoint: string, delta: number): boolean => {
    if (Math.abs(delta) < 0.01) return false;
    const norm = endpoint.toLowerCase();
    if (norm.includes('ld50') || norm.includes('lc50') || norm.includes('ec50')) {
      return delta < -0.01;
    }
    if (norm.includes('dt50') || norm.includes('bcf') || norm.includes('ames') || norm.includes('sensitization')) {
      return delta > 0.01;
    }
    if (norm === 'logp') {
      return delta > 0.01;
    }
    return false;
  };

  const getBadgeClassAndStyle = (endpoint: string, delta: number) => {
    if (isBetter(endpoint, delta)) {
      return { className: 'comp-badge badge-good', style: {} };
    }
    if (isWorse(endpoint, delta)) {
      return {
        className: 'comp-badge',
        style: {
          background: 'rgba(239, 68, 68, 0.08)',
          color: 'var(--color-red-700)',
          border: '0.5px solid rgba(239, 68, 68, 0.2)',
        }
      };
    }
    return { className: 'comp-badge badge-neutral', style: {} };
  };

  const getSuggestionName = (s: BioisostereSuggestion): string => {
    if (!s) return 'Bioisostere Analog';
    if (s.rule && s.rule.direction_notes) {
      return s.rule.direction_notes;
    }
    return `Bioisostere Rule ${s.rule.rule_id}`;
  };

  const getSuggestionRationale = (s: BioisostereSuggestion): string => {
    if (!s) return '';
    let text = `Sourced from ${s.rule.source.replace(/_/g, ' ')}`;
    if (s.rule.source_reference) {
      text += ` (${s.rule.source_reference})`;
    }
    text += `. Frequency: ${s.rule.occurrence_frequency}.`;
    return text;
  };

  return (
    <div className="collapsible-section">
      <div className="section-label collapsible-header" onClick={onToggle}>
        <span>BIOISOSTERE SUGGESTIONS</span>
        <span className="chevron">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="bioisostere-card">
          {loading ? (
            <div className="mini-structure-loading" style={{ height: '120px', display: 'flex', flexDirection: 'column', gap: '8px', justifyContent: 'center' }}>
              <div className="spinner"></div>
              <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>
                Computing suggestions & QSAR deltas...
              </span>
            </div>
          ) : error ? (
            <div className="mini-structure-error" style={{ height: '100px', padding: '12px', textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <span className="mini-structure-error-icon">✕</span>
              <span className="mini-structure-error-text" style={{ whiteSpace: 'normal', color: 'var(--color-red-600)' }}>
                Error: {error}
              </span>
            </div>
          ) : suggestions.length === 0 ? (
            <div className="mini-structure-error" style={{ height: '100px', padding: '12px', textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <span className="mini-structure-error-icon">💡</span>
              <span className="mini-structure-error-text" style={{ whiteSpace: 'normal', color: 'var(--color-text-400)' }}>
                No suggestions found for this compound.
              </span>
            </div>
          ) : (
            <>
              <div className="bioisostere-header">
                <span className="bioisostere-name">{getSuggestionName(activeSuggestion)}</span>
                <div className="carousel-controls">
                  <button 
                    className="carousel-arrow-btn" 
                    disabled={activeIndex === 0} 
                    onClick={(e) => { e.stopPropagation(); setActiveIndex(prev => prev - 1); }}
                  >
                    ◀
                  </button>
                  <span className="carousel-counter">{activeIndex + 1} / {suggestions.length}</span>
                  <button 
                    className="carousel-arrow-btn" 
                    disabled={activeIndex === suggestions.length - 1} 
                    onClick={(e) => { e.stopPropagation(); setActiveIndex(prev => prev + 1); }}
                  >
                    ▶
                  </button>
                </div>
              </div>
              
              <p className="bioisostere-rationale">{getSuggestionRationale(activeSuggestion)}</p>
              
              <div className="bioisostere-structure-container">
                {suggestionLoading ? (
                  <div className="mini-structure-loading">
                    <div className="spinner"></div>
                  </div>
                ) : suggestionError || !suggestionSvg ? (
                  <div className="mini-structure-error">
                    <span className="mini-structure-error-icon">✕</span>
                    <span className="mini-structure-error-text">2D Depiction Unavailable</span>
                  </div>
                ) : (
                  <div 
                    className="mini-structure-canvas selectable"
                    dangerouslySetInnerHTML={{ 
                      __html: suggestionSvg.replace(/<svg([^>]*)(width="[^"]*")([^>]*)(height="[^"]*")/, '<svg$1width="100%"$3height="100%"') 
                    }}
                  />
                )}
              </div>
              
              <div className="bioisostere-smiles-box">
                <span className="bioisostere-smiles-label">SMILES</span>
                <span className="bioisostere-smiles-value selectable">{activeSuggestion.transformed_smiles}</span>
              </div>
              
              <div className="bioisostere-comparison-table">
                <div className="comparison-header-row">
                  <span>QSAR METRIC</span>
                  <span>ORIGINAL</span>
                  <span>ANALOGUE</span>
                </div>
                
                {activeSuggestion.deltas && activeSuggestion.deltas.map((d: EndpointDelta) => {
                  const badge = getBadgeClassAndStyle(d.endpoint, d.delta);
                  return (
                    <div key={d.endpoint} className="comparison-row">
                      <span className="comp-label">{getFriendlyEndpointName(d.endpoint)}</span>
                      <span className="comp-val">{formatValue(d.endpoint, d.original_value)}</span>
                      <span className="comp-val" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span>{formatValue(d.endpoint, d.transformed_value)}</span>
                        {Math.abs(d.delta) >= 0.01 && (
                          <span className={badge.className} style={badge.style}>
                            {formatDelta(d.endpoint, d.delta)}
                          </span>
                        )}
                        {d.ad_warning && (
                          <span style={{ fontSize: '8px', cursor: 'help' }} title="Out of Applicability Domain">⚠️</span>
                        )}
                      </span>
                    </div>
                  );
                })}
              </div>

              <button 
                className="inspector-btn-primary" 
                style={{ width: '100%', marginTop: '10px' }}
                onClick={() => handleApply(activeSuggestion)}
                disabled={isApplying}
              >
                {isApplying ? 'Adding Compound...' : 'Apply Transformation →'}
              </button>

              {toast && (
                <div style={{
                  marginTop: '8px',
                  padding: '6px 10px',
                  borderRadius: '4px',
                  fontSize: '10px',
                  fontWeight: 500,
                  background: toast.type === 'success' ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                  border: toast.type === 'success' ? '0.5px solid rgba(16, 185, 129, 0.25)' : '0.5px solid rgba(239, 68, 68, 0.25)',
                  color: toast.type === 'success' ? 'var(--color-brand-700)' : 'var(--color-red-700)',
                  textAlign: 'center'
                }}>
                  {toast.message}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
