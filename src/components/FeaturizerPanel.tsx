import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useModelStore } from '../store/modelStore';
import { invoke } from '@tauri-apps/api/core';

// Hardcoded descriptions for common RDKit descriptors
const DESCRIPTOR_DESCRIPTIONS: Record<string, string> = {
  MolWt: "Average molecular weight of the compound.",
  MolLogP: "Wildman-Crippen octanol-water partition coefficient (logP) measuring lipophilicity.",
  TPSA: "Topological Polar Surface Area, estimating cellular permeability and absorption.",
  NumHDonors: "Number of Hydrogen Bond Donors (OH and NH groups).",
  NumHAcceptors: "Number of Hydrogen Bond Acceptors (O and N atoms).",
  NumRotatableBonds: "Number of rotatable single bonds, indicating molecular flexibility.",
  HeavyAtomCount: "Number of heavy (non-hydrogen) atoms.",
  NHOHCount: "Number of nitrogen-hydrogen or oxygen-hydrogen bonds.",
  NOCount: "Total number of nitrogen and oxygen atoms.",
  NumHeteroatoms: "Number of non-carbon, non-hydrogen atoms.",
  RingCount: "Total number of rings of any size.",
  BertzCT: "Bertz topological complexity index based on bond connectivity and heteroatoms.",
  BalabanJ: "Balaban's J index, a highly discriminating topological distance-based descriptor.",
  HallKierAlpha: "Kier and Hall alpha parameter for molecular shape modeling.",
  Ipc: "Information content of the coefficients of the characteristic polynomial (topological).",
  Kappa1: "First Kier shape index, describing molecular size and shape.",
  Kappa2: "Second Kier shape index, describing molecular spatial distribution.",
  Kappa3: "Third Kier shape index, describing structural branching features.",
  LabuteASA: "Labute's approximate surface area, modeling van der Waals contact area.",
  MaxEStateIndex: "Maximum electrotopological state (E-state) index of any atom.",
  MinEStateIndex: "Minimum electrotopological state (E-state) index of any atom.",
  MaxAbsEStateIndex: "Maximum absolute E-state index value.",
  MinAbsEStateIndex: "Minimum absolute E-state index value.",
  qed: "Quantitative Estimate of Drug-likeness (QED) score, ranging from 0 (poor) to 1 (excellent).",
  FractionCSP3: "Fraction of carbon atoms that are sp3 hybridized.",
  NumAliphaticRings: "Number of aliphatic rings in the structure.",
  NumAromaticRings: "Number of aromatic rings in the structure.",
  NumSaturatedRings: "Number of saturated (non-aromatic, non-olefinic) rings.",
  NumAmideBonds: "Number of amide linkages (O=C-N).",
  SPS: "Spatial Score (SPS) measuring structural complexity and 3D nature."
};

