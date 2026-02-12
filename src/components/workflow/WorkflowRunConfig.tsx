import { useState } from 'react';
import { useWorkflowStore } from '../../store/workflowStore';

export function WorkflowRunConfig() {
  const weights = useWorkflowStore((s) => s.weights);
  const setWeight = useWorkflowStore((s) => s.setWeight);
  const isRunning = useWorkflowStore((s) => s.isRunning);
  
  const selectedWorkflowType = useWorkflowStore((s) => s.selectedWorkflowType);
  const selectedReceptorPreset = useWorkflowStore((s) => s.selectedReceptorPreset);
  const setSelectedReceptorPreset = useWorkflowStore((s) => s.setSelectedReceptorPreset);
  const dockingParams = useWorkflowStore((s) => s.dockingParams);
  const setDockingParams = useWorkflowStore((s) => s.setDockingParams);
  const libraryPrepParams = useWorkflowStore((s) => s.libraryPrepParams);
  const setLibraryPrepParams = useWorkflowStore((s) => s.setLibraryPrepParams);
  const uploadedFile = useWorkflowStore((s) => s.uploadedFile);
  const setUploadedFile = useWorkflowStore((s) => s.setUploadedFile);
  const structureColumn = useWorkflowStore((s) => s.structureColumn);
  const setStructureColumn = useWorkflowStore((s) => s.setStructureColumn);
  const detectedCpuCores = useWorkflowStore((s) => s.detectedCpuCores);

  const getCompoundCount = () => {
    if (!uploadedFile) return 0;
    if (uploadedFile.extension === 'sdf') {
      const matches = uploadedFile.contents.match(/\$\$\$\$/g);
      return matches ? matches.length : 0;
    } else {
      const lines = uploadedFile.contents.split('\n').map(l => l.trim()).filter(Boolean);
      if (uploadedFile.extension === 'csv' && lines.length > 0) {
        return lines.length - 1;
      }
      return lines.length;
    }
  };

  const [expanded, setExpanded] = useState(true);
  const [advancedExpanded, setAdvancedExpanded] = useState(true);
  const [prepExpanded, setPrepExpanded] = useState(true);
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const name = file.name;
    const extension = name.split('.').pop()?.toLowerCase() || '';
    if (!['smi', 'smiles', 'sdf', 'csv'].includes(extension)) {
      alert('Unsupported file format. Please upload .smi, .smiles, .sdf, or .csv files.');
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const contents = event.target?.result as string;
      setUploadedFile({ name, contents, extension });
      
      if (extension === 'csv') {
        const firstLine = contents.split('\n')[0] || '';
        const headers = firstLine.split(',').map(h => h.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
        setCsvHeaders(headers);
        if (headers.length > 0) {
          setStructureColumn(headers[0]);
        }
      } else {
        setCsvHeaders([]);
        setStructureColumn('');
      }
    };
    reader.readAsText(file);
  };

  const sliders = [
    {
      key: 'pesticide_likeness',
      label: 'Pesticide-likeness',
      desc: 'Tice rules compliance and structural penalties',
      color: 'var(--color-brand-600)',
    },
    {
      key: 'selectivity',
      label: 'Off-Target Selectivity',
      desc: 'Target vs beneficial organism safety margins',
      color: 'var(--color-blue-600)',
    },
    {
      key: 'resistance',
      label: 'Resistance Risk',
      desc: 'HRAC/IRAC/FRAC group cross-resistance risks',
      color: 'var(--color-amber-600)',
    },
    {
      key: 'toxicity',
      label: 'Toxicity Profile',
      desc: 'Apicultural, avian, and mammalian safety margins',
      color: 'var(--color-red-600)',
    },
    {
      key: 'environmental_safety',
      label: 'Environmental Safety',
      desc: 'Soil degradation persistence and leaching fate',
      color: 'var(--color-teal-600)',
    },
  ];

  return (
    <div
      className="run-config-sidebar"
      style={{
        width: '320px',
        maxHeight: '100%',
        overflowY: 'auto',
        background: 'var(--color-surface)',
        border: '0.5px solid var(--color-border)',
        borderRadius: '12px',
        padding: '16px',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        boxSizing: 'border-box',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '0.5px solid var(--color-border-subtle)',
          paddingBottom: '10px',
        }}
      >
        <span
          style={{
            fontSize: '11px',
            fontWeight: 700,
            letterSpacing: '0.05em',
            color: 'var(--color-text-500)',
            textTransform: 'uppercase',
          }}
        >
          Run Configuration
        </span>
        {isRunning && (
          <span
            style={{
              fontSize: '10px',
              color: 'var(--color-text-400)',
              fontStyle: 'italic',
            }}
          >
            Locked during run
          </span>
        )}
      </div>

      {selectedWorkflowType === 'active_learning' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {uploadedFile ? (
            <div style={{
              padding: '12px',
              borderRadius: '8px',
              background: 'var(--color-brand-100)',
              border: '0.5px solid var(--color-brand-600)',
              color: 'var(--color-brand-900)',
              fontSize: '11px',
              lineHeight: '1.4',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              boxShadow: 'var(--shadow-sm)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                <span>📥 Imported Screening Library</span>
              </div>
              <div>
                A dataset of <strong>{getCompoundCount()}</strong> compounds (<code>{uploadedFile.name}</code>) has been uploaded and will be used.
              </div>
              {!isRunning && (
                <button
                  onClick={() => {
                    setUploadedFile(null);
                    setStructureColumn('');
                  }}
                  style={{
                    fontSize: '9px',
                    color: 'var(--color-red-500)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    alignSelf: 'flex-start',
                    marginTop: '4px',
                    textDecoration: 'underline',
                    padding: 0
                  }}
                >
                  Remove dataset
                </button>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                Screening Library
              </span>
              <div
                style={{
                  border: '1px dashed var(--color-border)',
                  borderRadius: '6px',
                  padding: '12px',
                  textAlign: 'center',
                  background: 'var(--color-bg)',
                  cursor: isRunning ? 'default' : 'pointer',
                  fontSize: '11px',
                  color: 'var(--color-text-600)',
                  position: 'relative',
                }}
                onClick={() => !isRunning && document.getElementById('active-learning-file-input')?.click()}
              >
                <div>
                  <span>Click to upload library</span>
                  <div style={{ fontSize: '9.5px', color: 'var(--color-text-400)', marginTop: '4.5px' }}>
                    Supports .smi, .smiles, .sdf, or .csv
                  </div>
                </div>
                <input
                  type="file"
                  id="active-learning-file-input"
                  accept=".smi,.smiles,.sdf,.csv"
                  style={{ display: 'none' }}
                  disabled={isRunning}
                  onChange={handleFileUpload}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Scoring Weights Section */}
      {selectedWorkflowType !== 'library_prep' && (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div
            onClick={() => setExpanded(!expanded)}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              cursor: 'pointer',
              padding: '8px 0',
              userSelect: 'none',
            }}
          >
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)' }}>
              ⚖ Scoring Weights
            </span>
            <span
              style={{
                fontSize: '10px',
                color: 'var(--color-text-400)',
                transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s ease',
              }}
            >
              ▼
            </span>
          </div>

          {expanded && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
                marginTop: '8px',
                paddingLeft: '4px',
              }}
            >
              {sliders.map((s) => {
                const val = weights[s.key] ?? 100;
                return (
                  <div key={s.key} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                        {s.label}
                      </span>
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '11px',
                          fontWeight: 700,
                          color: s.color,
                          background: 'var(--color-bg)',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          border: '0.5px solid var(--color-border)',
                        }}
                      >
                        {val}
                      </span>
                    </div>
                    <span style={{ fontSize: '9.5px', color: 'var(--color-text-400)', lineHeight: '1.2' }}>
                      {s.desc}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        step="5"
                        value={val}
                        disabled={isRunning}
                        onChange={(e) => setWeight(s.key, parseInt(e.target.value, 10))}
                        style={{
                          flex: 1,
                          height: '4px',
                          background: 'var(--color-bg)',
                          borderRadius: '2px',
                          appearance: 'none',
                          outline: 'none',
                          cursor: isRunning ? 'default' : 'pointer',
                          opacity: isRunning ? 0.6 : 1,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Target Docking Settings (Bioisostere Opt only) */}
      {selectedWorkflowType === 'bioisostere_opt' && (
        <div style={{ display: 'flex', flexDirection: 'column', borderTop: '0.5px solid var(--color-border-subtle)', paddingTop: '10px' }}>
          <div
            onClick={() => setAdvancedExpanded(!advancedExpanded)}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              cursor: 'pointer',
              padding: '8px 0',
              userSelect: 'none',
            }}
          >
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)' }}>
              ⚙️ Docking Parameters
            </span>
            <span
              style={{
                fontSize: '10px',
                color: 'var(--color-text-400)',
                transform: advancedExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s ease',
              }}
            >
              ▼
            </span>
          </div>

          {advancedExpanded && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
                marginTop: '8px',
                paddingLeft: '4px',
              }}
            >
              {/* Receptor Selector */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                  Target Receptor
                </span>
                <select
                  value={selectedReceptorPreset}
                  disabled={isRunning}
                  onChange={(e) => setSelectedReceptorPreset(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    borderRadius: '6px',
                    border: '0.5px solid var(--color-border)',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text-800)',
                    fontSize: '11px',
                    fontWeight: 500,
                    outline: 'none',
                    cursor: isRunning ? 'default' : 'pointer',
                  }}
                >
                  <option value="als">ALS (Acetolactate Synthase)</option>
                  <option value="accase">ACCase (Acetyl-CoA Carboxylase)</option>
                  <option value="epsps">EPSPS (EPSP Synthase)</option>
                  <option value="gs">GS (Glutamine Synthetase)</option>
                  <option value="hppd">HPPD (4-HPPD)</option>
                  <option value="ppo">PPO (Protoporphyrinogen Oxidase)</option>
                  <option value="ps2">PSII (Photosystem II)</option>
                  <option value="sdh">SDH (Succinate Dehydrogenase)</option>
                </select>
              </div>

              {/* Vina Exhaustiveness */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                    Exhaustiveness
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 700, color: 'var(--color-brand-600)' }}>
                    {dockingParams.exhaustiveness}
                  </span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="16"
                  step="1"
                  value={dockingParams.exhaustiveness}
                  disabled={isRunning}
                  onChange={(e) => setDockingParams({ exhaustiveness: parseInt(e.target.value, 10) })}
                  style={{
                    flex: 1,
                    height: '4px',
                    background: 'var(--color-bg)',
                    borderRadius: '2px',
                    appearance: 'none',
                    outline: 'none',
                    cursor: isRunning ? 'default' : 'pointer',
                  }}
                />
              </div>

              {/* Vina Num Modes */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                    Max Poses
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 700, color: 'var(--color-brand-600)' }}>
                    {dockingParams.numModes}
                  </span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="20"
                  step="1"
                  value={dockingParams.numModes}
                  disabled={isRunning}
                  onChange={(e) => setDockingParams({ numModes: parseInt(e.target.value, 10) })}
                  style={{
                    flex: 1,
                    height: '4px',
                    background: 'var(--color-bg)',
                    borderRadius: '2px',
                    appearance: 'none',
                    outline: 'none',
                    cursor: isRunning ? 'default' : 'pointer',
                  }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Library Preparation Settings (library_prep only) */}
      {selectedWorkflowType === 'library_prep' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Header */}
          <div
            onClick={() => setPrepExpanded(!prepExpanded)}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              cursor: 'pointer',
              padding: '8px 0',
              userSelect: 'none',
            }}
          >
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)' }}>
              📋 Prep Configuration
            </span>
            <span
              style={{
                fontSize: '10px',
                color: 'var(--color-text-400)',
                transform: prepExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s ease',
              }}
            >
              ▼
            </span>
          </div>

          {prepExpanded && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', paddingLeft: '4px' }}>
              {/* File Upload Zone */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                  Input Library File
                </span>
                <div
                  style={{
                    border: '1px dashed var(--color-border)',
                    borderRadius: '6px',
                    padding: '12px',
                    textAlign: 'center',
                    background: 'var(--color-bg)',
                    cursor: isRunning ? 'default' : 'pointer',
                    fontSize: '11px',
                    color: 'var(--color-text-600)',
                    position: 'relative',
                  }}
                  onClick={() => !isRunning && document.getElementById('library-file-input')?.click()}
                >
                  {uploadedFile ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontWeight: 600, color: 'var(--color-brand-700)' }}>
                        ✓ {uploadedFile.name}
                      </span>
                      <span style={{ fontSize: '9px', color: 'var(--color-text-400)' }}>
                        ({uploadedFile.extension.toUpperCase()} format)
                      </span>
                      {!isRunning && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setUploadedFile(null);
                            setStructureColumn('');
                          }}
                          style={{
                            fontSize: '9px',
                            color: 'var(--color-red-500)',
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            marginTop: '4px',
                            textDecoration: 'underline',
                          }}
                        >
                          Remove file
                        </button>
                      )}
                    </div>
                  ) : (
                    <div>
                      <span>Click to upload library</span>
                      <div style={{ fontSize: '9.5px', color: 'var(--color-text-400)', marginTop: '4.5px' }}>
                        Supports .smi, .smiles, .sdf, or .csv
                      </div>
                    </div>
                  )}
                  <input
                    type="file"
                    id="library-file-input"
                    accept=".smi,.smiles,.sdf,.csv"
                    style={{ display: 'none' }}
                    disabled={isRunning}
                    onChange={handleFileUpload}
                  />
                </div>

                {/* CSV Structure Column Selector */}
                {uploadedFile && uploadedFile.extension === 'csv' && csvHeaders.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                    <span style={{ fontSize: '10px', color: 'var(--color-text-600)' }}>
                      Structure (SMILES) Column:
                    </span>
                    <select
                      value={structureColumn}
                      disabled={isRunning}
                      onChange={(e) => setStructureColumn(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        border: '0.5px solid var(--color-border)',
                        background: 'var(--color-surface)',
                        color: 'var(--color-text-800)',
                        fontSize: '10px',
                        outline: 'none',
                        cursor: isRunning ? 'default' : 'pointer',
                      }}
                    >
                      {csvHeaders.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* Alert Filters */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', borderTop: '0.5px solid var(--color-border-subtle)', paddingTop: '10px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                  Structure Filters
                </span>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--color-text-700)', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={libraryPrepParams.filterPains}
                    disabled={isRunning}
                    onChange={(e) => setLibraryPrepParams({ filterPains: e.target.checked })}
                    style={{ cursor: isRunning ? 'default' : 'pointer' }}
                  />
                  PAINS (Interference) Alerts
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--color-text-700)', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={libraryPrepParams.filterReactive}
                    disabled={isRunning}
                    onChange={(e) => setLibraryPrepParams({ filterReactive: e.target.checked })}
                    style={{ cursor: isRunning ? 'default' : 'pointer' }}
                  />
                  Reactive / Toxicophore Alerts
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--color-text-700)', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={libraryPrepParams.filterHerbicideLikeness}
                    disabled={isRunning}
                    onChange={(e) => setLibraryPrepParams({ filterHerbicideLikeness: e.target.checked })}
                    style={{ cursor: isRunning ? 'default' : 'pointer' }}
                  />
                  Herbicide-likeness (Tice Rules)
                </label>
              </div>

              {/* Diversity Clustering */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', borderTop: '0.5px solid var(--color-border-subtle)', paddingTop: '10px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                  Clustering Method
                </span>
                <select
                  value={libraryPrepParams.clusteringAlgorithm || 'morgan'}
                  disabled={isRunning}
                  onChange={(e) => setLibraryPrepParams({ clusteringAlgorithm: e.target.value as 'morgan' | 'bemis_murcko' })}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    borderRadius: '6px',
                    border: '0.5px solid var(--color-border)',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text-800)',
                    fontSize: '11px',
                    fontWeight: 500,
                    outline: 'none',
                    cursor: isRunning ? 'default' : 'pointer',
                  }}
                >
                  <option value="morgan">ECFP/Morgan Fingerprints (Butina & MaxMin)</option>
                  <option value="bemis_murcko">Bemis-Murcko Scaffold (Round-Robin)</option>
                </select>
              </div>

              {libraryPrepParams.clusteringAlgorithm === 'morgan' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                      Similarity Threshold (Tanimoto)
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 700, color: 'var(--color-brand-600)' }}>
                      {libraryPrepParams.diversityThreshold.toFixed(2)}
                    </span>
                  </div>
                  <span style={{ fontSize: '9px', color: 'var(--color-text-400)', lineHeight: '1.2' }}>
                    Molecules with Tanimoto similarity higher than this will be filtered out to ensure diversity.
                  </span>
                  <input
                    type="range"
                    min="0.3"
                    max="1.0"
                    step="0.05"
                    value={libraryPrepParams.diversityThreshold}
                    disabled={isRunning}
                    onChange={(e) => setLibraryPrepParams({ diversityThreshold: parseFloat(e.target.value) })}
                    style={{
                      height: '4px',
                      background: 'var(--color-bg)',
                      borderRadius: '2px',
                      appearance: 'none',
                      outline: 'none',
                      cursor: isRunning ? 'default' : 'pointer',
                    }}
                  />
                </div>
              )}

              {/* Target Subset Size */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                    Target Subset Size
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 700, color: 'var(--color-brand-600)' }}>
                    {libraryPrepParams.targetSize}
                  </span>
                </div>
                <input
                  type="range"
                  min="50"
                  max="2000"
                  step="50"
                  value={libraryPrepParams.targetSize}
                  disabled={isRunning}
                  onChange={(e) => setLibraryPrepParams({ targetSize: parseInt(e.target.value, 10) })}
                  style={{
                    height: '4px',
                    background: 'var(--color-bg)',
                    borderRadius: '2px',
                    appearance: 'none',
                    outline: 'none',
                    cursor: isRunning ? 'default' : 'pointer',
                  }}
                />
              </div>

              {/* CPU Workers (Cores) */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                    CPU Workers (Cores)
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 700, color: 'var(--color-brand-600)' }}>
                    {libraryPrepParams.numWorkers} / {detectedCpuCores}
                  </span>
                </div>
                <input
                  type="range"
                  min="1"
                  max={detectedCpuCores || 4}
                  step="1"
                  value={libraryPrepParams.numWorkers}
                  disabled={isRunning}
                  onChange={(e) => setLibraryPrepParams({ numWorkers: parseInt(e.target.value, 10) })}
                  style={{
                    height: '4px',
                    background: 'var(--color-bg)',
                    borderRadius: '2px',
                    appearance: 'none',
                    outline: 'none',
                    cursor: isRunning ? 'default' : 'pointer',
                  }}
                />
              </div>

              {/* Target pH */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', borderTop: '0.5px solid var(--color-border-subtle)', paddingTop: '10px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                  3D Protonation Preset
                </span>
                <select
                  value={libraryPrepParams.protonationPh}
                  disabled={isRunning}
                  onChange={(e) => setLibraryPrepParams({ protonationPh: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    borderRadius: '6px',
                    border: '0.5px solid var(--color-border)',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text-800)',
                    fontSize: '11px',
                    fontWeight: 500,
                    outline: 'none',
                    cursor: isRunning ? 'default' : 'pointer',
                  }}
                >
                  <option value="7.4">Physiological Screening (pH 7.4)</option>
                  <option value="5.5">Soil Transport (pH 5.5)</option>
                  <option value="7.0">Neutral Assay (pH 7.0)</option>
                </select>
              </div>

              {/* Output Format */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)' }}>
                  Export Format
                </span>
                <select
                  value={libraryPrepParams.exportFormat}
                  disabled={isRunning}
                  onChange={(e) => setLibraryPrepParams({ exportFormat: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    borderRadius: '6px',
                    border: '0.5px solid var(--color-border)',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text-800)',
                    fontSize: '11px',
                    fontWeight: 500,
                    outline: 'none',
                    cursor: isRunning ? 'default' : 'pointer',
                  }}
                >
                  <option value="sdf">Multi-compound SDF (.sdf)</option>
                  <option value="csv">Summary CSV (.csv)</option>
                  <option value="smiles">SMILES List (.smi)</option>
                </select>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
