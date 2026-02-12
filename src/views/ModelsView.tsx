import { useState, useEffect, useRef } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useModelStore } from '../store/modelStore';
import { useSettingsStore } from '../store/settingsStore';
import { useResizableColumns } from '../hooks/useResizableColumns';
import { CurationReportPanel } from '../components/CurationReportPanel';
import { CvStabilityTable } from '../components/CvStabilityTable';
import { YScramblingCard } from '../components/YScramblingCard';
import { FeaturizerPanel } from '../components/FeaturizerPanel';
import { ArenaResultsView } from '../components/ArenaResultsView';
import DiagnosticsPanel from '../components/DiagnosticsPanel';
import CliffsPanel from '../components/CliffsPanel';
import { CitationExportButton } from '../components/shared/CitationExportButton';
import { ContextualHelp } from '../components/shared/ContextualHelp';
import { ProgressIndicator } from '../components/shared/ProgressIndicator';


const PRESETS = {
  bee: {
    name: "Honeybee Contact Toxicity (LD50)",
    type: "classification" as const,
    description: "Binary classification (toxic vs non-toxic) based on EPA pollinator exposure contact LD50 safety limits.",
    smiles: [
      "ClC1=C(C=CC=C1)C2=NC(Cl)=C(Cl)N2", // Permethrin-like
      "CN(C)C(=O)OC1=CC=CC(=C1)C(C)(C)C", // Carbofuran-like
      "O=C(OC(C#N)C1=CC(OC2=CC=CC=C2)=CC=C1)C3C(C=C(Cl)Cl)C3(C)C", // Cypermethrin
      "CN1C(SC=N1)=NC(=O)NC(C)(C)C", // Thiamethoxam-like
      "O=P(OCC)(OCC)SCSCC", // Phorate
      "O=C(NC1=CC(Cl)=C(OC2=C(Cl)C=C(C(F)(F)F)C=C2)C=C1Cl)C3=C(F)C=CC=C3F", // Teflubenzuron
      "CNC(=O)OC1=CC=CC=C1OC(C)C", // Propoxur
      "O=C(NC(=O)C1C(C=C(Br)Br)C1(C)C)C2=CC=CC=C2", // Deltamethrin-like
      "CN1C(=C(C(=O)N(C1=O)C)O)C(=O)NC2=CC=CC=C2", // Pyridate-like
      "O=P(OC(=C(Cl)Cl)OC)(OC)OC", // Dichlorvos
      // Non-toxic controls
      "O=C(O)CC(O)(C(=O)O)CC(=O)O", // Citric Acid
      "OC1C(O)C(O)C(O)C(O)C1O", // Inositol
      "CC(=O)O", // Acetic Acid
      "NC(C)C(=O)O", // Alanine
      "OCC(O)CO", // Glycerol
      "OC1=CC=CC=C1", // Phenol
      "O=C(O)C1=CC=CC=C1", // Benzoic Acid
      "NC1=CC=CC=C1", // Aniline
      "CCCCCC", // Hexane
      "CC(C)CO" // Isobutanol
    ],
    activities: [
      1, 1, 1, 1, 1, 1, 1, 1, 1, 1, // Toxic class
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0  // Non-toxic class
    ]
  },
  solubility: {
    name: "Aqueous Solubility (LogS)",
    type: "regression" as const,
    description: "QSAR regression model predicting logs of aqueous solubility indexes (mol/L) for systemic uptake calculations.",
    smiles: [
      "CC1=CC=CC=C1", // Toluene
      "C1=CC=CC=C1", // Benzene
      "CCC", // Propane
      "CCO", // Ethanol
      "CC(C)O", // Isopropanol
      "CCCC", // Butane
      "CCCCCC", // Hexane
      "CCCCCCCC", // Octane
      "ClC(Cl)Cl", // Chloroform
      "ClC1=CC=CC=C1", // Chlorobenzene
      "OC1=CC=CC=C1", // Phenol
      "O=C(O)C1=CC=CC=C1", // Benzoic acid
      "NC1=CC=CC=C1", // Aniline
      "CN(C)C", // Trimethylamine
      "O=S(=O)(O)O", // Sulfuric acid
      "O=C(O)CC(=O)O", // Malonic acid
      "O=C(O)C(=O)O", // Oxalic acid
      "CC(=O)O", // Acetic acid
      "C1CCCCC1", // Cyclohexane
      "CC1=CC=C(C=C1)C(C)C" // Cymene
    ],
    activities: [
      -2.73, -1.98, -3.00, 0.50, 0.40, -3.50, -4.30, -5.70, -1.72, -2.48,
      -0.74, -1.60, -0.47, 0.20, 1.00, 0.80, 0.50, 0.90, -3.80, -4.10
    ]
  },
  daphnia: {
    name: "Daphnia Selectivity (EC50)",
    type: "regression" as const,
    description: "Acute toxicity regression model predicting Daphnia magna EC50 levels (mg/L) for runoff assessments.",
    smiles: [
      "ClC1=CC(=C(C=C1)C(Cl)(C(=O)O)C2=CC(Cl)=CC=C2)Cl", // Herbicide-like
      "O=C(NC1=CC(Cl)=CC=C1)C2=CC=CC=C2", // Fungicide-like
      "CNC(=O)OC1=CC=CC=C1C(C)(C)S", // Carbamate-like
      "O=P(OCC)(OCC)OC1=NC(Cl)=C(Cl)N1", // Organophosphate-like
      "CN(C)C(=N)NC(=O)C1=CC=CC=C1",
      "NC(=O)NC1=CC=CC=C1",
      "FC(F)(F)C1=CC=CC=C1",
      "O=C(O)CC(O)(CC(=O)O)C(=O)O",
      "CC1=C(C)C(O)=CC=C1",
      "O=C(O)C1=CC=C(O)C=C1",
      "C1=CC=CC=C1",
      "CC1=CC=CC=C1",
      "CCO",
      "CC(C)O",
      "CCCCCC",
      "OC1=CC=CC=C1",
      "O=C(O)C1=CC=CC=C1",
      "NC1=CC=CC=C1",
      "CCCCCC(C)C",
      "CC1=CC=C(C=C1)C(C)C"
    ],
    activities: [
      0.15, 0.45, 0.08, 0.02, 1.25, 8.40, 14.50, 48.00, 3.20, 24.10,
      12.00, 9.20, 120.00, 95.00, 1.80, 4.20, 22.00, 3.10, 0.80, 2.10
    ]
  }
};

const ALGO_PRETTY_NAMES: Record<string, string> = {
  rf: 'Random Forest',
  xgboost: 'XGBoost',
  gbm: 'Gradient Boosting',
  lightgbm: 'LightGBM',
  svm: 'SVM',
  ridge: 'Ridge',
  elasticnet: 'ElasticNet',
  knn: 'k-NN',
  mlp: 'MLP'
};