// Sorted master list of all 208 descriptors
const ALL_DESCRIPTORS = [
  "MaxAbsEStateIndex", "MaxEStateIndex", "MinAbsEStateIndex", "MinEStateIndex", "qed", "SPS", "MolWt", "HeavyAtomMolWt", "ExactMolWt", "NumValenceElectrons", "NumRadicalElectrons", "MaxPartialCharge", "MinPartialCharge", "MaxAbsPartialCharge", "MinAbsPartialCharge", "FpDensityMorgan1", "FpDensityMorgan2", "FpDensityMorgan3", "BCUT2D_MWHI", "BCUT2D_MWLOW", "BCUT2D_CHGHI", "BCUT2D_CHGLO", "BCUT2D_LOGPHI", "BCUT2D_LOGPLOW", "BCUT2D_MRHI", "BCUT2D_MRLOW", "AvgIpc", "BalabanJ", "BertzCT", "Chi0", "Chi0n", "Chi0v", "Chi1", "Chi1n", "Chi1v", "Chi2n", "Chi2v", "Chi3n", "Chi3v", "Chi4n", "Chi4v", "HallKierAlpha", "Ipc", "Kappa1", "Kappa2", "Kappa3", "LabuteASA", "PEOE_VSA1", "PEOE_VSA10", "PEOE_VSA11", "PEOE_VSA12", "PEOE_VSA13", "PEOE_VSA14", "PEOE_VSA2", "PEOE_VSA3", "PEOE_VSA4", "PEOE_VSA5", "PEOE_VSA6", "PEOE_VSA7", "PEOE_VSA8", "PEOE_VSA9", "SMR_VSA1", "SMR_VSA10", "SMR_VSA2", "SMR_VSA3", "SMR_VSA4", "SMR_VSA5", "SMR_VSA6", "SMR_VSA7", "SMR_VSA8", "SMR_VSA9", "SlogP_VSA1", "SlogP_VSA10", "SlogP_VSA11", "SlogP_VSA12", "SlogP_VSA2", "SlogP_VSA3", "SlogP_VSA4", "SlogP_VSA5", "SlogP_VSA6", "SlogP_VSA7", "SlogP_VSA8", "SlogP_VSA9", "TPSA", "EState_VSA1", "EState_VSA10", "EState_VSA11", "EState_VSA2", "EState_VSA3", "EState_VSA4", "EState_VSA5", "EState_VSA6", "EState_VSA7", "EState_VSA8", "EState_VSA9", "VSA_EState1", "VSA_EState10", "VSA_EState2", "VSA_EState3", "VSA_EState4", "VSA_EState5", "VSA_EState6", "VSA_EState7", "VSA_EState8", "VSA_EState9", "FractionCSP3", "HeavyAtomCount", "NHOHCount", "NOCount", "NumAliphaticCarbocycles", "NumAliphaticHeterocycles", "NumAliphaticRings", "NumAmideBonds", "NumAromaticCarbocycles", "NumAromaticHeterocycles", "NumAromaticRings", "NumAtomStereoCenters", "NumBridgeheadAtoms", "NumHAcceptors", "NumHDonors", "NumHeteroatoms", "NumHeterocycles", "NumRotatableBonds", "NumSaturatedCarbocycles", "NumSaturatedHeterocycles", "NumSaturatedRings", "NumSpiroAtoms", "NumUnspecifiedAtomStereoCenters", "Phi", "RingCount", "MolLogP", "MolMR", "fr_Al_COO", "fr_Al_OH", "fr_Al_OH_noTert", "fr_ArN", "fr_Ar_COO", "fr_Ar_N", "fr_Ar_NH", "fr_Ar_OH", "fr_COO", "fr_COO2", "fr_C_O", "fr_C_O_noCOO", "fr_C_S", "fr_HOCCN", "fr_Imine", "fr_NH0", "fr_NH1", "fr_NH2", "fr_N_O", "fr_Ndealkylation1", "fr_Ndealkylation2", "fr_Nhpyrrole", "fr_SH", "fr_aldehyde", "fr_alkyl_carbamate", "fr_alkyl_halide", "fr_allylic_oxid", "fr_amide", "fr_amidine", "fr_aniline", "fr_aryl_methyl", "fr_azide", "fr_azo", "fr_barbitur", "fr_benzene", "fr_benzodiazepine", "fr_bicyclic", "fr_diazo", "fr_dihydropyridine", "fr_epoxide", "fr_ester", "fr_ether", "fr_furan", "fr_guanido", "fr_halogen", "fr_hdrzine", "fr_hdrzone", "fr_imidazole", "fr_imide", "fr_isocyan", "fr_isothiocyan", "fr_ketone", "fr_ketone_Topliss", "fr_lactam", "fr_lactone", "fr_methoxy", "fr_morpholine", "fr_nitrile", "fr_nitro", "fr_nitro_arom", "fr_nitro_arom_nonortho", "fr_nitroso", "fr_oxazole", "fr_oxime", "fr_para_hydroxylation", "fr_phenol", "fr_phenol_noOrthoHbond", "fr_phos_acid", "fr_phos_ester", "fr_piperdine", "fr_piperzine", "fr_priamide", "fr_prisulfonamd", "fr_pyridine", "fr_quatN", "fr_sulfide", "fr_sulfonamd", "fr_sulfone", "fr_term_acetylene", "fr_tetrazole", "fr_thiazole", "fr_thiocyan", "fr_thiophene", "fr_unbrch_alkane", "fr_urea"
];

// Group sets
const LIPINSKI = ["MolWt", "MolLogP", "NumHDonors", "NumHAcceptors", "TPSA", "NumRotatableBonds"];
const TICE = ["MolWt", "MolLogP", "NumHDonors", "NumHAcceptors", "TPSA", "NumRotatableBonds"];
const CONSTITUTIONAL = ["HeavyAtomCount", "NHOHCount", "NOCount", "NumHAcceptors", "NumHDonors", "NumHeteroatoms", "NumRotatableBonds", "NumValenceElectrons", "RingCount"];
const TOPOLOGICAL = ["BertzCT", "BalabanJ", "HallKierAlpha", "Ipc", "Kappa1", "Kappa2", "Kappa3", "LabuteASA", "PEOE_VSA1", "PEOE_VSA2", "PEOE_VSA3", "PEOE_VSA4", "PEOE_VSA5", "PEOE_VSA6", "PEOE_VSA7", "PEOE_VSA8", "PEOE_VSA9", "PEOE_VSA10", "PEOE_VSA11", "PEOE_VSA12", "PEOE_VSA13", "PEOE_VSA14", "SMR_VSA1", "SMR_VSA2", "SMR_VSA3", "SMR_VSA4", "SMR_VSA5", "SMR_VSA6", "SMR_VSA7", "SMR_VSA8", "SMR_VSA9", "SlogP_VSA1", "SlogP_VSA2", "SlogP_VSA3", "SlogP_VSA4", "SlogP_VSA5", "SlogP_VSA6", "SlogP_VSA7", "SlogP_VSA8", "SlogP_VSA9", "SlogP_VSA10", "SlogP_VSA11", "SlogP_VSA12", "TPSA"];
const ELECTROTOPOLOGICAL = ["MaxEStateIndex", "MinEStateIndex", "MaxAbsEStateIndex", "MinAbsEStateIndex", "EState_VSA1", "EState_VSA2", "EState_VSA3", "EState_VSA4", "EState_VSA5", "EState_VSA6", "EState_VSA7", "EState_VSA8", "EState_VSA9", "EState_VSA10", "EState_VSA11", "VSA_EState1", "VSA_EState2", "VSA_EState3", "VSA_EState4", "VSA_EState5", "VSA_EState6", "VSA_EState7", "VSA_EState8", "VSA_EState9", "VSA_EState10"];

interface FeaturizerPanelProps {
  smiles: string[];
}

export function FeaturizerPanel({ smiles }: FeaturizerPanelProps) {
  const featurizerSelections = useModelStore((s) => s.featurizerSelections) || [];
  const featurizerEstimate = useModelStore((s) => s.featurizerEstimate);
  const setFeaturizerSelections = useModelStore((s) => s.setFeaturizerSelections);
  const updateFeaturizerEstimate = useModelStore((s) => s.updateFeaturizerEstimate);

  const [activeTab, setActiveTab] = useState<'descriptors_2d' | 'fingerprints' | 'pharmacophore' | 'custom'>('descriptors_2d');
  
  // 2D Descriptors Tab States
  const [searchTerm, setSearchTerm] = useState('');
  const [scrollTop, setScrollTop] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  // Fingerprint Tab States (radius/n_bits/max_path params per card)
  const [fingerprintParams, setFingerprintParams] = useState<Record<string, any>>({
    morgan: { radius: 2, n_bits: 2048 },
    fcfp: { radius: 2, n_bits: 2048 },
    maccs: {},
    avalon: { n_bits: 1024 },
    rdkit_topological: { n_bits: 2048, max_path: 7 },
    atom_pair: { n_bits: 2048 },
    topological_torsion: { n_bits: 2048 },
  });

  // Pharmacophore Tab States
  const [pharmParams, setPharmParams] = useState<Record<string, any>>({
    pharm2d_gobbi: { n_bits: 2048 },
    pharm2d_basic: { n_bits: 2048 },
  });

  // Custom Tab States
  const [customExpression, setCustomExpression] = useState('Descriptors.MolWt(mol)');
  const [customTesting, setCustomTesting] = useState(false);
  const [customTestResults, setCustomTestResults] = useState<any[] | null>(null);
  const [customTestError, setCustomTestError] = useState<string | null>(null);

  // Dynamic estimate trigger debounced on selection changes
  useEffect(() => {
    const handler = setTimeout(() => {
      updateFeaturizerEstimate(smiles.length);
    }, 200);
    return () => clearTimeout(handler);
  }, [featurizerSelections, smiles.length, updateFeaturizerEstimate]);

  // Extract selected descriptors list
  const selectedDescriptors = useMemo(() => {
    const block = featurizerSelections.find(s => s.id === 'descriptors_2d');
    return block?.params?.selected || [];
  }, [featurizerSelections]);

  const updateSelectedDescriptors = (newSelected: string[]) => {
    let updatedSelections = [...featurizerSelections];
    const index = updatedSelections.findIndex(s => s.id === 'descriptors_2d');
    
    if (newSelected.length === 0) {
      // Remove block if nothing selected
      if (index !== -1) {
        updatedSelections.splice(index, 1);
      }
    } else {
      if (index !== -1) {
        updatedSelections[index] = {
          ...updatedSelections[index],
          params: { selected: newSelected }
        };
      } else {
        updatedSelections.push({
          id: 'descriptors_2d',
          params: { selected: newSelected }
        });
      }
    }
    setFeaturizerSelections(updatedSelections);
  };

  // 2D Preset Click Handler with Shift-click subtraction
  const handlePresetClick = (presetList: string[], event: React.MouseEvent) => {
    const current = [...selectedDescriptors];
    if (event.shiftKey) {
      // Remove preset items
      const updated = current.filter(x => !presetList.includes(x));
      updateSelectedDescriptors(updated);
    } else {
      // Add preset items (avoid duplicates)
      const updated = Array.from(new Set([...current, ...presetList]));
      updateSelectedDescriptors(updated);
    }
  };

  // Checkbox toggle handler
  const handleDescriptorToggle = (name: string) => {
    const current = [...selectedDescriptors];
    if (current.includes(name)) {
      updateSelectedDescriptors(current.filter(x => x !== name));
    } else {
      updateSelectedDescriptors([...current, name]);
    }
  };

  // Filter 2D Descriptors
  const filteredDescriptors = useMemo(() => {
    return ALL_DESCRIPTORS.filter(d => 
      d.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [searchTerm]);

  // Simple Virtualization/Windowing Calculation
  const itemHeight = 44;
  const visibleCount = 10;
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - 2);
  const endIndex = Math.min(filteredDescriptors.length, startIndex + visibleCount + 5);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  };

  // Add Fingerprint entry
  const addFingerprint = (id: string) => {
    const params = fingerprintParams[id];
    setFeaturizerSelections([
      ...featurizerSelections,
      { id, params: { ...params } }
    ]);
  };

  // Add Pharmacophore entry
  const addPharmacophore = (id: string) => {
    const params = pharmParams[id];
    setFeaturizerSelections([
      ...featurizerSelections,
      { id, params: { ...params } }
    ]);
  };

  // Add Custom expression entry
  const addCustomExpression = () => {
    if (!customExpression.trim()) return;
    setFeaturizerSelections([
      ...featurizerSelections,
      { id: 'custom', params: { expression: customExpression.trim() } }
    ]);
  };

  // Remove block
  const removeSelectionBlock = (index: number) => {
    const updated = [...featurizerSelections];
    updated.splice(index, 1);
    setFeaturizerSelections(updated);
  };

  // Test Custom Expression IPC call
  const testCustom = async () => {
    if (!customExpression.trim()) return;
    setCustomTesting(true);
    setCustomTestResults(null);
    setCustomTestError(null);
    try {
      const results = await invoke<any[]>('test_custom_expression', {
        smiles: smiles.slice(0, 5),
        expression: customExpression.trim()
      });
      setCustomTestResults(results);
    } catch (e) {
      setCustomTestError(String(e));
    } finally {
      setCustomTesting(false);
    }
  };

  // Validation feedback
  const totalDim = featurizerEstimate?.total_dim || 0;
  const showHardCapError = totalDim > 50000;
  const showSoftWarning = totalDim > 0 && smiles.length > 0 && totalDim > smiles.length * 5;

  return (
    <div className="featurizer-panel-card">
      <style>{`
        .featurizer-panel-card {
          background: var(--color-bg-card);
          border: 0.5px solid var(--color-border);
          border-radius: 8px;
          margin-top: 16px;
          box-shadow: var(--shadow-sm);
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }
        .fp-tabs-row {
          display: flex;
          background: var(--color-border-subtle);
          border-bottom: 0.5px solid var(--color-border);
          padding: 4px 8px 0 8px;
          gap: 4px;
        }
        .fp-tab-btn {
          border: none;
          background: transparent;
          color: var(--color-text-400);
          font-size: 11px;
          font-weight: 500;
          padding: 8px 16px;
          border-radius: 6px 6px 0 0;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .fp-tab-btn:hover {
          color: var(--color-text);
          background: var(--color-bg);
        }
        .fp-tab-btn.active {
          color: var(--color-brand-700);
          background: var(--color-bg-card);
          font-weight: 600;
          border: 0.5px solid var(--color-border);
          border-bottom: none;
          box-shadow: 0 -2px 5px rgba(0,0,0,0.02);
        }
        .fp-tab-content {
          padding: 16px;
          min-height: 280px;
          background: var(--color-bg-card);
        }
        
        /* 2D Tab */
        .fp-2d-layout {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .fp-2d-presets {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          align-items: center;
        }
        .fp-preset-title {
          font-size: 10px;
          color: var(--color-text-400);
          font-weight: 600;
          text-transform: uppercase;
          margin-right: 4px;
        }
        .fp-preset-btn {
          background: var(--color-bg);
          border: 0.5px solid var(--color-border);
          font-size: 10px;
          font-weight: 500;
          padding: 4px 10px;
          border-radius: 4px;
          cursor: pointer;
          color: var(--color-text);
          transition: all 0.15s ease;
        }
        .fp-preset-btn:hover {
          background: var(--color-border-subtle);
          border-color: var(--color-text-400);
        }
        .fp-preset-btn:active {
          transform: translateY(1px);
        }
        .fp-search-box {
          width: 100%;
          background: var(--color-bg);
          border: 0.5px solid var(--color-border);
          padding: 8px 12px;
          border-radius: 6px;
          color: var(--color-text);
          font-size: 11px;
        }
        .fp-search-box:focus {
          outline: none;
          border-color: var(--color-brand-600);
          box-shadow: 0 0 0 2px var(--color-brand-200);
        }
        .fp-virtualized-list {
          border: 0.5px solid var(--color-border);
          border-radius: 6px;
          overflow-y: auto;
          background: var(--color-bg);
          position: relative;
        }
        .fp-descriptor-row {
          position: absolute;
          left: 0;
          right: 0;
          display: flex;
          align-items: center;
          padding: 0 12px;
          border-bottom: 0.5px solid var(--color-border-subtle);
          font-size: 11px;
          cursor: pointer;
          transition: background-color 0.15s;
        }
        .fp-descriptor-row:hover {
          background: var(--color-border-subtle);
        }
        .fp-descriptor-label {
          display: flex;
          align-items: center;
          gap: 8px;
          width: 100%;
          cursor: pointer;
          user-select: none;
        }
        .fp-desc-name {
          font-weight: 600;
          color: var(--color-text);
          min-width: 160px;
        }
        .fp-desc-tooltip {
          color: var(--color-text-400);
          font-size: 10px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        /* Card grid for Fingerprints & Pharmacophores */
        .fp-card-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
          gap: 12px;
        }
        .fp-card {
          background: var(--color-bg);
          border: 0.5px solid var(--color-border);
          border-radius: 6px;
          padding: 12px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          gap: 8px;
          transition: all 0.2s;
        }
        .fp-card:hover {
          border-color: var(--color-brand-400);
          box-shadow: var(--shadow-sm);
        }
        .fp-card-title {
          font-weight: 600;
          font-size: 12px;
          color: var(--color-text);
        }
        .fp-card-desc {
          font-size: 10px;
          color: var(--color-text-400);
          line-height: 1.4;
          min-height: 42px;
        }
        .fp-card-controls {
          display: flex;
          gap: 8px;
          align-items: center;
          font-size: 10px;
        }
        .fp-card-control-group {
          display: flex;
          flex-direction: column;
          gap: 2px;
          flex: 1;
        }
        .fp-card-label {
          font-size: 9px;
          color: var(--color-text-400);
          font-weight: 600;
        }
        .fp-card-select, .fp-card-input {
          background: var(--color-bg-card);
          border: 0.5px solid var(--color-border);
          border-radius: 4px;
          padding: 4px 6px;
          color: var(--color-text);
          font-size: 10px;
        }
        .fp-card-select:focus, .fp-card-input:focus {
          outline: none;
          border-color: var(--color-brand-600);
        }
        .fp-card-add-btn {
          background: var(--color-brand-700);
          color: #ffffff;
          border: none;
          border-radius: 4px;
          padding: 5px 10px;
          font-weight: 600;
          font-size: 10px;
          cursor: pointer;
          transition: background-color 0.15s;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
        }
        .fp-card-add-btn:hover {
          background: var(--color-brand-800);
        }

        /* Custom Tab */
        .fp-custom-layout {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .fp-custom-textarea {
          font-family: monospace;
          background: var(--color-bg);
          border: 0.5px solid var(--color-border);
          border-radius: 6px;
          padding: 12px;
          color: var(--color-text);
          font-size: 11px;
          resize: vertical;
          min-height: 80px;
        }
        .fp-custom-textarea:focus {
          outline: none;
          border-color: var(--color-brand-600);
          box-shadow: 0 0 0 2px var(--color-brand-200);
        }
        .fp-custom-actions {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
        }
        .fp-btn-test {
          background: var(--color-border-subtle);
          border: 0.5px solid var(--color-border);
          color: var(--color-text);
          font-size: 10px;
          font-weight: 600;
          padding: 5px 12px;
          border-radius: 4px;
          cursor: pointer;
        }
        .fp-btn-test:hover {
          background: var(--color-border);
        }
        .fp-custom-preview {
          background: var(--color-bg);
          border: 0.5px solid var(--color-border);
          border-radius: 6px;
          padding: 8px 12px;
          font-size: 10px;
        }
        .fp-preview-row {
          display: flex;
          justify-content: space-between;
          border-bottom: 0.5px solid var(--color-border-subtle);
          padding: 4px 0;
        }
        .fp-preview-row:last-child {
          border-bottom: none;
        }
        .fp-preview-smiles {
          max-width: 250px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: var(--color-text-400);
        }
        .fp-preview-value {
          font-weight: 600;
        }

        /* Sticky Footer */
        .fp-footer {
          border-top: 0.5px solid var(--color-border);
          background: var(--color-border-subtle);
          padding: 12px 16px;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .fp-selected-blocks {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          max-height: 80px;
          overflow-y: auto;
        }
        .fp-block-tag {
          background: var(--color-bg-card);
          border: 0.5px solid var(--color-border);
          border-radius: 4px;
          padding: 3px 8px;
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 10px;
          font-weight: 500;
          color: var(--color-text);
        }
        .fp-block-remove {
          color: var(--color-red-700);
          cursor: pointer;
          font-weight: bold;
          font-size: 11px;
        }
        .fp-block-remove:hover {
          color: var(--color-red-800);
        }
        .fp-total-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 11px;
          font-weight: 600;
          color: var(--color-text);
        }
        .validation-warning {
          background: var(--color-amber-200);
          color: var(--color-amber-700);
          border: 0.5px solid var(--color-amber-600);
          padding: 6px 12px;
          border-radius: 4px;
          font-size: 10px;
          font-weight: 500;
        }
        .validation-error {
          background: var(--color-red-200);
          color: var(--color-red-700);
          border: 0.5px solid var(--color-red-600);
          padding: 6px 12px;
          border-radius: 4px;
          font-size: 10px;
          font-weight: 500;
        }
      `}</style>

      {/* Tabs Menu */}
      <div className="fp-tabs-row">
        <button
          className={`fp-tab-btn${activeTab === 'descriptors_2d' ? ' active' : ''}`}
          onClick={() => setActiveTab('descriptors_2d')}
        >
          2D Descriptors
        </button>
        <button
          className={`fp-tab-btn${activeTab === 'fingerprints' ? ' active' : ''}`}
          onClick={() => setActiveTab('fingerprints')}
        >
          Fingerprints
        </button>
        <button
          className={`fp-tab-btn${activeTab === 'pharmacophore' ? ' active' : ''}`}
          onClick={() => setActiveTab('pharmacophore')}
        >
          Pharmacophore
        </button>
        <button
          className={`fp-tab-btn${activeTab === 'custom' ? ' active' : ''}`}
          onClick={() => setActiveTab('custom')}
        >
          Custom Python
        </button>
      </div>

      {/* Tab Panel Body */}
      <div className="fp-tab-content">
        
        {/* TAB 1: 2D Descriptors */}
        {activeTab === 'descriptors_2d' && (
          <div className="fp-2d-layout">
            <div className="fp-2d-presets">
              <span className="fp-preset-title">Presets (Shift+Click to Subtract):</span>
              <button
                className="fp-preset-btn"
                onClick={(e) => handlePresetClick(LIPINSKI, e)}
                title="Lipinski's Rule of 5 parameters"
              >
                Lipinski Ro5
              </button>
              <button
                className="fp-preset-btn"
                onClick={(e) => handlePresetClick(TICE, e)}
                title="Tice 2001 agrochemical preset"
              >
                Tice Agrochemical
              </button>
              <button
                className="fp-preset-btn"
                onClick={(e) => handlePresetClick(CONSTITUTIONAL, e)}
                title="Constitutional indices and atom counts"
              >
                Constitutional
              </button>
              <button
                className="fp-preset-btn"
                onClick={(e) => handlePresetClick(TOPOLOGICAL, e)}
                title="Topological shape and connectivity descriptors"
              >
                Topological
              </button>
              <button
                className="fp-preset-btn"
                onClick={(e) => handlePresetClick(ELECTROTOPOLOGICAL, e)}
                title="E-state and electrotopological values"
              >
                Electrotopological
              </button>
            </div>

            <input
              type="text"
              placeholder="Search ~208 RDKit descriptors..."
              className="fp-search-box"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />

            <div
              ref={listRef}
              className="fp-virtualized-list"
              style={{ height: '240px' }}
              onScroll={handleScroll}
            >
              <div style={{ height: `${filteredDescriptors.length * itemHeight}px`, position: 'relative' }}>
                {filteredDescriptors.slice(startIndex, endIndex).map((name, idx) => {
                  const actualIndex = startIndex + idx;
                  const top = actualIndex * itemHeight;
                  const isChecked = selectedDescriptors.includes(name);
                  const tooltip = DESCRIPTOR_DESCRIPTIONS[name] || "RDKit physicochemical calculated descriptor.";

                  return (
                    <div
                      key={name}
                      className="fp-descriptor-row"
                      style={{ top: `${top}px`, height: `${itemHeight}px` }}
                      onClick={() => handleDescriptorToggle(name)}
                    >
                      <label className="fp-descriptor-label" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          style={{ cursor: 'pointer' }}
                          checked={isChecked}
                          onChange={() => handleDescriptorToggle(name)}
                        />
                        <span className="fp-desc-name">{name}</span>
                        <span className="fp-desc-tooltip">{tooltip}</span>
                      </label>
                    </div>
                  );
                })}
              </div>
            </div>
            <div style={{ fontSize: '10px', color: 'var(--color-text-400)', textAlign: 'right' }}>
              Showing {filteredDescriptors.length} of {ALL_DESCRIPTORS.length} descriptors. {selectedDescriptors.length} selected.
            </div>
          </div>
        )}

        {/* TAB 2: Fingerprints */}
        {activeTab === 'fingerprints' && (
          <div className="fp-card-grid">
            
            {/* Morgan Card */}
            <div className="fp-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="fp-card-title">Morgan (ECFP)</span>
                <span className="fp-card-desc">Circular topological fingerprint representing atom neighborhoods. Cheap and powerful.</span>
              </div>
              <div className="fp-card-controls">
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Radius (r)</span>
                  <select
                    className="fp-card-select"
                    value={fingerprintParams.morgan.radius}
                    onChange={(e) => setFingerprintParams({
                      ...fingerprintParams,
                      morgan: { ...fingerprintParams.morgan, radius: parseInt(e.target.value) }
                    })}
                  >
                    <option value={1}>1 (ECFP2)</option>
                    <option value={2}>2 (ECFP4 - std)</option>
                    <option value={3}>3 (ECFP6)</option>
                    <option value={4}>4 (ECFP8)</option>
                  </select>
                </div>
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Bits</span>
                  <select
                    className="fp-card-select"
                    value={fingerprintParams.morgan.n_bits}
                    onChange={(e) => setFingerprintParams({
                      ...fingerprintParams,
                      morgan: { ...fingerprintParams.morgan, n_bits: parseInt(e.target.value) }
                    })}
                  >
                    <option value={512}>512</option>
                    <option value={1024}>1024</option>
                    <option value={2048}>2048</option>
                  </select>
                </div>
                <button className="fp-card-add-btn" onClick={() => addFingerprint('morgan')}>Add</button>
              </div>
            </div>

            {/* FCFP Card */}
            <div className="fp-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="fp-card-title">FCFP</span>
                <span className="fp-card-desc">Feature-based Extended Connectivity circular fingerprint utilizing functional chemical classes.</span>
              </div>
              <div className="fp-card-controls">
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Radius (r)</span>
                  <select
                    className="fp-card-select"
                    value={fingerprintParams.fcfp.radius}
                    onChange={(e) => setFingerprintParams({
                      ...fingerprintParams,
                      fcfp: { ...fingerprintParams.fcfp, radius: parseInt(e.target.value) }
                    })}
                  >
                    <option value={1}>1 (FCFP2)</option>
                    <option value={2}>2 (FCFP4 - std)</option>
                    <option value={3}>3 (FCFP6)</option>
                    <option value={4}>4 (FCFP8)</option>
                  </select>
                </div>
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Bits</span>
                  <select
                    className="fp-card-select"
                    value={fingerprintParams.fcfp.n_bits}
                    onChange={(e) => setFingerprintParams({
                      ...fingerprintParams,
                      fcfp: { ...fingerprintParams.fcfp, n_bits: parseInt(e.target.value) }
                    })}
                  >
                    <option value={512}>512</option>
                    <option value={1024}>1024</option>
                    <option value={2048}>2048</option>
                  </select>
                </div>
                <button className="fp-card-add-btn" onClick={() => addFingerprint('fcfp')}>Add</button>
              </div>
            </div>

            {/* MACCS Keys Card */}
            <div className="fp-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="fp-card-title">MACCS Keys</span>
                <span className="fp-card-desc">167 predefined, binary structural keys mapping specific biological structural fragments.</span>
              </div>
              <div className="fp-card-controls" style={{ justifyContent: 'flex-end' }}>
                <span style={{ fontSize: '9px', color: 'var(--color-text-400)', marginRight: 'auto' }}>Fixed 167 bits</span>
                <button className="fp-card-add-btn" onClick={() => addFingerprint('maccs')}>Add</button>
              </div>
            </div>

            {/* Avalon Card */}
            <div className="fp-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="fp-card-title">Avalon</span>
                <span className="fp-card-desc">A highly robust, hybrid path-based fingerprint capturing structural path features.</span>
              </div>
              <div className="fp-card-controls">
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Bits</span>
                  <select
                    className="fp-card-select"
                    value={fingerprintParams.avalon.n_bits}
                    onChange={(e) => setFingerprintParams({
                      ...fingerprintParams,
                      avalon: { ...fingerprintParams.avalon, n_bits: parseInt(e.target.value) }
                    })}
                  >
                    <option value={512}>512</option>
                    <option value={1024}>1024</option>
                    <option value={2048}>2048</option>
                  </select>
                </div>
                <button className="fp-card-add-btn" onClick={() => addFingerprint('avalon')}>Add</button>
              </div>
            </div>

            {/* RDKit Topological Card */}
            <div className="fp-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="fp-card-title">RDKit Topological</span>
                <span className="fp-card-desc">Topological path-based fingerprint mapping subgraphs of varying lengths. More expensive.</span>
              </div>
              <div className="fp-card-controls">
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Max Path</span>
                  <input
                    type="number"
                    min={1}
                    max={7}
                    className="fp-card-input"
                    value={fingerprintParams.rdkit_topological.max_path}
                    onChange={(e) => setFingerprintParams({
                      ...fingerprintParams,
                      rdkit_topological: { ...fingerprintParams.rdkit_topological, max_path: parseInt(e.target.value) || 7 }
                    })}
                  />
                </div>
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Bits</span>
                  <select
                    className="fp-card-select"
                    value={fingerprintParams.rdkit_topological.n_bits}
                    onChange={(e) => setFingerprintParams({
                      ...fingerprintParams,
                      rdkit_topological: { ...fingerprintParams.rdkit_topological, n_bits: parseInt(e.target.value) }
                    })}
                  >
                    <option value={512}>512</option>
                    <option value={1024}>1024</option>
                    <option value={2048}>2048</option>
                  </select>
                </div>
                <button className="fp-card-add-btn" onClick={() => addFingerprint('rdkit_topological')}>Add</button>
              </div>
            </div>

            {/* Atom Pairs Card */}
            <div className="fp-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="fp-card-title">Atom Pairs</span>
                <span className="fp-card-desc">Topological distance-based fingerprints capturing environments of all pairs of heavy atoms.</span>
              </div>
              <div className="fp-card-controls">
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Bits</span>
                  <select
                    className="fp-card-select"
                    value={fingerprintParams.atom_pair.n_bits}
                    onChange={(e) => setFingerprintParams({
                      ...fingerprintParams,
                      atom_pair: { ...fingerprintParams.atom_pair, n_bits: parseInt(e.target.value) }
                    })}
                  >
                    <option value={512}>512</option>
                    <option value={1024}>1024</option>
                    <option value={2048}>2048</option>
                  </select>
                </div>
                <button className="fp-card-add-btn" onClick={() => addFingerprint('atom_pair')}>Add</button>
              </div>
            </div>

            {/* Topological Torsions Card */}
            <div className="fp-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="fp-card-title">Topological Torsions</span>
                <span className="fp-card-desc">Torsion-based path representation mapping structures of four bonded heavy atoms.</span>
              </div>
              <div className="fp-card-controls">
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Bits</span>
                  <select
                    className="fp-card-select"
                    value={fingerprintParams.topological_torsion.n_bits}
                    onChange={(e) => setFingerprintParams({
                      ...fingerprintParams,
                      topological_torsion: { ...fingerprintParams.topological_torsion, n_bits: parseInt(e.target.value) }
                    })}
                  >
                    <option value={512}>512</option>
                    <option value={1024}>1024</option>
                    <option value={2048}>2048</option>
                  </select>
                </div>
                <button className="fp-card-add-btn" onClick={() => addFingerprint('topological_torsion')}>Add</button>
              </div>
            </div>

          </div>
        )}

        {/* TAB 3: Pharmacophores */}
        {activeTab === 'pharmacophore' && (
          <div className="fp-card-grid">
            
            {/* Gobbi Card */}
            <div className="fp-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="fp-card-title">2D Pharmacophore (Gobbi)</span>
                <span className="fp-card-desc">2D pharmacophore fingerprints utilizing Gobbi factories, folded modulo n_bits to a dense vector.</span>
              </div>
              <div className="fp-card-controls">
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Dense Fold Modulo</span>
                  <select
                    className="fp-card-select"
                    value={pharmParams.pharm2d_gobbi.n_bits}
                    onChange={(e) => setPharmParams({
                      ...pharmParams,
                      pharm2d_gobbi: { n_bits: parseInt(e.target.value) }
                    })}
                  >
                    <option value={1024}>1024</option>
                    <option value={2048}>2048</option>
                    <option value={4096}>4096</option>
                  </select>
                </div>
                <button className="fp-card-add-btn" onClick={() => addPharmacophore('pharm2d_gobbi')}>Add</button>
              </div>
            </div>

            {/* Basic Card */}
            <div className="fp-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="fp-card-title">2D Pharmacophore (Basic)</span>
                <span className="fp-card-desc">Uses standard 5-feature definitions (Acceptor, Donor, Hydrophobic, Positive, Negative).</span>
              </div>
              <div className="fp-card-controls">
                <div className="fp-card-control-group">
                  <span className="fp-card-label">Dense Fold Modulo</span>
                  <select
                    className="fp-card-select"
                    value={pharmParams.pharm2d_basic.n_bits}
                    onChange={(e) => setPharmParams({
                      ...pharmParams,
                      pharm2d_basic: { n_bits: parseInt(e.target.value) }
                    })}
                  >
                    <option value={1024}>1024</option>
                    <option value={2048}>2048</option>
                    <option value={4096}>4096</option>
                  </select>
                </div>
                <button className="fp-card-add-btn" onClick={() => addPharmacophore('pharm2d_basic')}>Add</button>
              </div>
            </div>

          </div>
        )}

        {/* TAB 4: Custom Python Expression */}
        {activeTab === 'custom' && (
          <div className="fp-custom-layout">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span className="fp-card-title">Sandboxed Python Expression</span>
              <span className="fp-card-desc">
                Evaluate safe, restricted expressions per molecule. Namespace contains: <code>Chem</code>, <code>Descriptors</code>, <code>rdMolDescriptors</code>, <code>Lipinski</code>, <code>Crippen</code>, <code>math</code>, and the variable <code>mol</code>. Expression must return a float or a list/tuple of floats.
              </span>
            </div>

            <textarea
              className="fp-custom-textarea"
              placeholder="Descriptors.MolWt(mol) + Descriptors.MolLogP(mol)"
              value={customExpression}
              onChange={(e) => setCustomExpression(e.target.value)}
            />

            <div className="fp-custom-actions">
              <button
                className="fp-btn-test"
                disabled={customTesting || !customExpression.trim()}
                onClick={testCustom}
              >
                {customTesting ? "Evaluating on 5 mols..." : "Test on first 5 molecules"}
              </button>
              <button
                className="fp-card-add-btn"
                disabled={!customExpression.trim()}
                onClick={addCustomExpression}
              >
                Add Block to Selection
              </button>
            </div>

            {customTestError && (
              <div className="validation-error">
                ⚠ Custom Evaluation Failed: {customTestError}
              </div>
            )}

            {customTestResults && (
              <div className="fp-custom-preview">
                <span className="fp-card-label" style={{ marginBottom: '6px', display: 'block' }}>Expression Preview Results (First 5 Curated Molecules):</span>
                {customTestResults.map((res, i) => (
                  <div className="fp-preview-row" key={i}>
                    <span className="fp-preview-smiles">{res.smiles}</span>
                    {res.success ? (
                      <span className="fp-preview-value" style={{ color: 'var(--color-brand-700)' }}>
                        ✓ {typeof res.value === 'number' ? res.value.toFixed(4) : JSON.stringify(res.value)}
                      </span>
                    ) : (
                      <span className="fp-preview-value" style={{ color: 'var(--color-red-700)' }}>
                        ✗ Error: {res.value}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>

      {/* Sticky Bottom Footer */}
      <div className="fp-footer">
        <span className="fp-card-label">Selected Blocks:</span>
        <div className="fp-selected-blocks">
          {featurizerSelections.length === 0 ? (
            <span style={{ fontSize: '10px', color: 'var(--color-text-400)', fontStyle: 'italic' }}>
              No featurization blocks selected. Please configure at least one descriptor/fingerprint.
            </span>
          ) : (
            featurizerSelections.map((sel, idx) => {
              let labelText = sel.id;
              let paramText = '';
              const blockDetails = featurizerEstimate?.blocks?.find(b => b.id === sel.id);
              const costText = blockDetails ? ` (${blockDetails.dim} dim, ~${blockDetails.cost_seconds.toFixed(3)}s)` : '';

              if (sel.id === 'descriptors_2d') {
                labelText = '2D Descriptors';
                const count = sel.params?.selected?.length || 0;
                paramText = `${count} descriptors selected`;
              } else if (sel.id === 'morgan') {
                labelText = 'Morgan ECFP';
                paramText = `r=${sel.params?.radius}, ${sel.params?.n_bits} bits`;
              } else if (sel.id === 'fcfp') {
                labelText = 'FCFP';
                paramText = `r=${sel.params?.radius}, ${sel.params?.n_bits} bits`;
              } else if (sel.id === 'maccs') {
                labelText = 'MACCS Keys';
                paramText = '167 bits';
              } else if (sel.id === 'avalon') {
                labelText = 'Avalon';
                paramText = `${sel.params?.n_bits} bits`;
              } else if (sel.id === 'rdkit_topological') {
                labelText = 'RDKit Topological';
                paramText = `max_path=${sel.params?.max_path}, ${sel.params?.n_bits} bits`;
              } else if (sel.id === 'atom_pair') {
                labelText = 'Atom Pairs';
                paramText = `${sel.params?.n_bits} bits`;
              } else if (sel.id === 'topological_torsion') {
                labelText = 'Topological Torsions';
                paramText = `${sel.params?.n_bits} bits`;
              } else if (sel.id === 'pharm2d_gobbi') {
                labelText = '2D Pharmacophore (Gobbi)';
                paramText = `${sel.params?.n_bits} bits`;
              } else if (sel.id === 'pharm2d_basic') {
                labelText = '2D Pharmacophore (Basic)';
                paramText = `${sel.params?.n_bits} bits`;
              } else if (sel.id === 'custom') {
                labelText = 'Custom Expression';
                paramText = sel.params?.expression || '';
              }

              return (
                <div className="fp-block-tag" key={idx}>
                  <span><strong>{labelText}</strong> {paramText ? `(${paramText})` : ''} {costText}</span>
                  <span className="fp-block-remove" onClick={() => removeSelectionBlock(idx)}>×</span>
                </div>
              );
            })
          )}
        </div>

        {/* Total Summary IPC result */}
        {featurizerEstimate && (
          <div className="fp-total-row">
            <span>
              Total: {totalDim} features · est. {featurizerEstimate.total_cost_seconds.toFixed(2)} s for {smiles.length} molecules
            </span>
          </div>
        )}

        {/* Validation warnings */}
        {showHardCapError && (
          <div className="validation-error" style={{ marginTop: '4px' }}>
            ⚠ Hard Cap Violation: Total features ({totalDim}) exceed 50,000 threshold. Please reduce your fingerprints size or 2D descriptors selections.
          </div>
        )}

        {showSoftWarning && !showHardCapError && (
          <div className="validation-warning" style={{ marginTop: '4px' }}>
            ⚠ Attention: You have configured more features ({totalDim}) than compounds ({smiles.length}) in the dataset (ratio exceeds 5x). Consider reducing bits or selections to avoid extreme overfitting.
          </div>
        )}
      </div>

    </div>
  );
}