function StructureDepict({ smiles }: { smiles: string }) {
  const [svg, setSvg] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!smiles) return;
    setLoading(true);
    invoke<string>('depict_compound', { smiles })
      .then(res => setSvg(res))
      .catch(err => console.error("Depiction failed", err))
      .finally(() => setLoading(false));
  }, [smiles]);

  if (loading) return <div style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>Rendering 2D structure...</div>;
  if (!svg) return <div style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>Structure depiction unavailable</div>;

  return (
    <div
      className="structure-view-svg-container"
      style={{
        width: '100%',
        height: '150px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--color-surface)',
        border: '0.5px solid var(--color-border)',
        borderRadius: '6px',
        padding: '8px',
        overflow: 'hidden'
      }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

export function ModelsView() {
  const { widths: previewWidths, tableRef: previewTableRef, handleMouseDown: handlePreviewMouseDown } = useResizableColumns([75, 25]);
  const models = useModelStore((s) => s.models) || [];
  const wizardStep = useModelStore((s) => s.wizardStep);
  const trainingLogs = useModelStore((s) => s.trainingLogs) || [];
  const activeResults = useModelStore((s) => s.activeTrainingResults);
  const selectedModelId = useModelStore((s) => s.selectedModelId);

  const deployModel = useModelStore((s) => s.deployModel);
  const undeployModel = useModelStore((s) => s.undeployModel);
  const [selectedTargets, setSelectedTargets] = useState<Record<string, string>>({});

  // Unified inspector and library selections state
  const isViewingLibraryModel = !activeResults && !!selectedModelId;
  const selectedModel = models.find(m => m.id === selectedModelId);

  const effectiveResults = activeResults || (selectedModel ? {
    id: selectedModel.id,
    config: {
      algorithm: selectedModel.algorithm,
      model_type: selectedModel.type,
      features: (() => {
        try {
          return JSON.parse(selectedModel.features || '[]');
        } catch {
          return [];
        }
      })(),
      featurizer_selections: (() => {
        try {
          const diag = JSON.parse(selectedModel.diagnostics || '{}');
          return diag.featurizer_selections || [];
        } catch {
          return [];
        }
      })()
    },
    metrics: (() => {
      try {
        return JSON.parse(selectedModel.metrics || '{}');
      } catch {
        return {};
      }
    })(),
    importances: (() => {
      try {
        return JSON.parse(selectedModel.importances || '{}');
      } catch {
        return {};
      }
    })(),
    plot_data: (() => {
      try {
        const diag = JSON.parse(selectedModel.diagnostics || '{}');
        return diag.plot_data || {};
      } catch {
        return {};
      }
    })(),
    learning_curve: (() => {
      try {
        const diag = JSON.parse(selectedModel.diagnostics || '{}');
        return diag.learning_curve || [];
      } catch {
        return [];
      }
    })(),
    cv_results: (() => {
      try {
        return JSON.parse(selectedModel.cv_results || '[]');
      } catch {
        return [];
      }
    })(),
    y_scramble: (() => {
      try {
        return selectedModel.y_scramble ? JSON.parse(selectedModel.y_scramble) : null;
      } catch {
        return null;
      }
    })(),
    shap_values: selectedModel.shap_values || null,
    cliffs: (() => {
      try {
        return selectedModel.cliffs ? JSON.parse(selectedModel.cliffs) : [];
      } catch {
        return [];
      }
    })(),
    diagnostics: (() => {
      try {
        return JSON.parse(selectedModel.diagnostics || '{}');
      } catch {
        return {};
      }
    })(),
    is_saved: true,
  } : null);

  const activeMetrics = effectiveResults?.metrics || {};
  const activeImportances = effectiveResults?.importances || {};
  const activeLearningCurve = effectiveResults?.learning_curve || [];

  const [highlightedPoints, setHighlightedPoints] = useState<number[]>([]);

  // SHAP interpretability subtabs and cache hooks
  const [activeTab, setActiveTab] = useState<'diagnostics' | 'why'>('diagnostics');
  const [shapSubTab, setShapSubTab] = useState<'global' | 'beeswarm' | 'waterfall'>('global');
  const [selectedCompoundIndex, setSelectedCompoundIndex] = useState<number>(0);
  const [globalToggle, setGlobalToggle] = useState<'shap' | 'gini' | 'coef'>('shap');
  const [shapSummaryData, setShapSummaryData] = useState<any>(null);
  const [shapLoading, setShapLoading] = useState<boolean>(false);

  // Atom map states
  const [selectedMorganBlockIdx, setSelectedMorganBlockIdx] = useState<number>(0);
  const [atomMapUri, setAtomMapUri] = useState<string>('');
  const [atomMapLoading, setAtomMapLoading] = useState<boolean>(false);
  const [atomMapError, setAtomMapError] = useState<string>('');

  const effectiveModelId = activeResults ? 'active' : selectedModelId;

  // Extract topological blocks and check eligibility
  const modelFeaturizerSelections = effectiveResults?.config?.featurizer_selections || [];
  const morganBlocks = modelFeaturizerSelections.filter((s: any) => s.id === 'morgan' || s.id === 'fcfp');
  const hasCircular = morganBlocks.length > 0;
  const algoLower = (effectiveResults?.config?.algorithm || '').toLowerCase();
  const isTreeOrLinear = ['rf', 'gbm', 'xgboost', 'lightgbm', 'ridge', 'elasticnet'].some((k: string) => algoLower.includes(k));
  const isEligible = hasCircular && isTreeOrLinear;

  const pointsList = effectiveResults?.plot_data?.points || [];
  const currentPt = pointsList[selectedCompoundIndex] || {};
  const currentSmiles = currentPt.smiles || '';

  // Effect to load contribution map
  useEffect(() => {
    if (!effectiveModelId || !currentSmiles || !isEligible) {
      setAtomMapUri('');
      setAtomMapError('');
      return;
    }

    setAtomMapLoading(true);
    setAtomMapError('');

    invoke<string>('render_atom_map', {
      modelId: effectiveModelId,
      smiles: currentSmiles,
      morganBlockIdx: selectedMorganBlockIdx
    })
      .then((uri) => {
        setAtomMapUri(uri);
      })
      .catch((err) => {
        console.error('Failed to render atom contribution map:', err);
        setAtomMapError(String(err));
      })
      .finally(() => {
        setAtomMapLoading(false);
      });
  }, [effectiveModelId, currentSmiles, selectedMorganBlockIdx, isEligible]);

  useEffect(() => {
    if (!effectiveModelId) {
      setShapSummaryData(null);
      return;
    }

    setShapLoading(true);
    setShapSummaryData(null);
    setSelectedCompoundIndex(0);

    invoke<any>('get_shap_summary', { modelId: effectiveModelId })
      .then((data) => {
        setShapSummaryData(data);
      })
      .catch((err) => {
        console.error('Failed to fetch SHAP summary:', err);
      })
      .finally(() => {
        setShapLoading(false);
      });
  }, [effectiveModelId]);

  const fetchModels = useModelStore((s) => s.fetchModels);
  const deleteModel = useModelStore((s) => s.deleteModel);
  const saveActiveModel = useModelStore((s) => s.saveActiveModel);
  const trainModel = useModelStore((s) => s.trainModel);
  const setWizardStep = useModelStore((s) => s.setWizardStep);
  const setSelectedModelId = useModelStore((s) => s.setSelectedModelId);
  const resetWizard = useModelStore((s) => s.resetWizard);

  // Arena Store actions & states
  const runArena = useModelStore((s) => s.runArena);
  const activeArenaResults = useModelStore((s) => s.activeArenaResults);
  const arenaProgress = useModelStore((s) => s.arenaProgress);

  // Settings Store for python diagnostics
  const pythonInfo = useSettingsStore((s) => s.pythonInfo);

  // Curation state & actions
  const curationReport = useModelStore((s) => s.curationReport);
  const curatedSmiles = useModelStore((s) => s.curatedSmiles);
  const curatedActivities = useModelStore((s) => s.curatedActivities);
  const imbalanceRecommendation = useModelStore((s) => s.imbalanceRecommendation);
  const runCuration = useModelStore((s) => s.runCuration);
  const acceptCuration = useModelStore((s) => s.acceptCuration);
  
  const featurizerSelections = useModelStore((s) => s.featurizerSelections) || [];
  const featurizerEstimate = useModelStore((s) => s.featurizerEstimate);

  // Mode & Arena configurations state
  const [mode, setMode] = useState<'single' | 'arena'>('single');
  const [selectedAlgos, setSelectedAlgos] = useState<string[]>(['rf', 'gbm', 'svm']);
  const [searchMode, setSearchMode] = useState<'default' | 'bayesian_quick'>('default');

  // Wizard state
  const [selectedPreset, setSelectedPreset] = useState<'bee' | 'solubility' | 'daphnia' | 'custom' | null>(null);
  const [isCurationLoading, setIsCurationLoading] = useState(false);
  const [expandedProvenanceId, setExpandedProvenanceId] = useState<string | null>(null);

  const handleNextToCuration = async () => {
    let smiles: string[] = [];
    let activities: number[] = [];

    if (selectedPreset === 'custom') {
      if (!customParsedData) return;
      smiles = customParsedData.smiles;
      activities = customParsedData.activities;
    } else if (selectedPreset) {
      smiles = PRESETS[selectedPreset].smiles;
      activities = PRESETS[selectedPreset].activities;
    } else {
      return;
    }

    setIsCurationLoading(true);
    try {
      await runCuration(smiles, activities, modelType);
    } catch (e) {
      console.error('Curation failed:', e);
      alert('Failed to execute curation preview: ' + String(e));
    } finally {
      setIsCurationLoading(false);
    }
  };
  
  // Custom CSV State
  const [customFile, setCustomFile] = useState<File | null>(null);
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [csvPreview, setCsvPreview] = useState<string[][]>([]);
  const [smilesCol, setSmilesCol] = useState<string>('');
  const [targetCol, setTargetCol] = useState<string>('');
  const [customParsedData, setCustomParsedData] = useState<{ smiles: string[]; activities: number[] } | null>(null);
  const [csvError, setCsvError] = useState<string | null>(null);

  // Config parameters state
  const [modelType, setModelType] = useState<'regression' | 'classification'>('regression');
  const [selectedAlgorithm, setSelectedAlgorithm] = useState<string>('Random Forest');

  const [nEstimators, setNEstimators] = useState<number>(100);
  const [maxDepth, setMaxDepth] = useState<number>(6);
  const [ridgeAlpha, setRidgeAlpha] = useState<number>(1.0);
  const [mitigation, setMitigation] = useState<'none' | 'class_weight' | 'smote'>('none');
  const [imbalanceStrategy, setImbalanceStrategy] = useState<'none' | 'class_weight' | 'smote' | 'undersample'>('none');
  const [splitRatio, setSplitRatio] = useState<number>(0.8);
  const [splitMode, setSplitMode] = useState<'random' | 'stratified' | 'scaffold'>('random');
  const [cvFolds, setCvFolds] = useState<number>(5);
  const [randomSeed, setRandomSeed] = useState<number>(42);
  const [nScramble, setNScramble] = useState<number>(10);
  const [saveName, setSaveName] = useState<string>('');

  const terminalEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch models on mount
  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  // Synchronize mitigation and imbalance strategy to store recommendation when loaded
  useEffect(() => {
    if (imbalanceRecommendation) {
      setMitigation(imbalanceRecommendation);
      setImbalanceStrategy(imbalanceRecommendation as any);
    } else {
      setMitigation('none');
      setImbalanceStrategy('none');
    }
  }, [imbalanceRecommendation]);

  // Autoscroll terminal
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [trainingLogs]);

  // Auto-fill save name when training succeeds
  useEffect(() => {
    if (activeResults && !saveName) {
      const presetName = selectedPreset && selectedPreset !== 'custom' ? PRESETS[selectedPreset].name : 'custom_model';
      const formattedName = presetName.toLowerCase().replace(/[^a-z0-9]/g, '_') + '_' + activeResults.config.algorithm.toLowerCase().replace(/[^a-z0-9]/g, '_');
      setSaveName(formattedName);
    }
  }, [activeResults, selectedPreset]);

  // Synchronize wizard model types when preset changes
  useEffect(() => {
    if (selectedPreset && selectedPreset !== 'custom') {
      const type = PRESETS[selectedPreset].type;
      setModelType(type);
      if (type === 'classification') {
        setSelectedAlgorithm('Random Forest');
      } else {
        setSelectedAlgorithm('Random Forest');
      }
    }
  }, [selectedPreset]);



  const handleCustomFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setCustomFile(file);
    setCsvError(null);
    setCustomParsedData(null);

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const lines = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);
      if (lines.length < 2) {
        setCsvError("CSV file must contain a header row and at least 5 compounds.");
        return;
      }

      // Simple CSV cell splitter (handles commas inside quotes briefly if needed)
      const parseCsvLine = (line: string) => {
        const result: string[] = [];
        let current = '';
        let inQuotes = false;
        for (let i = 0; i < line.length; i++) {
          const char = line[i];
          if (char === '"') {
            inQuotes = !inQuotes;
          } else if (char === ',' && !inQuotes) {
            result.push(current.trim());
            current = '';
          } else {
            current += char;
          }
        }
        result.push(current.trim());
        return result;
      };

      const headers = parseCsvLine(lines[0]);
      setCsvHeaders(headers);

      // Guess SMILES and target columns
      const lowHeaders = headers.map(h => h.toLowerCase());
      const smilesIndex = lowHeaders.findIndex(h => h.includes('smiles') || h.includes('structure'));
      const targetIndex = lowHeaders.findIndex(h => h.includes('target') || h.includes('activity') || h.includes('log') || h.includes('val') || h.includes('ld50') || h.includes('ec50'));

      if (smilesIndex !== -1) setSmilesCol(headers[smilesIndex]);
      else if (headers.length > 0) setSmilesCol(headers[0]);

      if (targetIndex !== -1) setTargetCol(headers[targetIndex]);
      else if (headers.length > 1) setTargetCol(headers[1]);

      // Grab first 3 rows for preview
      const previewRows = lines.slice(1, 4).map(line => parseCsvLine(line));
      setCsvPreview(previewRows);

      // Store parsed columns temporarily
      const smilesList: string[] = [];
      const activitiesList: number[] = [];

      for (let i = 1; i < lines.length; i++) {
        const row = parseCsvLine(lines[i]);
        if (row.length < Math.max(smilesIndex, targetIndex) + 1) continue;

        const sVal = row[smilesIndex !== -1 ? smilesIndex : 0];
        const tValRaw = row[targetIndex !== -1 ? targetIndex : 1];
        const tVal = parseFloat(tValRaw);

        if (sVal && !isNaN(tVal)) {
          smilesList.push(sVal);
          activitiesList.push(tVal);
        }
      }

      if (smilesList.length < 5) {
        setCsvError("Failed to parse enough valid SMILES and continuous numeric labels. Minimum 5 rows required.");
      } else {
        setCustomParsedData({ smiles: smilesList, activities: activitiesList });
      }
    };
    reader.readAsText(file);
  };

  const handleStartTraining = async () => {
    let smiles: string[] = [];
    let activities: number[] = [];
    let datasetName = '';

    if (selectedPreset === 'custom') {
      if (!customParsedData) {
        alert("Please load a valid CSV file first.");
        return;
      }
      smiles = customParsedData.smiles;
      activities = customParsedData.activities;
      datasetName = customFile?.name ?? 'Custom CSV Dataset';
    } else if (selectedPreset) {
      smiles = PRESETS[selectedPreset].smiles;
      activities = PRESETS[selectedPreset].activities;
      datasetName = PRESETS[selectedPreset].name;
    } else {
      alert("Please select a dataset first.");
      return;
    }

    if (featurizerSelections.length === 0) {
      alert("Please configure at least one descriptor/fingerprint featurizer.");
      return;
    }

    const totalDim = featurizerEstimate?.total_dim || 0;
    if (totalDim > 50000) {
      alert(`Hard Cap Violation: Total configured features (${totalDim}) exceed 50,000 threshold. Please reduce your fingerprint size or descriptors selection.`);
      return;
    }

    const config = {
      model_type: modelType,
      algorithm: selectedAlgorithm,
      featurizer_selections: featurizerSelections,
      split_mode: splitMode,
      test_size: 1.0 - splitRatio,
      random_seed: randomSeed,
      cv_folds: cvFolds,
      n_scramble: nScramble,
      imbalance_strategy: modelType === 'classification' ? imbalanceStrategy : 'none',
      hyperparameters: {
        n_estimators: nEstimators,
        max_depth: maxDepth,
        alpha: ridgeAlpha,
        mitigation: modelType === 'classification' ? mitigation : 'none'
      }
    };

    const trainingSmiles = curatedSmiles || smiles;
    const trainingActivities = curatedActivities || activities;

    try {
      await trainModel(datasetName, trainingSmiles, trainingActivities, config);
    } catch (e) {
      console.error('Failed training QSAR model:', e);
    }
  };

  const handleStartArena = async () => {
    let smiles: string[] = [];
    let activities: number[] = [];

    if (selectedPreset === 'custom') {
      if (!customParsedData) {
        alert("Please load a valid CSV file first.");
        return;
      }
      smiles = customParsedData.smiles;
      activities = customParsedData.activities;
    } else if (selectedPreset) {
      smiles = PRESETS[selectedPreset].smiles;
      activities = PRESETS[selectedPreset].activities;
    } else {
      alert("Please select a dataset first.");
      return;
    }

    if (selectedAlgos.length < 2 || selectedAlgos.length > 6) {
      alert("Please select between 2 and 6 algorithms to compare.");
      return;
    }

    if (featurizerSelections.length === 0) {
      alert("Please configure at least one descriptor/fingerprint featurizer.");
      return;
    }

    const totalDim = featurizerEstimate?.total_dim || 0;
    if (totalDim > 50000) {
      alert(`Hard Cap Violation: Total configured features (${totalDim}) exceed 50,000 threshold. Please reduce your fingerprint size or descriptors selection.`);
      return;
    }

    const config = {
      model_type: modelType,
      featurizer_selections: featurizerSelections,
      split_mode: splitMode,
      test_size: 1.0 - splitRatio,
      random_seed: randomSeed,
      cv_folds: cvFolds,
      n_scramble: nScramble,
      imbalance_strategy: modelType === 'classification' ? imbalanceStrategy : 'none',
      arena: {
        algorithms: selectedAlgos,
        per_algo_search: searchMode
      }
    };

    const trainingSmiles = curatedSmiles || smiles;
    const trainingActivities = curatedActivities || activities;

    try {
      await runArena(trainingSmiles, trainingActivities, config);
    } catch (e) {
      console.error('Failed executing QSAR Arena comparison:', e);
    }
  };

  // Safe metric rendering
  const getMetricBadge = (key: string, val: number | undefined) => {
    if (val == null) return '—';
    if (key.includes('r2')) {
      return val > 0.7 ? (
        <span style={{ color: 'var(--color-brand-700)', fontWeight: 600 }}>{val.toFixed(3)}</span>
      ) : val > 0.4 ? (
        <span style={{ color: 'var(--color-amber-700)', fontWeight: 500 }}>{val.toFixed(3)}</span>
      ) : (
        <span style={{ color: 'var(--color-red-700)' }}>{val.toFixed(3)}</span>
      );
    }
    if (key.includes('accuracy') || key === 'precision' || key === 'recall' || key === 'f1_score' || key === 'auc_roc') {
      return val > 0.8 ? (
        <span style={{ color: 'var(--color-brand-700)', fontWeight: 600 }}>{(val * 100).toFixed(1)}%</span>
      ) : val > 0.6 ? (
        <span style={{ color: 'var(--color-amber-700)', fontWeight: 500 }}>{(val * 100).toFixed(1)}%</span>
      ) : (
        <span style={{ color: 'var(--color-red-700)' }}>{(val * 100).toFixed(1)}%</span>
      );
    }
    return val.toFixed(3);
  };

  const renderGlobalView = () => {
    const algo = effectiveResults?.config.algorithm || '';
    const algoLower = algo.toLowerCase();
    const isTree = ['rf', 'gbm', 'xgboost', 'lightgbm'].some(k => algoLower.includes(k));
    const isLinear = ['ridge', 'elasticnet'].some(k => algoLower.includes(k)) || (algoLower === 'svm' && selectedModel?.diagnostics?.includes('linear'));

    let displayData: { name: string; score: number }[] = [];
    let scoreLabel = '';

    if (globalToggle === 'shap') {
      displayData = (shapSummaryData.global_importance || []).map((item: any) => ({
        name: item.name,
        score: item.mean_abs_shap
      }));
      scoreLabel = 'Mean Absolute SHAP value';
    } else if (globalToggle === 'gini') {
      displayData = Object.entries(effectiveResults.importances || {}).map(([name, val]: any) => ({
        name,
        score: val
      }));
      displayData.sort((a, b) => b.score - a.score);
      scoreLabel = 'Gini Importance (Relative %)';
    } else if (globalToggle === 'coef') {
      displayData = (shapSummaryData.linear_coefficients || []).map((item: any) => ({
        name: item.name,
        score: Math.abs(item.std_coef)
      }));
      scoreLabel = 'Absolute Standardized Coefficient';
    }

    const clippedData = displayData.slice(0, 20);
    const maxScore = Math.max(...clippedData.map(d => d.score), 1e-5);

    return (
      <div className="plot-container-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div className="plot-title" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            Global Feature Influence ({scoreLabel})
            <ContextualHelp topicId="studio.shap" />
          </div>
          
          <div style={{ display: 'flex', gap: '4px', background: 'var(--color-border-subtle)', padding: '2px', borderRadius: '4px' }}>
            <button
              onClick={() => setGlobalToggle('shap')}
              style={{
                padding: '2px 8px',
                fontSize: '9px',
                border: 'none',
                borderRadius: '3px',
                background: globalToggle === 'shap' ? 'var(--color-surface)' : 'transparent',
                color: globalToggle === 'shap' ? 'var(--color-text-900)' : 'var(--color-text-400)',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              SHAP
            </button>
            {isTree && (
              <button
                onClick={() => setGlobalToggle('gini')}
                style={{
                  padding: '2px 8px',
                  fontSize: '9px',
                  border: 'none',
                  borderRadius: '3px',
                  background: globalToggle === 'gini' ? 'var(--color-surface)' : 'transparent',
                  color: globalToggle === 'gini' ? 'var(--color-text-900)' : 'var(--color-text-400)',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Gini
              </button>
            )}
            {isLinear && shapSummaryData.linear_coefficients && shapSummaryData.linear_coefficients.length > 0 && (
              <button
                onClick={() => setGlobalToggle('coef')}
                style={{
                  padding: '2px 8px',
                  fontSize: '9px',
                  border: 'none',
                  borderRadius: '3px',
                  background: globalToggle === 'coef' ? 'var(--color-surface)' : 'transparent',
                  color: globalToggle === 'coef' ? 'var(--color-text-900)' : 'var(--color-text-400)',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Coefficients
              </button>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {clippedData.length === 0 ? (
            <div style={{ fontSize: '10px', color: 'var(--color-text-400)', textAlign: 'center', padding: '20px' }}>No values calculated.</div>
          ) : (
            clippedData.map((d) => {
              const percentage = (d.score / maxScore) * 100;
              let tooltipDetail = `${scoreLabel}: ${d.score.toFixed(4)}`;
              if (globalToggle === 'coef') {
                const orig = (shapSummaryData.linear_coefficients || []).find((c: any) => c.name === d.name);
                if (orig) {
                  tooltipDetail += ` (Std: ${orig.std_coef.toFixed(4)}, Raw: ${orig.coef.toFixed(4)})`;
                }
              }

              return (
                <div key={d.name} className="eval-feature-row" title={tooltipDetail}>
                  <div className="eval-feature-header">
                    <span className="eval-feature-label">{d.name}</span>
                    <span className="eval-feature-val">{d.score.toFixed(4)}</span>
                  </div>
                  <div className="eval-feature-bar-bg">
                    <div
                      className="eval-feature-bar-fill"
                      style={{
                        width: `${Math.max(1, percentage)}%`,
                        backgroundColor: globalToggle === 'shap' ? 'var(--color-brand-600)' : globalToggle === 'gini' ? 'var(--color-blue-500)' : 'var(--color-amber-600)'
                      }}
                    />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    );
  };

  const renderBeeswarmView = () => {
    const beeswarmPoints = shapSummaryData.beeswarm_data || [];
    const top20Features = Array.from(new Set(beeswarmPoints.map((pt: any) => pt.feature))).slice(0, 20);

    const shapVals = beeswarmPoints.map((pt: any) => pt.shap);
    const minShap = Math.min(...shapVals, -1e-5);
    const maxShap = Math.max(...shapVals, 1e-5);
    const shapRange = maxShap - minShap;

    const getBeeswarmColor = (val: number) => {
      const r = Math.round(59 + val * (239 - 59));
      const g = Math.round(130 + val * (68 - 130));
      const b = Math.round(246 + val * (68 - 246));
      return `rgb(${r}, ${g}, ${b})`;
    };

    return (
      <div className="plot-container-card">
        <div className="plot-title" style={{ marginBottom: '6px' }}>Beeswarm Distribution Strip-Plot</div>
        <p style={{ fontSize: '9px', color: 'var(--color-text-400)', marginBottom: '16px' }}>
          Each point represents a compound. Horizontal position shows SHAP attribution (direction and magnitude of impact). Color represents the relative feature value (Blue = Low, Red = High). Click any point to select compound and open Waterfall.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderLeft: '1px solid var(--color-border)', paddingLeft: '8px' }}>
          {top20Features.map((fName: any) => {
            const points = beeswarmPoints.filter((pt: any) => pt.feature === fName);
            
            return (
              <div key={fName} style={{ display: 'flex', alignItems: 'center', height: '28px', borderBottom: '0.5px solid var(--color-border-subtle)' }}>
                <div style={{ width: '140px', fontSize: '9px', fontWeight: 600, color: 'var(--color-text-700)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={fName}>
                  {fName}
                </div>

                <div style={{ flex: 1, height: '100%', position: 'relative' }}>
                  <div style={{
                    position: 'absolute',
                    left: `${(-minShap / shapRange) * 100}%`,
                    top: 0,
                    bottom: 0,
                    width: '1px',
                    borderLeft: '1px dashed var(--color-border)',
                    opacity: 0.7,
                    zIndex: 1
                  }} />

                  {points.map((pt: any, idx: number) => {
                    const x = ((pt.shap - minShap) / shapRange) * 100;
                    const color = getBeeswarmColor(pt.relative_value);
                    
                    return (
                      <div
                        key={idx}
                        style={{
                          position: 'absolute',
                          left: `${Math.min(98, Math.max(1, x))}%`,
                          top: '50%',
                          transform: 'translate(-50%, -50%)',
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          backgroundColor: color,
                          border: '0.2px solid rgba(255, 255, 255, 0.4)',
                          zIndex: 2,
                          cursor: 'pointer'
                        }}
                        title={`Val: ${pt.value.toFixed(3)}\nSHAP: ${pt.shap.toFixed(4)}`}
                        onClick={() => {
                          const foundIdx = (effectiveResults.plot_data.points || []).findIndex((p: any) => p.smiles === effectiveResults.plot_data.points[pt.compound_index]?.smiles);
                          if (foundIdx !== -1) {
                            setSelectedCompoundIndex(foundIdx);
                            setActiveTab('why');
                            setShapSubTab('waterfall');
                          }
                        }}
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: 'var(--color-text-400)', marginTop: '8px', paddingLeft: '148px' }}>
          <span>← Less Safe / Lower Activity ({minShap.toFixed(2)})</span>
          <span style={{ fontWeight: 600 }}>Attribution (SHAP = 0.0)</span>
          <span>More Safe / Higher Activity (+{maxShap.toFixed(2)}) →</span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', marginTop: '16px', fontSize: '9px', fontWeight: 600 }}>
          <span style={{ color: 'rgb(59, 130, 246)' }}>Low Feature Value</span>
          <div style={{ width: '120px', height: '6px', borderRadius: '3px', background: 'linear-gradient(to right, rgb(59, 130, 246), rgb(239, 68, 68))' }} />
          <span style={{ color: 'rgb(239, 68, 68)' }}>High Feature Value</span>
        </div>
      </div>
    );
  };

  const renderWaterfallView = () => {
    const pointsList = effectiveResults.plot_data.points || [];
    const selectedComp = shapSummaryData.per_compound?.[selectedCompoundIndex];

    if (!selectedComp || pointsList.length === 0) {
      return (
        <div style={{ padding: '20px', textAlign: 'center', fontSize: '11px', color: 'var(--color-text-400)' }}>
          No local explanation data available for compound index {selectedCompoundIndex}.
        </div>
      );
    }

    const currentPt = pointsList[selectedCompoundIndex] || {};
    const expectedVal = selectedComp.expected_value;
    const predVal = selectedComp.prediction;
    const topFeatures = selectedComp.top_features || [];
    const remainingShap = selectedComp.remaining_shap;

    // Calculate fingerprint vs descriptor percentage contribution
    const rowShap = shapSummaryData.shap_values?.[selectedCompoundIndex] || [];
    const totalAbsShap = rowShap.reduce((sum: number, val: number) => sum + Math.abs(val), 0);

    const selectedBlock = morganBlocks[selectedMorganBlockIdx];
    const radius = selectedBlock?.params?.radius ?? 2;
    const blockId = selectedBlock?.id ?? 'morgan';
    const prefix = `${blockId}_${radius}:`;
    const prefixFallback = `${blockId}:`;

    const blockShapSum = rowShap.reduce((sum: number, val: number, idx: number) => {
      const fName = shapSummaryData.feature_names?.[idx] || '';
      if (fName.startsWith(prefix) || fName.startsWith(prefixFallback)) {
        return sum + Math.abs(val);
      }
      return sum;
    }, 0);

    const percent = totalAbsShap > 0 ? ((blockShapSum / totalAbsShap) * 100).toFixed(1) : '0.0';

    let current = expectedVal;
    const cumulativePoints = [
      { label: 'Expected Value', start: 0, end: expectedVal, shap: expectedVal },
    ];

    topFeatures.forEach((feat: any) => {
      const next = current + feat.shap;
      cumulativePoints.push({
        label: `${feat.name} = ${feat.value.toFixed(2)}`,
        start: current,
        end: next,
        shap: feat.shap
      });
      current = next;
    });

    if (remainingShap !== 0) {
      const next = current + remainingShap;
      cumulativePoints.push({
        label: 'Other Features',
        start: current,
        end: next,
        shap: remainingShap
      });
      current = next;
    }

    cumulativePoints.push({
      label: 'Final Prediction',
      start: 0,
      end: predVal,
      shap: predVal
    });

    const allVals = cumulativePoints.flatMap(pt => [pt.start, pt.end]);
    const minVal = Math.min(...allVals, 0) - 0.2;
    const maxVal = Math.max(...allVals, 0) + 0.2;
    const valRange = maxVal - minVal;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <div className="plot-container-card">
            <div className="plot-title" style={{ marginBottom: '12px' }}>Attribution Waterfall Chart</div>

            <div className="config-form-group" style={{ marginBottom: '16px' }}>
              <label className="config-form-label" style={{ fontSize: '10px' }}>Selected Compound:</label>
              <select
                className="config-select"
                value={selectedCompoundIndex}
                onChange={(e) => setSelectedCompoundIndex(parseInt(e.target.value))}
                style={{ fontSize: '11px', height: '28px', padding: '4px' }}
              >
                {pointsList.map((pt: any, i: number) => (
                  <option key={i} value={i}>
                    {`Compound #${i + 1} (True: ${pt.true_value.toFixed(2)}, Pred: ${pt.pred_value.toFixed(2)})`}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {cumulativePoints.map((pt, idx) => {
                const xStart = ((pt.start - minVal) / valRange) * 100;
                const xEnd = ((pt.end - minVal) / valRange) * 100;
                const left = Math.min(xStart, xEnd);
                const width = Math.max(1.5, Math.abs(xEnd - xStart));
                const isBase = idx === 0 || idx === cumulativePoints.length - 1;
                const barColor = isBase
                  ? 'var(--color-blue-500, #3b82f6)'
                  : pt.shap > 0
                    ? 'var(--color-brand-600, #16a34a)'
                    : 'var(--color-red-500, #dc2626)';

                return (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', height: '24px', fontSize: '10px' }}>
                    <div style={{ width: '130px', fontWeight: 600, color: 'var(--color-text-700)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={pt.label}>
                      {pt.label}
                    </div>
                    
                    <div style={{ flex: 1, position: 'relative', height: '100%', background: 'var(--color-border-subtle)', borderRadius: '4px' }}>
                      <div style={{
                        position: 'absolute',
                        left: `${(-minVal / valRange) * 100}%`,
                        top: 0,
                        bottom: 0,
                        width: '1px',
                        borderLeft: '1px dashed var(--color-border)',
                        zIndex: 1
                      }} />
                      
                      <div
                        style={{
                          position: 'absolute',
                          left: `${left}%`,
                          width: `${width}%`,
                          height: '80%',
                          top: '10%',
                          backgroundColor: barColor,
                          borderRadius: '3px',
                          zIndex: 2,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: pt.shap > 0 ? 'flex-end' : 'flex-start',
                          padding: '0 4px',
                          color: '#fff',
                          fontSize: '8px',
                          fontWeight: 700
                        }}
                      >
                        {pt.shap !== 0 && (pt.shap > 0 ? '+' : '') + pt.shap.toFixed(3)}
                      </div>
                    </div>
                    
                    <div style={{ width: '50px', textAlign: 'right', fontWeight: 700, color: 'var(--color-text-900)' }}>
                      {pt.end.toFixed(3)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="plot-container-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div className="plot-title">Compound Chemical Profile</div>
            
            <div style={{ fontSize: '9px', wordBreak: 'break-all', padding: '6px', background: 'var(--color-sidebar)', borderRadius: '4px', border: '0.5px solid var(--color-border)', color: 'var(--color-text-600)', fontFamily: 'monospace' }}>
              <strong>SMILES:</strong> {currentPt.smiles || '—'}
            </div>

            {currentPt.smiles && <StructureDepict smiles={currentPt.smiles} />}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '0.5px solid var(--color-border-subtle)', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--color-text-400)' }}>True value:</span>
                <span style={{ fontWeight: 600, color: 'var(--color-text-900)' }}>{currentPt.true_value?.toFixed(3) ?? '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '0.5px solid var(--color-border-subtle)', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--color-text-400)' }}>Predicted:</span>
                <span style={{ fontWeight: 600, color: 'var(--color-text-900)' }}>{currentPt.pred_value?.toFixed(3) ?? '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--color-text-400)' }}>Error:</span>
                <span style={{ fontWeight: 600, color: 'var(--color-red-600)' }}>
                  {currentPt.true_value != null && currentPt.pred_value != null
                    ? (currentPt.true_value - currentPt.pred_value).toFixed(3)
                    : '—'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Atom Contribution Map Card */}
        <div className="plot-container-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div className="plot-title">🧬 Topological Atom-level Contribution Map</div>
            
            {/* Morgan Block Selector if multiple blocks exist */}
            {isEligible && morganBlocks.length > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>Fingerprint Block:</span>
                <select
                  className="config-select"
                  value={selectedMorganBlockIdx}
                  onChange={(e) => setSelectedMorganBlockIdx(parseInt(e.target.value))}
                  style={{ fontSize: '10px', height: '24px', padding: '2px 4px', width: 'auto' }}
                >
                  {morganBlocks.map((block: any, i: number) => (
                    <option key={i} value={i}>
                      {`${block.id === 'fcfp' ? 'FCFP' : 'Morgan'} (r=${block.params?.radius ?? 2}, size=${block.params?.n_bits ?? 2048})`}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {!isEligible ? (
            <div style={{ padding: '20px', textAlign: 'center', background: 'var(--color-sidebar)', borderRadius: '6px', border: '0.5px solid var(--color-border)', fontSize: '11px', color: 'var(--color-text-400)' }}>
              ⚠️ Atom-level contribution mapping is only available for models trained with topological circular fingerprints (Morgan/FCFP) and using linear or tree algorithms.
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px' }}>
              {/* Map depiction */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'var(--color-bg)', border: '0.5px solid var(--color-border)', borderRadius: '6px', padding: '16px', minHeight: '300px', position: 'relative' }}>
                {atomMapLoading ? (
                  <div className="inspector-structure-loading">Rendering topological similarity map...</div>
                ) : atomMapError ? (
                  <div style={{ fontSize: '11px', color: 'var(--color-red-600)', textAlign: 'center' }}>
                    ✕ Failed to render similarity map:<br />
                    <span style={{ fontSize: '10px', opacity: 0.8 }}>{atomMapError}</span>
                  </div>
                ) : atomMapUri ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', width: '100%' }}>
                    <img
                      src={atomMapUri}
                      alt="Atom Contribution Similarity Map"
                      style={{ maxWidth: '100%', maxHeight: '350px', objectFit: 'contain', borderRadius: '4px' }}
                    />
                    <button
                      className="inspector-btn"
                      onClick={() => {
                        invoke('save_atom_map_png', { base64Data: atomMapUri })
                          .catch(err => alert('Failed to save file: ' + String(err)));
                      }}
                      style={{ fontSize: '10px', padding: '4px 10px', background: 'var(--color-surface)', display: 'flex', alignItems: 'center', gap: '4px' }}
                    >
                      💾 Save contribution map PNG
                    </button>
                  </div>
                ) : (
                  <div style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>Map visualization empty</div>
                )}
              </div>

              {/* Explanations, Legend & Disclaimer */}
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '16px' }}>
                <div>
                  <h4 style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-text-900)', marginBottom: '8px' }}>
                    How to interpret this similarity map:
                  </h4>
                  <ul style={{ fontSize: '10px', color: 'var(--color-text-600)', paddingLeft: '14px', lineHeight: 1.5, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <li><strong>Circular Environments:</strong> Topological features (Morgan/FCFP) are mapped back to their atomic spheres of influence.</li>
                    <li><strong>SHAP Attributions:</strong> The contribution weights are distributed uniformly across the atoms within the bit's BFS radius.</li>
                    <li><strong>Atomic contribution color-coding</strong> highlights which structural centers drive the predicted endpoint.</li>
                  </ul>
                </div>

                {/* Color legend */}
                <div style={{ background: 'var(--color-sidebar)', border: '0.5px solid var(--color-border)', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-700)', marginBottom: '6px' }}>
                    Atomic Contribution Weights (Blue-White-Red):
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: 'var(--color-text-400)', marginBottom: '4px' }}>
                    <span>Decreases activity / toxicity (Blue)</span>
                    <span>Neutral (White)</span>
                    <span>Increases activity / toxicity (Red)</span>
                  </div>
                  <div style={{ width: '100%', height: '8px', borderRadius: '4px', background: 'linear-gradient(to right, #3b82f6, #f3f4f6, #dc2626)' }} />
                </div>

                {/* Disclaimer if non-circular features exist */}
                {modelFeaturizerSelections.some((s: any) => s.id !== 'morgan' && s.id !== 'fcfp') && (
                  <div style={{ fontSize: '9.5px', fontStyle: 'italic', color: 'var(--color-brand-850)', background: 'var(--color-brand-55)', border: '0.5px solid var(--color-brand-300)', padding: '10px', borderRadius: '6px', lineHeight: 1.4 }}>
                    💡 <strong>Interpretation Note:</strong> This map shows the {selectedBlock?.id === 'fcfp' ? 'FCFP' : 'Morgan'} fingerprint contribution only (<strong>{percent}%</strong> of total local |SHAP| attribution). The remaining <strong>{(100 - parseFloat(percent)).toFixed(1)}%</strong> of contribution comes from descriptor-based or other custom features.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="main-content models-container">
      {/* Top Banner */}
      <div className="models-header-banner">
        <div>
          <h1>QSAR Model Studio</h1>
          <p>Fit custom predictive models using physicochemical descriptors and topological fingerprints. Validate offline first.</p>
        </div>
        {wizardStep !== 'select_data' && (
          <button className="inspector-btn" onClick={resetWizard}>
            ✕ Cancel Wizard
          </button>
        )}
      </div>

      <div className="models-grid-layout">
        {/* Left Column: Wizard Panels */}
        <div className="models-wizard-card">
          
          {/* Step 1: Select Dataset */}
          {wizardStep === 'select_data' && (
            <div>
              <div className="wizard-step-header" style={{ marginBottom: '12px' }}>
                <span className="wizard-step-title">1. Choose Training Dataset</span>
                <span className="wizard-step-indicator">Step 1 of 4</span>
              </div>

              {/* Mode Toggle */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', background: 'var(--color-bg)', padding: '4px', borderRadius: '6px', border: '0.5px solid var(--color-border)' }}>
                <button
                  onClick={() => setMode('single')}
                  style={{
                    flex: 1,
                    padding: '6px 12px',
                    borderRadius: '4px',
                    border: 'none',
                    background: mode === 'single' ? 'var(--color-brand-600)' : 'transparent',
                    color: mode === 'single' ? '#ffffff' : 'var(--color-text-600)',
                    fontWeight: 600,
                    fontSize: '11px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                  className="mode-toggle-btn"
                >
                  Single Model Fit
                </button>
                <button
                  onClick={() => setMode('arena')}
                  style={{
                    flex: 1,
                    padding: '6px 12px',
                    borderRadius: '4px',
                    border: 'none',
                    background: mode === 'arena' ? 'var(--color-brand-600)' : 'transparent',
                    color: mode === 'arena' ? '#ffffff' : 'var(--color-text-600)',
                    fontWeight: 600,
                    fontSize: '11px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                  className="mode-toggle-btn"
                >
                  🛡️ Arena Mode (Compare Models)
                </button>
              </div>

              <div className="config-section-title">Agrochemical Presets</div>
              <div className="presets-grid">
                {(Object.keys(PRESETS) as Array<keyof typeof PRESETS>).map((key) => {
                  const preset = PRESETS[key];
                  return (
                    <div
                      key={key}
                      className={`model-preset-card${selectedPreset === key ? ' selected' : ''}`}
                      onClick={() => setSelectedPreset(key)}
                    >
                      <div className="model-preset-title">{preset.name}</div>
                      <div className="model-preset-desc">{preset.description}</div>
                      <div className="model-preset-meta">
                        <span>{preset.type === 'regression' ? 'Regression' : 'Classification'}</span>
                        <span>{preset.smiles.length} compounds</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="config-section-title" style={{ marginTop: '16px' }}>Proprietary Compound Library</div>
              <div
                className={`csv-dropzone${selectedPreset === 'custom' ? ' selected' : ''}`}
                onClick={() => {
                  setSelectedPreset('custom');
                  fileInputRef.current?.click();
                }}
              >
                <div className="csv-dropzone-icon">📁</div>
                <div className="csv-dropzone-text">
                  {customFile ? `Selected: ${customFile.name}` : 'Upload Proprietary Dataset (CSV)'}
                </div>
                <div className="csv-dropzone-subtext">
                  File must contain a column of SMILES structures and a continuous/binary target.
                </div>
                <input
                  type="file"
                  ref={fileInputRef}
                  accept=".csv"
                  style={{ display: 'none' }}
                  onChange={handleCustomFileChange}
                />
              </div>

              {csvError && (
                <div className="workflow-error" style={{ marginTop: '10px' }}>
                  ⚠ {csvError}
                </div>
              )}

              {selectedPreset === 'custom' && customParsedData && (
                <div style={{ marginTop: '16px', background: 'var(--color-bg)', padding: '12px', borderRadius: '6px', border: '0.5px solid var(--color-border)' }}>
                  <div className="config-section-title" style={{ fontSize: '10px', marginBottom: '8px' }}>Column Mapping & Preview</div>
                  
                  <div className="config-options-grid" style={{ marginBottom: '10px' }}>
                    <div className="config-form-group">
                      <label className="config-form-label">SMILES Column</label>
                      <select
                        className="config-select"
                        value={smilesCol}
                        onChange={(e) => setSmilesCol(e.target.value)}
                      >
                        {csvHeaders.map(h => <option key={h} value={h}>{h}</option>)}
                      </select>
                    </div>
                    <div className="config-form-group">
                      <label className="config-form-label">Target Activity</label>
                      <select
                        className="config-select"
                        value={targetCol}
                        onChange={(e) => setTargetCol(e.target.value)}
                      >
                        {csvHeaders.map(h => <option key={h} value={h}>{h}</option>)}
                      </select>
                    </div>
                  </div>

                  <table ref={previewTableRef} style={{ width: '100%', fontSize: '10px', borderCollapse: 'collapse', marginTop: '6px' }}>
                    <thead>
                      <tr style={{ background: 'var(--color-border-subtle)', textAlign: 'left' }}>
                        <th style={{ padding: '4px', width: `${previewWidths[0]}%`, position: 'relative' }}>
                          SMILES
                          <div className="col-resize-handle" onMouseDown={(e) => handlePreviewMouseDown(0, e)} />
                        </th>
                        <th style={{ padding: '4px', width: `${previewWidths[1]}%`, position: 'relative' }}>
                          Activity
                          <div className="col-resize-handle" onMouseDown={(e) => handlePreviewMouseDown(1, e)} />
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {csvPreview.map((row, i) => (
                        <tr key={i} style={{ borderBottom: '0.5px solid var(--color-border-subtle)' }}>
                          <td style={{ padding: '4px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {row[csvHeaders.indexOf(smilesCol)] ?? '—'}
                          </td>
                          <td style={{ padding: '4px', fontWeight: 600 }}>
                            {row[csvHeaders.indexOf(targetCol)] ?? '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{ fontSize: '9px', color: 'var(--color-text-400)', marginTop: '8px', textAlign: 'right' }}>
                    Successfully indexed {customParsedData.smiles.length} rows for training.
                  </div>
                </div>
              )}

              <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  className="inspector-btn-primary"
                  style={{ width: 'auto', padding: '6px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
                  disabled={!selectedPreset || (selectedPreset === 'custom' && !customParsedData) || isCurationLoading}
                  onClick={handleNextToCuration}
                >
                  {isCurationLoading ? (
                    <>
                      <span className="inspector-structure-spinner" style={{ width: '12px', height: '12px', border: '1.5px solid #ffffff', borderTopColor: 'transparent' }} />
                      Curating Dataset...
                    </>
                  ) : (
                    'Configure Parameters →'
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Step 1.5: Curation Report Panel */}
          {wizardStep === 'curation' && curationReport && (
            <CurationReportPanel
              report={curationReport}
              modelType={modelType}
              onBack={() => setWizardStep('select_data')}
              onAccept={acceptCuration}
            />
          )}

          {/* Step 2: Configure Parameters */}
          {wizardStep === 'configure' && mode === 'single' && (
            <div>
              <div className="wizard-step-header">
                <span className="wizard-step-title">2. Configure Estimator Parameters</span>
                <span className="wizard-step-indicator">Step 2 of 4</span>
              </div>

              <div className="config-options-grid" style={{ gridTemplateColumns: modelType === 'classification' ? '1fr 1fr 1fr' : '1fr 1fr' }}>
                <div className="config-form-group">
                  <label className="config-form-label">Estimator Target</label>
                  <select
                    className="config-select"
                    value={modelType}
                    onChange={(e) => {
                      const val = e.target.value as 'regression' | 'classification';
                      setModelType(val);
                      setSelectedAlgorithm('Random Forest');
                    }}
                    disabled={selectedPreset !== 'custom'}
                  >
                    <option value="regression">Regression (Continuous values)</option>
                    <option value="classification">Classification (Binary Toxic/Safe)</option>
                  </select>
                </div>

                <div className="config-form-group">
                  <label className="config-form-label">
                    ML Estimator Algorithm
                    <ContextualHelp topicId="studio.algorithm" />
                  </label>
                  <select
                    className="config-select"
                    value={selectedAlgorithm}
                    onChange={(e) => setSelectedAlgorithm(e.target.value)}
                  >
                    <option value="Random Forest">Random Forest (Ensemble Tree)</option>
                    <option value="SVM">Support Vector Machine (SVM)</option>
                    <option value="Gradient Boosting">Gradient Boosting Regressor</option>
                    <option value="Ridge">Linear Ridge Regressor</option>
                  </select>
                </div>

                {modelType === 'classification' && curationReport?.activity_stats?.imbalance_warning && (
                  <div className="config-form-group">
                    <label className="config-form-label">
                      Class imbalance detected ({curationReport.activity_stats.imbalance_ratio?.toFixed(1) ?? '—'}:1). Mitigation:
                    </label>
                    <select
                      className="config-select"
                      value={imbalanceStrategy}
                      onChange={(e) => {
                        const val = e.target.value as any;
                        setImbalanceStrategy(val);
                        setMitigation(val === 'undersample' ? 'none' : val);
                      }}
                      style={{
                        borderColor: imbalanceRecommendation ? 'var(--color-brand-600)' : undefined,
                        boxShadow: imbalanceRecommendation ? '0 0 0 1px var(--color-brand-200)' : undefined
                      }}
                    >
                      <option value="none">None</option>
                      <option value="class_weight">Class weighting (balanced)</option>
                      <option value="smote">SMOTE oversampling</option>
                      <option value="undersample">Random undersampling</option>
                    </select>
                    {imbalanceRecommendation && imbalanceStrategy === imbalanceRecommendation && (
                      <span style={{ fontSize: '9px', color: 'var(--color-brand-700)', marginTop: '2px', fontWeight: 500 }}>
                        ★ Auto-suggested: {
                          imbalanceRecommendation === 'smote' ? 'SMOTE oversampling' :
                          imbalanceRecommendation === 'class_weight' ? 'Class weighting' :
                          imbalanceRecommendation === 'undersample' ? 'Random undersampling' : 'None'
                        }
                      </span>
                    )}
                    {imbalanceStrategy === 'smote' && curationReport.activity_stats.class_counts &&
                      Math.min(curationReport.activity_stats.class_counts["0"] || 0, curationReport.activity_stats.class_counts["1"] || 0) < 6 && (
                        <span style={{ fontSize: '9px', color: 'var(--color-amber-700)', marginTop: '4px', fontWeight: 500, lineHeight: 1.2 }}>
                          ⚠️ SMOTE may be unstable with so few minority samples; consider class weighting.
                        </span>
                    )}
                  </div>
                )}
              </div>

              <FeaturizerPanel smiles={curatedSmiles || (selectedPreset === 'custom' ? (customParsedData?.smiles || []) : (selectedPreset ? PRESETS[selectedPreset].smiles : []))} />

              <div className="config-section-title">Estimator Hyperparameters</div>
              <div className="config-options-grid" style={{ marginBottom: '16px' }}>
                {selectedAlgorithm === 'Random Forest' || selectedAlgorithm === 'Gradient Boosting' ? (
                  <>
                    <div className="config-form-group">
                      <label className="config-form-label">Number of Trees</label>
                      <input
                        type="number"
                        className="config-input"
                        value={nEstimators}
                        onChange={(e) => setNEstimators(parseInt(e.target.value) || 10)}
                      />
                    </div>
                    <div className="config-form-group">
                      <label className="config-form-label">Max Depth</label>
                      <input
                        type="number"
                        className="config-input"
                        value={maxDepth}
                        onChange={(e) => setMaxDepth(parseInt(e.target.value) || 1)}
                      />
                    </div>
                  </>
                ) : selectedAlgorithm === 'SVM' ? (
                  <div className="config-form-group">
                    <label className="config-form-label">Regularization (C-parameter)</label>
                    <input
                      type="number"
                      step="0.1"
                      className="config-input"
                      value={ridgeAlpha}
                      onChange={(e) => setRidgeAlpha(parseFloat(e.target.value) || 0.1)}
                    />
                  </div>
                ) : (
                  <div className="config-form-group">
                    <label className="config-form-label">L2 Regularization (Alpha)</label>
                    <input
                      type="number"
                      step="0.1"
                      className="config-input"
                      value={ridgeAlpha}
                      onChange={(e) => setRidgeAlpha(parseFloat(e.target.value) || 0.1)}
                    />
                  </div>
                )}
              </div>

              <div className="config-form-group" style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <label className="config-form-label">Training / Validation Split</label>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-brand-700)' }}>
                    {(splitRatio * 100).toFixed(0)}% Train / {((1 - splitRatio) * 100).toFixed(0)}% Test
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="0.9"
                  step="0.05"
                  style={{ width: '100%', accentColor: 'var(--color-brand-700)', cursor: 'pointer' }}
                  value={splitRatio}
                  onChange={(e) => setSplitRatio(parseFloat(e.target.value))}
                />
              </div>

              <div className="config-section-title">Validation Strategy</div>
              <div className="config-options-grid" style={{ marginBottom: '24px' }}>
                <div className="config-form-group">
                  <label className="config-form-label">Split Mode</label>
                  <select
                    className="config-select"
                    value={splitMode}
                    onChange={(e) => setSplitMode(e.target.value as 'random' | 'stratified' | 'scaffold')}
                  >
                    <option value="random">Random (shuffle & split)</option>
                    <option value="stratified">Stratified (balanced bins)</option>
                    <option value="scaffold">Scaffold (Murcko, chemical novelty)</option>
                  </select>
                </div>
                <div className="config-form-group">
                  <label className="config-form-label">
                    CV Folds
                    <ContextualHelp topicId="studio.cv_folds" />
                  </label>
                  <select
                    className="config-select"
                    value={cvFolds}
                    onChange={(e) => setCvFolds(parseInt(e.target.value))}
                  >
                    <option value={3}>3-Fold</option>
                    <option value={5}>5-Fold (recommended)</option>
                    <option value={10}>10-Fold</option>
                    <option value={0}>Disabled</option>
                  </select>
                </div>
                <div className="config-form-group">
                  <label className="config-form-label">Random Seed</label>
                  <input
                    type="number"
                    className="config-input"
                    value={randomSeed}
                    onChange={(e) => setRandomSeed(parseInt(e.target.value) || 42)}
                  />
                </div>
                <div className="config-form-group">
                  <label className="config-form-label">Y-Scramble Iterations</label>
                  <input
                    type="number"
                    min={0}
                    max={50}
                    className="config-input"
                    value={nScramble}
                    onChange={(e) => setNScramble(Math.min(50, Math.max(0, parseInt(e.target.value) || 0)))}
                  />
                  <span style={{ fontSize: '9px', color: 'var(--color-text-400)', marginTop: '2px' }}>0 = disabled (max 50)</span>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <button className="inspector-btn" onClick={() => setWizardStep('select_data')}>
                  ← Choose Dataset
                </button>
                <button className="inspector-btn-primary" style={{ width: 'auto', padding: '6px 16px' }} onClick={handleStartTraining}>
                  🚀 Start Training Fit
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Configure Arena Mode */}
          {wizardStep === 'configure' && mode === 'arena' && (
            <div>
              <div className="wizard-step-header">
                <span className="wizard-step-title">2. Configure Arena Mode Comparison</span>
                <span className="wizard-step-indicator">Step 2 of 4</span>
              </div>

              {/* Featurizer Panel */}
              <div className="config-section-title">Featurization Settings (shared across all models)</div>
              <FeaturizerPanel smiles={curatedSmiles || (selectedPreset === 'custom' ? (customParsedData?.smiles || []) : (selectedPreset ? PRESETS[selectedPreset].smiles : []))} />

              {/* Algorithms Selector Grid */}
              <div className="config-section-title" style={{ marginTop: '20px' }}>Compare Algorithms (select 2 to 6)</div>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: '12px',
                marginBottom: '16px'
              }}>
                {[
                  { id: 'rf', name: 'Random Forest' },
                  { id: 'xgboost', name: 'XGBoost' },
                  { id: 'gbm', name: 'Gradient Boosting' },
                  { id: 'lightgbm', name: 'LightGBM', disabled: pythonInfo?.has_lgb === false, tooltip: pythonInfo?.lgb_error || 'LightGBM is disabled because the libomp library failed to load or is not present on the host.' },
                  { id: 'svm', name: 'SVM' },
                  { id: 'ridge', name: 'Ridge' },
                  { id: 'elasticnet', name: 'ElasticNet' },
                  { id: 'knn', name: 'k-NN' },
                  { id: 'mlp', name: 'MLP' }
                ].map((algo) => {
                  const isChecked = selectedAlgos.includes(algo.id);
                  return (
                    <label
                      key={algo.id}
                      title={algo.disabled ? algo.tooltip : undefined}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '10px 12px',
                        border: isChecked ? '1px solid var(--color-brand-600)' : '1px solid var(--color-border)',
                        background: algo.disabled ? 'rgba(239, 68, 68, 0.05)' : isChecked ? 'var(--color-brand-50)' : 'var(--color-surface)',
                        borderRadius: '6px',
                        cursor: algo.disabled ? 'not-allowed' : 'pointer',
                        opacity: algo.disabled ? 0.5 : 1,
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <input
                        type="checkbox"
                        disabled={algo.disabled}
                        checked={isChecked}
                        onChange={() => {
                          if (isChecked) {
                            setSelectedAlgos(selectedAlgos.filter(a => a !== algo.id));
                          } else {
                            setSelectedAlgos([...selectedAlgos, algo.id]);
                          }
                        }}
                        style={{ accentColor: 'var(--color-brand-600)' }}
                      />
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-900)' }}>
                          {algo.name}
                        </span>
                        {algo.disabled && (
                          <span style={{ fontSize: '8px', color: 'var(--color-red-700)', fontWeight: 500 }} title={algo.tooltip}>
                            ⚠️ libomp probe failed
                          </span>
                        )}
                      </div>
                    </label>
                  );
                })}
              </div>

              {/* Param Search Options */}
              <div className="config-form-group" style={{ marginBottom: '16px' }}>
                <label className="config-form-label">Hyperparameter Optimization Sweep Strategy</label>
                <div style={{ display: 'flex', gap: '20px', marginTop: '6px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '11px' }}>
                    <input
                      type="radio"
                      name="searchMode"
                      checked={searchMode === 'default'}
                      onChange={() => setSearchMode('default')}
                      style={{ accentColor: 'var(--color-brand-600)' }}
                    />
                    ◉ Default parameters (baseline fit)
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '11px' }}>
                    <input
                      type="radio"
                      name="searchMode"
                      checked={searchMode === 'bayesian_quick'}
                      onChange={() => setSearchMode('bayesian_quick')}
                      style={{ accentColor: 'var(--color-brand-600)' }}
                    />
                    ○ Bayesian optimization sweeps (quick n=20)
                  </label>
                </div>
              </div>

              {/* Split and CV folds options */}
              <div className="config-section-title">Validation Strategy (shared across all models)</div>
              <div className="config-options-grid" style={{ marginBottom: '24px', gridTemplateColumns: modelType === 'classification' && curationReport?.activity_stats?.imbalance_warning ? '1fr 1fr 1fr 1fr' : '1fr 1fr 1fr' }}>
                <div className="config-form-group">
                  <label className="config-form-label">Split Mode</label>
                  <select
                    className="config-select"
                    value={splitMode}
                    onChange={(e) => setSplitMode(e.target.value as 'random' | 'stratified' | 'scaffold')}
                  >
                    <option value="random">Random (shuffle & split)</option>
                    <option value="stratified">Stratified (balanced bins)</option>
                    <option value="scaffold">Scaffold (Murcko, chemical novelty)</option>
                  </select>
                </div>
                <div className="config-form-group">
                  <label className="config-form-label">
                    CV Folds
                    <ContextualHelp topicId="studio.cv_folds" />
                  </label>
                  <select
                    className="config-select"
                    value={cvFolds}
                    onChange={(e) => setCvFolds(parseInt(e.target.value))}
                  >
                    <option value={3}>3-Fold (fast)</option>
                    <option value={5}>5-Fold (recommended)</option>
                    <option value={10}>10-Fold (rigorous)</option>
                    <option value={0}>Disabled</option>
                  </select>
                </div>
                <div className="config-form-group">
                  <label className="config-form-label">Random Seed</label>
                  <input
                    type="number"
                    className="config-input"
                    value={randomSeed}
                    onChange={(e) => setRandomSeed(parseInt(e.target.value) || 42)}
                  />
                </div>
                {modelType === 'classification' && curationReport?.activity_stats?.imbalance_warning && (
                  <div className="config-form-group">
                    <label className="config-form-label">Imbalance Mitigation</label>
                    <select
                      className="config-select"
                      value={imbalanceStrategy}
                      onChange={(e) => {
                        const val = e.target.value as any;
                        setImbalanceStrategy(val);
                        setMitigation(val === 'undersample' ? 'none' : val);
                      }}
                      style={{
                        borderColor: imbalanceRecommendation ? 'var(--color-brand-600)' : undefined,
                        boxShadow: imbalanceRecommendation ? '0 0 0 1px var(--color-brand-200)' : undefined
                      }}
                    >
                      <option value="none">None</option>
                      <option value="class_weight">Class weighting (balanced)</option>
                      <option value="smote">SMOTE oversampling</option>
                      <option value="undersample">Random undersampling</option>
                    </select>
                    {imbalanceStrategy === 'smote' && curationReport.activity_stats.class_counts &&
                      Math.min(curationReport.activity_stats.class_counts["0"] || 0, curationReport.activity_stats.class_counts["1"] || 0) < 6 && (
                        <span style={{ fontSize: '9px', color: 'var(--color-amber-700)', marginTop: '4px', fontWeight: 500, lineHeight: 1.2 }}>
                          ⚠️ SMOTE may be unstable with so few minority samples; consider class weighting.
                        </span>
                    )}
                  </div>
                )}
              </div>

              {/* Bottom buttons */}
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <button className="inspector-btn" onClick={() => setWizardStep('select_data')}>
                  ← Choose Dataset
                </button>
                <button
                  className="inspector-btn-primary"
                  style={{ width: 'auto', padding: '6px 16px' }}
                  disabled={selectedAlgos.length < 2 || selectedAlgos.length > 6}
                  onClick={handleStartArena}
                >
                  🛡️ Start Arena Comparison →
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Training Console */}
          {wizardStep === 'training' && mode === 'single' && (
            <div>
              <div className="wizard-step-header">
                <span className="wizard-step-title">3. Execution Pipeline Stream</span>
                <span className="wizard-step-indicator">Step 3 of 4</span>
              </div>

              <div className="terminal-console">
                <div className="terminal-header">
                  <div className="terminal-dots">
                    <div className="terminal-dot red" />
                    <div className="terminal-dot yellow" />
                    <div className="terminal-dot green" />
                  </div>
                  <span className="terminal-title">EDEON ENGINE LOGS</span>
                  <div style={{ width: '28px' }} />
                </div>
                <div className="terminal-body">
                  {trainingLogs.map((log, i) => {
                    let typeClass = 'info';
                    if (log.startsWith('[SUCCESS]')) typeClass = 'success';
                    if (log.startsWith('[PROCESS]')) typeClass = 'process';
                    if (log.startsWith('[ERROR]')) typeClass = 'error';

                    return (
                      <div key={i} className={`terminal-log-line ${typeClass}`}>
                        {log}
                      </div>
                    );
                  })}
                  <div ref={terminalEndRef} />
                </div>
              </div>

              <div className="inspector-notice" style={{ background: 'var(--color-brand-100)', color: 'var(--color-brand-900)', border: '0.5px solid var(--color-brand-600)' }}>
                <span className="inspector-notice-icon">⚙</span>
                Calculating true chemical descriptors and fitting QSAR weights...
              </div>

              <div style={{ marginTop: '20px' }}>
                <ProgressIndicator
                  variant="indeterminate"
                  label="Fitting custom model estimator weights..."
                />
              </div>
            </div>
          )}

          {/* Step 3: Training Console (Arena Mode) */}
          {wizardStep === 'training' && mode === 'arena' && (
            <div>
              <div className="wizard-step-header">
                <span className="wizard-step-title">3. Multi-Model Arena Training Sweeps</span>
                <span className="wizard-step-indicator">Step 3 of 4</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', margin: '20px 0' }}>
                {selectedAlgos.map((algo) => {
                  const progress = arenaProgress[algo] || { stage: 'waiting', pct: 0 };
                  const isDone = progress.stage === 'done' || progress.pct === 100;
                  const isFailed = progress.stage === 'failed';
                  
                  return (
                    <div
                      key={algo}
                      style={{
                        background: 'var(--color-surface)',
                        border: isDone ? '1px solid var(--color-brand-600)' : isFailed ? '1px solid var(--color-red-500)' : '1px solid var(--color-border)',
                        boxShadow: isDone ? '0 0 12px rgba(23, 52, 4, 0.05)' : 'none',
                        borderRadius: '8px',
                        padding: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '12px',
                        position: 'relative',
                        overflow: 'hidden'
                      }}
                    >
                      {/* Top Label */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 700, fontSize: '12px', color: 'var(--color-text-900)' }}>
                          {ALGO_PRETTY_NAMES[algo] || algo.toUpperCase()}
                        </span>
                        <span style={{
                          fontSize: '10px',
                          fontWeight: 600,
                          color: isDone ? 'var(--color-brand-700)' : isFailed ? 'var(--color-red-700)' : 'var(--color-blue-500)',
                          background: isDone ? 'var(--color-brand-100)' : isFailed ? 'var(--color-red-100)' : 'var(--color-blue-100)',
                          padding: '2px 6px',
                          borderRadius: '4px'
                        }}>
                          {isDone ? 'done ✓' : isFailed ? 'error ✕' : progress.stage}
                        </span>
                      </div>

                      {/* Progress Bar Container */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--color-text-400)' }}>
                          <span>Stage: {progress.stage.toUpperCase()}</span>
                          <span style={{ fontWeight: 600 }}>{progress.pct}%</span>
                        </div>
                        <div style={{
                          width: '100%',
                          height: '6px',
                          background: 'var(--color-border-subtle)',
                          borderRadius: '3px',
                          overflow: 'hidden'
                        }}>
                          <div style={{
                            width: `${progress.pct}%`,
                            height: '100%',
                            background: isDone ? 'var(--color-brand-600)' : isFailed ? 'var(--color-red-500)' : 'var(--color-blue-500)',
                            borderRadius: '3px',
                            transition: 'width 0.3s ease'
                          }} />
                        </div>
                      </div>

                      {/* Bottom Info Status */}
                      <div style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>
                        {isDone ? (
                          <span style={{ color: 'var(--color-brand-700)', fontWeight: 600 }}>
                            Concurrently trained and cross-validated
                          </span>
                        ) : isFailed ? (
                          <span style={{ color: 'var(--color-red-700)' }}>
                            Worker thread encountered error
                          </span>
                        ) : progress.stage === 'waiting' ? (
                          <span>In parallel process pool queue...</span>
                        ) : (
                          <span>Executing {progress.stage.toUpperCase()} permutations...</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="inspector-notice" style={{ background: 'var(--color-blue-100)', color: 'var(--color-blue-700)', border: '0.5px solid var(--color-blue-500)' }}>
                <span className="inspector-notice-icon">⚙</span>
                Running competitive multi-model QSAR training sweeps concurrently in process worker pool.
              </div>
            </div>
          )}

          {/* Step 4: Interactive Scientific Evaluation Panel */}
          {((wizardStep === 'evaluate' && mode === 'single' && activeResults) || isViewingLibraryModel) && effectiveResults && (
            <div>
              <div className="wizard-step-header">
                <span className="wizard-step-title">
                  {effectiveResults.is_saved ? 'Library Model Evaluation Dashboard' : '4. Scientific Evaluation Dashboard'}
                </span>
                <span className="wizard-step-indicator">
                  {effectiveResults.is_saved ? 'Saved' : 'Step 4 of 4'}
                </span>
              </div>

              {/* Dashboard Tabs Toolbar */}
              <div className="dashboard-tabs" style={{ display: 'flex', gap: '16px', borderBottom: '1px solid var(--color-border)', marginBottom: '16px' }}>
                <button
                  className={`dashboard-tab ${activeTab === 'diagnostics' ? 'active' : ''}`}
                  onClick={() => setActiveTab('diagnostics')}
                  style={{
                    padding: '8px 16px',
                    background: 'none',
                    border: 'none',
                    borderBottom: activeTab === 'diagnostics' ? '2px solid var(--color-brand-600)' : '2px solid transparent',
                    color: activeTab === 'diagnostics' ? 'var(--color-brand-900)' : 'var(--color-text-400)',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  📊 Performance Diagnostics
                </button>
                <button
                  className={`dashboard-tab ${activeTab === 'why' ? 'active' : ''}`}
                  onClick={() => setActiveTab('why')}
                  style={{
                    padding: '8px 16px',
                    background: 'none',
                    border: 'none',
                    borderBottom: activeTab === 'why' ? '2px solid var(--color-brand-600)' : '2px solid transparent',
                    color: activeTab === 'why' ? 'var(--color-brand-900)' : 'var(--color-text-400)',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  🔍 Why? (Interpretability)
                </button>
              </div>

              {/* Imbalance Mitigation Badge */}
              {effectiveResults?.imbalance && effectiveResults.imbalance.strategy && effectiveResults.imbalance.strategy !== 'none' && (
                <div style={{
                  background: 'var(--color-brand-100)',
                  border: '1px solid var(--color-brand-500)',
                  borderRadius: '6px',
                  padding: '8px 12px',
                  marginBottom: '16px',
                  fontSize: '11px',
                  color: 'var(--color-brand-900)',
                  fontWeight: 500,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  ⚖️ <span>
                    Imbalance: {
                      effectiveResults.imbalance.strategy === 'class_weight' ? 'Class weighting' :
                      effectiveResults.imbalance.strategy === 'smote' ? 'SMOTE' :
                      effectiveResults.imbalance.strategy === 'undersample' ? 'Undersampling' : effectiveResults.imbalance.strategy
                    } applied — train set {
                      effectiveResults.imbalance.resampled_class_counts ? 
                        Object.values(effectiveResults.imbalance.resampled_class_counts).join('/') : 
                        (effectiveResults.imbalance.original_class_counts ? Object.values(effectiveResults.imbalance.original_class_counts).join('/') : '—')
                    }
                  </span>
                </div>
              )}

              {activeTab === 'diagnostics' && (
                <>
                  {/* KPI Cards */}
                  <div className="evaluation-kpi-grid">
                {modelType === 'regression' ? (
                  <>
                    <div className="evaluation-kpi-card">
                      <div className="evaluation-kpi-val">{getMetricBadge('r2_val', activeMetrics.r2_val)}</div>
                      <div className="evaluation-kpi-label">R² Validation</div>
                    </div>
                    <div className="evaluation-kpi-card">
                      <div className="evaluation-kpi-val">{getMetricBadge('r2_train', activeMetrics.r2_train)}</div>
                      <div className="evaluation-kpi-label">R² Training</div>
                    </div>
                    <div className="evaluation-kpi-card">
                      <div className="evaluation-kpi-val">{activeMetrics.rmse_val?.toFixed(3) ?? '—'}</div>
                      <div className="evaluation-kpi-label">RMSE Validation</div>
                    </div>
                    <div className="evaluation-kpi-card">
                      <div className="evaluation-kpi-val">{activeMetrics.mae_val?.toFixed(3) ?? '—'}</div>
                      <div className="evaluation-kpi-label">MAE Validation</div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="evaluation-kpi-card">
                      <div className="evaluation-kpi-val">{getMetricBadge('accuracy_val', activeMetrics.accuracy_val)}</div>
                      <div className="evaluation-kpi-label">Accuracy Val</div>
                    </div>
                    <div className="evaluation-kpi-card">
                      <div className="evaluation-kpi-val">{getMetricBadge('precision', activeMetrics.precision)}</div>
                      <div className="evaluation-kpi-label">Precision</div>
                    </div>
                    <div className="evaluation-kpi-card">
                      <div className="evaluation-kpi-val">{getMetricBadge('recall', activeMetrics.recall)}</div>
                      <div className="evaluation-kpi-label">Recall</div>
                    </div>
                    <div className="evaluation-kpi-card">
                      <div className="evaluation-kpi-val">{getMetricBadge('f1_score', activeMetrics.f1_score)}</div>
                      <div className="evaluation-kpi-label">F1-Score</div>
                    </div>
                  </>
                )}
              </div>

              {/* Parity Plot or Confusion Matrix & Feature importances */}
              <div className="evaluation-plots-grid">
                
                {/* Scientific Performance Diagnostics Suite */}
                <div className="plot-container-card">
                  <div className="plot-title flex justify-between items-center mb-4">
                    <span>Performance Diagnostics Panel</span>
                    <span className="text-[10px] uppercase font-bold text-[var(--color-brand-600)] bg-[var(--color-brand-50)] px-2 py-0.5 rounded-full border border-[var(--color-brand-100)]">
                      {modelType} Mode
                    </span>
                  </div>

                  {effectiveResults && (
                    <div className="mb-4">
                      <CliffsPanel
                        modelId={effectiveResults.is_saved ? effectiveResults.id : ''}
                        modelType={modelType}
                        cliffs={effectiveResults.cliffs || []}
                        onHighlightPoints={(pts) => setHighlightedPoints(pts)}
                        onRecompute={(newCliffs) => {
                          if (effectiveResults.is_saved) {
                            useModelStore.getState().fetchModels();
                          } else {
                            const updated = {
                              ...activeResults,
                              cliffs: newCliffs
                            };
                            useModelStore.getState().setActiveTrainingResults(updated);
                          }
                        }}
                      />
                    </div>
                  )}

                  <DiagnosticsPanel
                    diagnostics={effectiveResults.diagnostics}
                    modelType={modelType}
                    highlightedPoints={highlightedPoints}
                    onSelectCompound={(index) => {
                      setSelectedCompoundIndex(index);
                      setActiveTab('why');
                      setShapSubTab('waterfall');
                    }}
                  />
                </div>

                {/* Feature Importances list */}
                <div className="plot-container-card">
                  <div className="plot-title">Feature Importance Scores</div>
                  
                  <div className="eval-feature-importances">
                    {Object.entries(activeImportances)
                      .sort((a, b) => (b[1] as number) - (a[1] as number))
                      .map(([feat, val]: any) => (
                        <div key={feat} className="eval-feature-row">
                          <div className="eval-feature-header">
                            <span className="eval-feature-label">{feat}</span>
                            <span className="eval-feature-val">{(val * 100).toFixed(1)}%</span>
                          </div>
                          <div className="eval-feature-bar-bg">
                            <div className="eval-feature-bar-fill" style={{ width: `${Math.max(1, val * 100)}%` }} />
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

              </div>

              {/* Convergence Learning Curve details */}
              {activeLearningCurve.length > 0 && (
                <div className="plot-container-card" style={{ marginBottom: '16px' }}>
                  <div className="plot-title">Training Fit Convergence (Learning Curve)</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', fontWeight: 600, color: 'var(--color-text-400)', borderBottom: '0.5px solid var(--color-border)', paddingBottom: '4px' }}>
                      <span>Sub-Sample size</span>
                      <span>Training Score</span>
                      <span>Cross-Validation Score</span>
                    </div>
                    {activeLearningCurve.map((row: any, i: number) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', borderBottom: '0.5px solid var(--color-border-subtle)', paddingBottom: '3px' }}>
                        <span>{row.samples} compounds</span>
                        <span style={{ color: 'var(--color-brand-600)', fontWeight: 500 }}>{(row.train_score * 100).toFixed(0)}%</span>
                        <span style={{ color: 'var(--color-blue-500)', fontWeight: 500 }}>{(row.val_score * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Cross-Validation Stability Table */}
              {activeResults?.cv_results && activeResults.cv_results.length > 0 && (
                <div className="plot-container-card" style={{ marginBottom: '16px' }}>
                  <CvStabilityTable
                    cvResults={activeResults.cv_results}
                    modelType={modelType}
                  />
                </div>
              )}

                </>
              )}
              
              {/* Why? Tab Content */}
              {activeTab === 'why' && (
                <div style={{ marginTop: '16px', marginBottom: '16px' }}>
                  {shapLoading ? (
                    <div style={{ padding: '40px', textAlign: 'center', background: 'var(--color-surface)', borderRadius: '8px', border: '0.5px solid var(--color-border)' }}>
                      <div className="inspector-structure-loading" style={{ margin: '0 auto 12px' }}>Loading interpretability values...</div>
                      <p style={{ fontSize: '11px', color: 'var(--color-text-400)' }}>Computing TreeSHAP, LinearSHAP or downsampled KernelSHAP fallback attributions.</p>
                    </div>
                  ) : !shapSummaryData ? (
                    <div style={{ padding: '30px', textAlign: 'center', background: 'var(--color-surface)', borderRadius: '8px', border: '0.5px solid var(--color-border)', fontSize: '11px', color: 'var(--color-text-400)' }}>
                      No interpretability details available for this model.
                    </div>
                  ) : (
                    <div>
                      {/* SHAP Subtabs */}
                      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', background: 'var(--color-sidebar)', padding: '4px', borderRadius: '6px' }}>
                        {[
                          { id: 'global', name: '📊 Global Importance' },
                          { id: 'beeswarm', name: '🐝 Beeswarm Distribution' },
                          { id: 'waterfall', name: '💧 Local Waterfall' }
                        ].map(t => (
                          <button
                            key={t.id}
                            onClick={() => setShapSubTab(t.id as any)}
                            style={{
                              flex: 1,
                              padding: '6px 12px',
                              border: 'none',
                              borderRadius: '4px',
                              background: shapSubTab === t.id ? 'var(--color-surface)' : 'transparent',
                              color: shapSubTab === t.id ? 'var(--color-text-900)' : 'var(--color-text-400)',
                              fontWeight: shapSubTab === t.id ? 700 : 500,
                              fontSize: '11px',
                              boxShadow: shapSubTab === t.id ? '0 1px 3px rgba(0,0,0,0.05)' : 'none',
                              cursor: 'pointer',
                              transition: 'all 0.15s'
                            }}
                          >
                            {t.name}
                          </button>
                        ))}
                      </div>

                      {/* Global Subview */}
                      {shapSubTab === 'global' && renderGlobalView()}

                      {/* Beeswarm Subview */}
                      {shapSubTab === 'beeswarm' && renderBeeswarmView()}

                      {/* Waterfall Subview */}
                      {shapSubTab === 'waterfall' && renderWaterfallView()}
                    </div>
                  )}
                </div>
              )}
              
              {/* Y-Scrambling Sanity Check */}
              {activeResults?.y_scramble && (
                <YScramblingCard yScramble={activeResults.y_scramble} />
              )}

              {/* Save Dialog */}
              {!effectiveResults.is_saved ? (
                <div style={{ background: 'var(--color-brand-100)', border: '0.5px solid var(--color-brand-600)', borderRadius: '8px', padding: '12px', marginTop: '16px' }}>
                  <div className="config-form-group">
                    <label className="config-form-label" style={{ color: 'var(--color-brand-900)' }}>Save Model as:</label>
                    <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                      <input
                        type="text"
                        className="config-input"
                        style={{ flex: 1, background: 'var(--color-surface)' }}
                        value={saveName}
                        onChange={(e) => setSaveName(e.target.value)}
                        placeholder="Enter model name..."
                      />
                      <button
                        className="inspector-btn-primary"
                        style={{ width: 'auto', padding: '6px 16px' }}
                        disabled={!saveName.trim()}
                        onClick={() => saveActiveModel(saveName)}
                      >
                        💾 Save weights
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ background: 'var(--color-brand-50)', border: '0.5px solid var(--color-brand-400)', borderRadius: '8px', padding: '12px', marginTop: '16px', fontSize: '11px', color: 'var(--color-brand-900)', fontWeight: 500 }}>
                  ✓ Stored under library. Predictive scoring and explanations fully active.
                </div>
              )}

              <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-start' }}>
                <button
                  className="inspector-btn"
                  onClick={() => {
                    if (isViewingLibraryModel) {
                      setSelectedModelId(null);
                    }
                    resetWizard();
                  }}
                >
                  ← {isViewingLibraryModel ? 'Back to Library' : 'Back to Start'}
                </button>
              </div>

            </div>
          )}

          {/* Step 4: Arena Leaderboard Dashboard */}
          {wizardStep === 'evaluate' && mode === 'arena' && activeArenaResults && (
            <ArenaResultsView
              results={activeArenaResults}
              onClose={resetWizard}
            />
          )}

        </div>

        {/* Right Column: Saved Models Library */}
        <div className="models-library-card-container">
          <div className="wizard-step-header">
            <span className="wizard-step-title">Saved Model Library</span>
            <span className="wizard-step-indicator">{models.length} stored</span>
          </div>

          {models.length === 0 ? (
            <div className="saved-models-empty">
              <h3>No custom models saved</h3>
              <p>Train weights on a dataset and save the fitted parameters here for lead optimization scoring.</p>
            </div>
          ) : (
            <div className="models-library-list">
              {models.map((model) => {
                const isSelected = selectedModelId === model.id;
                
                let metricsObj: Record<string, number> = {};
                try {
                  metricsObj = JSON.parse(model.metrics || '{}') as Record<string, number>;
                  if (!metricsObj || typeof metricsObj !== 'object') {
                    metricsObj = {};
                  }
                } catch (e) {
                  console.error('[ERROR] Failed to parse metrics for model', model.id, e);
                }

                let provObj: any = {};
                try {
                  provObj = JSON.parse(model.provenance || '{}');
                } catch (e) {
                  console.error('[ERROR] Failed to parse provenance for model', model.id, e);
                }

                const isProvExpanded = expandedProvenanceId === model.id;

                return (
                  <div
                    key={model.id}
                    className={`saved-model-item${isSelected ? ' selected' : ''}`}
                    onClick={() => {
                      if (activeResults) {
                        if (!confirm("Discard current training results to inspect the saved model?")) {
                          return;
                        }
                      }
                      useModelStore.setState({ activeTrainingResults: null });
                      setSelectedModelId(model.id);
                      setWizardStep('evaluate');
                      setMode('single');
                      setActiveTab('diagnostics');
                    }}
                  >
                    <div className="saved-model-header">
                      <div>
                        <div className="saved-model-title">{model.name}</div>
                        <div className="saved-model-sub">{model.algorithm} · {model.type === 'regression' ? 'Regression' : 'Classification'}</div>
                        {provObj.dataset_hash ? (
                          <div className="saved-model-hash-badge" title={`Dataset Hash: ${provObj.dataset_hash}`}>
                            SHA256: <span>{provObj.dataset_hash.replace('sha256:', '').substring(0, 8)}</span>
                          </div>
                        ) : (
                          <div className="saved-model-hash-badge" style={{ borderColor: 'rgba(245, 158, 11, 0.3)', background: 'rgba(245, 158, 11, 0.05)' }} title="No provenance metadata available for this model">
                            ⚠️ <span style={{ color: 'var(--color-amber-700, #b45309)' }}>Pre-Phase-1 model — provenance unavailable</span>
                          </div>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }} onClick={(e) => e.stopPropagation()}>
                        <CitationExportButton
                          target="prediction"
                          metadata={{
                            endpoint: model.name,
                            value: 'Model Weight Parameter File',
                            model_id: model.id,
                            version: '1.0'
                          }}
                          variant="icon"
                        />
                        <button
                          className="saved-model-delete-btn"
                          title="Delete model"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm(`Are you sure you want to delete ${model.name}?`)) {
                              deleteModel(model.id);
                            }
                          }}
                        >
                          ✕
                        </button>
                      </div>
                    </div>

                    <div className="saved-model-metrics-summary">
                      {model.type === 'regression' ? (
                        <>
                          <div className="saved-model-metric-pill">
                            R² Val: <span>{metricsObj.r2_val?.toFixed(3) ?? '—'}</span>
                          </div>
                          <div className="saved-model-metric-pill">
                            RMSE: <span>{metricsObj.rmse_val?.toFixed(3) ?? '—'}</span>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="saved-model-metric-pill">
                            Acc: <span>{metricsObj.accuracy_val ? `${(metricsObj.accuracy_val * 100).toFixed(0)}%` : '—'}</span>
                          </div>
                          <div className="saved-model-metric-pill">
                            AUC: <span>{metricsObj.auc_roc ? `${(metricsObj.auc_roc * 100).toFixed(0)}%` : '—'}</span>
                          </div>
                        </>
                      )}
                    </div>

                    {/* Deployment Service Panel */}
                    <div style={{
                      marginTop: '12px',
                      paddingTop: '12px',
                      borderTop: '0.5px solid var(--color-border)',
                      fontSize: '11px'
                    }} onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span style={{ fontWeight: 600, color: 'var(--color-text-600)' }}>Pipeline Deployment:</span>
                        {model.deployment_status === 'deployed' ? (
                          <span style={{
                            background: 'rgba(16, 185, 129, 0.1)',
                            border: '0.5px solid rgba(16, 185, 129, 0.3)',
                            color: 'var(--color-emerald-700, #047857)',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            fontWeight: 600,
                            fontSize: '9px'
                          }}>
                            🟢 Deployed
                          </span>
                        ) : (
                          <span style={{
                            background: 'var(--color-surface)',
                            border: '0.5px solid var(--color-border)',
                            color: 'var(--color-text-400)',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            fontWeight: 500,
                            fontSize: '9px'
                          }}>
                            ⚪ Undeployed
                          </span>
                        )}
                      </div>

                      {model.deployment_status === 'deployed' ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <div style={{ color: 'var(--color-text-700)', fontWeight: 500 }}>
                            Target: <code style={{
                              background: 'var(--color-surface)',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              border: '0.5px solid var(--color-border)',
                              fontSize: '10px'
                            }}>{model.deploy_target}</code>
                          </div>
                          <button
                            className="saved-model-delete-btn"
                            style={{
                              width: '100%',
                              height: '28px',
                              lineHeight: '28px',
                              padding: '0',
                              borderRadius: '6px',
                              background: '#ef4444',
                              color: '#fff',
                              border: 'none',
                              fontSize: '10px',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '4px'
                            }}
                            onClick={async () => {
                              try {
                                await undeployModel(model.id);
                                alert("Model undeployed successfully!");
                              } catch (err: any) {
                                alert(`Failed to undeploy model: ${err}`);
                              }
                            }}
                          >
                            🛑 Undeploy from Pipeline
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <select
                            style={{
                              flex: 1,
                              height: '28px',
                              padding: '0 8px',
                              borderRadius: '6px',
                              border: '0.5px solid var(--color-border)',
                              background: 'var(--color-surface)',
                              color: 'var(--color-text)',
                              fontSize: '10px',
                              outline: 'none'
                            }}
                            value={selectedTargets[model.id] || (model.type === 'classification' ? 'skin_sensitization' : 'bee_acute_oral_ld50')}
                            onChange={(e) => setSelectedTargets({
                              ...selectedTargets,
                              [model.id]: e.target.value
                            })}
                          >
                            {model.type === 'classification' ? (
                              <>
                                <option value="skin_sensitization">Skin Sensitization</option>
                                <option value="eye_irritation">Eye Irritation</option>
                                <option value="photostability_class">Photostability Class</option>
                              </>
                            ) : (
                              <>
                                <option value="bee_acute_oral_ld50">Honeybee Acute Oral LD50</option>
                                <option value="bee_acute_contact_ld50">Honeybee Acute Contact LD50</option>
                                <option value="fish_acute_lc50">Fish Acute LC50</option>
                                <option value="daphnia_acute_ec50">Daphnia Acute EC50</option>
                                <option value="algae_growth_ec50">Algae Growth EC50</option>
                                <option value="earthworm_acute_lc50">Earthworm Acute LC50</option>
                                <option value="bird_acute_oral_ld50">Bird Acute Oral LD50</option>
                                <option value="rat_acute_oral_ld50">Rat Acute Oral LD50</option>
                                <option value="soil_koc">Soil Koc</option>
                                <option value="soil_dt50">Soil DT50</option>
                                <option value="gus_index">GUS Index</option>
                                <option value="bcf">Bioconcentration Factor (BCF)</option>
                                <option value="pesticide_likeness_tice">Pesticide Likeness (Tice)</option>
                              </>
                            )}
                          </select>
                          <button
                            className="inspector-btn-primary"
                            style={{
                              width: 'auto',
                              height: '28px',
                              padding: '0 12px',
                              borderRadius: '6px',
                              fontSize: '10px',
                              fontWeight: 600,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '4px',
                              minHeight: 'unset'
                            }}
                            onClick={async () => {
                              const target = selectedTargets[model.id] || (model.type === 'classification' ? 'skin_sensitization' : 'bee_acute_oral_ld50');
                              try {
                                await deployModel(model.id, target);
                                alert(`Model successfully deployed as T4 backend for ${target}!`);
                              } catch (err: any) {
                                alert(`Failed to deploy model: ${err}`);
                              }
                            }}
                          >
                            🚀 Deploy
                          </button>
                        </div>
                      )}
                    </div>

                    <div className="saved-model-provenance-toggle" onClick={(e) => {
                      e.stopPropagation();
                      setExpandedProvenanceId(isProvExpanded ? null : model.id);
                    }}>
                      {isProvExpanded ? '▼ Hide Provenance' : '► Show Provenance'}
                    </div>

                    {isProvExpanded && (
                      <div className="saved-model-provenance-content" onClick={(e) => e.stopPropagation()}>
                        <div className="provenance-actions">
                          <button
                            className="inspector-btn-primary"
                            style={{ fontSize: '9px', padding: '2px 6px', height: 'auto', minHeight: 'unset', width: 'auto' }}
                            disabled={!provObj.dataset_hash}
                            onClick={() => {
                              navigator.clipboard.writeText(JSON.stringify(provObj, null, 2));
                              alert('Provenance JSON copied to clipboard!');
                            }}
                          >
                            📋 Copy JSON
                          </button>
                        </div>
                        <pre className="provenance-pre">
                          {provObj.dataset_hash ? JSON.stringify(provObj, null, 2) : "No provenance metadata exists for this model. It was trained before Phase-1 reproducibility logs were introduced."}
                        </pre>
                      </div>
                    )}

                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}