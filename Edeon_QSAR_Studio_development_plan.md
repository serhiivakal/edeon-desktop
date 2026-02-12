**Edeon QSAR Studio — Industrial-Grade Development Plan**
1. Strategic Vision
The current Models tab is functionally a wizard for fitting one estimator at a time. To match industrial QSAR platforms (Schrödinger AutoQSAR, StarDrop, MOE, ChemAxon Trainer, KNIME), it needs to evolve into a chemoinformatically-aware modelling workbench that an agrochemical scientist can defend in a regulatory or patent context. The five competencies that separate an industrial tool from a tutorial-grade one are: defensible data curation, scientifically valid splitting (scaffold-aware, not random), applicability-domain analysis, model comparison and interpretability, and reproducible deployment to the downstream screening pipeline.

Concretely, the north-star user story is: "A discovery chemist uploads a proprietary compound set, the platform automatically curates and characterises the chemical space, trains and benchmarks a portfolio of models with chemistry-appropriate validation, surfaces interpretable structure–activity insights, and one-click deploys the best model into the MPO scoring engine — with a model card the chemist can hand to regulators."

Everything below is anchored to that story.

**Edeon QSAR Studio — Industrial-Grade Development Plan**

**1. Strategic Vision**
The current Models tab is functionally a wizard for fitting one estimator at a time. To match industrial QSAR platforms (Schrödinger AutoQSAR, StarDrop, MOE, ChemAxon Trainer, KNIME), it needs to evolve into a chemoinformatically-aware modelling workbench that an agrochemical scientist can defend in a regulatory or patent context. The five competencies that separate an industrial tool from a tutorial-grade one are: defensible data curation, scientifically valid splitting (scaffold-aware, not random), applicability-domain analysis, model comparison and interpretability, and reproducible deployment to the downstream screening pipeline.

Concretely, the north-star user story is: "A discovery chemist uploads a proprietary compound set, the platform automatically curates and characterises the chemical space, trains and benchmarks a portfolio of models with chemistry-appropriate validation, surfaces interpretable structure–activity insights, and one-click deploys the best model into the MPO scoring engine — with a model card the chemist can hand to regulators."

Everything below is anchored to that story.

**2. Current State Assessment**
The existing implementation has a solid skeleton: a four-step wizard, a presets library, a clean Rust↔Python IPC, a sklearn dual-path trainer, and a saved-model library card. The major gaps are scientific rather than cosmetic:

The data layer is opaque — there is no curation visible to the user (no canonicalisation report, salt stripping, mixture handling, duplicate aggregation, activity unit normalisation, or class-imbalance check), and the activity distribution is never shown. The splitting strategy is a positional [:split_idx] slice in models_training.py which will silently produce optimistic metrics whenever the input CSV is sorted by activity; there is no random shuffling, no stratification, no scaffold split, and no k-fold CV. The featurization layer has no MACCS, Avalon, RDKit topological, atom-pair, or pharmacophore fingerprints; descriptor selection is hardcoded to six values; fingerprint radius and bit count are not configurable. The training offers no hyperparameter search, no class weighting, no early stopping, and no Y-scrambling/permutation test. The evaluation lacks ROC/PR curves, calibration plots, residual diagnostics, applicability-domain analysis, and external test set support. The interpretability is limited to global feature importances — no SHAP values, no per-prediction explanations, no atom-level contribution maps. The sandbox prediction described in the file overview is not actually implemented in the UI. The library is a flat list with no versioning, lineage, model cards, or deployment status. And there is no bridge to the MPO scoring engine in scoring.py — saved models are dead weights.

**3. Phased Roadmap**
The plan is structured in four phases over what would realistically be a 10–14 week roll-out. Each phase ends with a usable, shippable increment.

**Phase 1 — Scientific Foundations (Weeks 1–3)**
Goal: Make every metric that comes out of the trainer defensible. Nothing else matters until this is true.

- ***Data curation pipeline.*** Insert a deterministic pre-processing step in models_training.py that runs before featurization: SMILES canonicalisation via RDKit, salt/solvent stripping using SaltRemover, neutralisation of charged forms, fragment selection (keep largest organic component), rejection of compounds with disallowed atoms, and aggregation of duplicates by mean (regression) or majority vote (classification) with conflict warnings. Return a structured curation_report to the UI: {n_input, n_canonicalised, n_salts_stripped, n_duplicates_merged, n_invalid, n_final, warnings: []}. Surface this as a dedicated "Curation Report" panel between Step 1 and Step 2 of the wizard so the user explicitly accepts the cleaned set before training.

- ***Activity distribution & class-balance preview.*** Right after curation, render a histogram (regression) or stacked bar (classification) of activities using recharts. For regression, show min/max/median/IQR and flag if the dynamic range is < 2 log units (insufficient signal). For classification, show class counts and flag imbalance ratios > 3:1 with a recommendation for class weighting or SMOTE.

- ***Replace the broken split with proper validation.*** This is the single most important change. Implement three split modes in models_training.py:

- ***Random shuffle split with seed (default for novice users)***
Scaffold split using Bemis–Murcko scaffolds via rdkit.Chem.Scaffolds.MurckoScaffold (default for chemistry-aware users — single most differentiated feature)
Stratified split (classification) and activity-stratified (regression, binned)
Add k-fold cross-validation (default k=5) and surface fold-by-fold scores (mean ± std) in the evaluation panel. The current point-estimate metrics are misleading on the small datasets in PRESETS (n=20).

- ***Y-scrambling test.*** Run a 10-iteration permutation test with shuffled labels and report the mean R²/accuracy of scrambled models. The user must see a clear gap between true and scrambled performance to trust the model. This is an OECD QSAR validation principle and a regulatory expectation.

- ***Reproducibility.*** Persist random_state, RDKit version, sklearn version, feature list, hyperparameters, and curation flags into the SavedModel record so any model can be retrained byte-identically.

**Phase 2 — Chemistry-Aware Featurization & Model Portfolio (Weeks 4–6)**
Goal: Move from "one model, one feature set" to "compare a portfolio of models on the same data".

- ***Featurization expansion.*** Refactor the descriptor checklist into a tabbed featurizer panel:

- ***2D Descriptors:*** full RDKit set (~200), with a search/filter input and pre-baked groups (Lipinski, Tice, Constitutional, Topological, Electrotopological)
Fingerprints: Morgan/ECFP (configurable radius 1–4, bits 512/1024/2048), FCFP (feature-based Morgan), MACCS (166), Avalon, RDKit topological, atom-pair, topological torsion
Pharmacophore-based: 2D pharmacophore fingerprints, Gobbi 2D pharm
Custom: free-text RDKit descriptor expression for power users
Each featurizer block reports its dimensionality and computation cost in real time so the user understands the train-time implications.

- ***Hyperparameter search.*** Replace the static hyperparameter inputs with three modes: Manual (current behaviour), Grid Search (user-defined grid with checkbox presets), Bayesian (Optuna with n_trials slider). Stream search progress through the same training-log channel — each trial reports its CV score so the terminal becomes a live optimisation dashboard.

- ***Model portfolio / arena mode.*** Introduce an "Arena" entry point alongside the single-model wizard: the user picks a featurization once and ticks 2–6 algorithms to train in parallel (RF, GBM, XGBoost via xgboost, LightGBM, SVM, Ridge, ElasticNet, k-NN, MLP). Results display as a sortable table with R²/RMSE/AUC/F1 columns and small inline parity-plot sparklines per model. Selecting a row drills into the full evaluation dashboard. This single feature collapses what is currently 6 wizard runs into one and is the headline differentiator vs. tutorial-grade tools.

- ***Class weighting and resampling for imbalance.*** When the imbalance flag fires in Phase 1, enable a "Handle imbalance" dropdown: None / class_weight=balanced / SMOTE / undersample. Wire to imbalanced-learn (imblearn).

**Phase 3 — Interpretability, Applicability Domain & Diagnostics (Weeks 7–9)**
Goal: Tell the chemist why a prediction is what it is, and when not to trust the model.

- Applicability Domain (AD). Implement two complementary AD methods:

- Tanimoto-based: for any query compound, distance to k-nearest training compounds in fingerprint space. Threshold = 95th percentile of training intra-distance.
Leverage / hat matrix: for descriptor-based models, classical Williams plot.
Render a Williams plot (standardised residual vs leverage) on the evaluation dashboard with the AD threshold marked, and tag every validation-set prediction as In-AD / Borderline / Out-of-AD. Critically, at prediction time in scoring.py, return the AD flag alongside the prediction so the MPO engine can downweight low-confidence predictions.

- SHAP-based interpretability. Add a "Why?" tab in the evaluation dashboard. For tree models, compute TreeSHAP on the validation set and render: (1) a global feature-importance bar with proper SHAP values replacing the current Gini importances; (2) a beeswarm summary plot; (3) per-compound waterfall plots — clickable from the parity plot points. For linear models, fall back to standardised coefficients.

- Atom-level contribution maps. For Morgan-based models, compute per-bit SHAP and project back to atoms via the bit-info dict from GetMorganFingerprintAsBitVect(useFeatures=False, bitInfo=...). Render the molecule as 2D depiction with red/blue atom highlights using RDKit's SimilarityMaps.GetSimilarityMapFromWeights rasterised to PNG. This is the visual that sells the tool to a medicinal chemist — and it is fully implementable on top of your current Morgan featurizer.

- Diagnostic plot suite. Replace the single parity plot / confusion matrix with a tabbed diagnostics panel:

Regression: parity (with AD colouring), residual-vs-fitted, residual histogram, Q-Q plot, learning curve, Y-scrambling distribution
Classification: confusion matrix, ROC curve (with CI band from CV folds), Precision-Recall curve, calibration plot, threshold-vs-F1 sweep slider, class-probability histogram
Use recharts for everything except the molecular images.

Activity cliffs panel. Identify pairs in the training set with high structural similarity (Tanimoto > 0.85) but large activity gap (>1 log unit) and show them in a small "Activity Cliffs Detected" warning card with thumbnails. This is what separates a chemist's tool from a generic ML tool.

**Phase 4 — Deployment, Library & Sandbox (Weeks 10–12)**
Goal: Turn the trained model into something the rest of Edeon and the user actually use.

Prediction sandbox. Implement the missing prediction UI: a drawer-style panel accessible from any saved model card, with three input modes — single SMILES (with RDKit-rendered preview as the user types), batch paste (one SMILES per line), CSV upload. Predictions render in a sortable table with: structure thumbnail, prediction value, prediction interval (from CV-based bootstrap or quantile RF), AD flag, top-3 SHAP contributors. Add an "Add to Project" button that pushes results into the existing screening dataset.

Model versioning & lineage. Extend the saved_models schema with version, parent_id, dataset_hash, git_like_changelog. When a user retrains with a tweaked hyperparameter, it becomes v2 of the same logical model rather than a new entry. Render the library as collapsible groups with version chips, last-trained date, and a deployment-status badge (Draft / Validated / Production).

Model cards. Auto-generate a one-page Markdown/PDF model card per saved model containing: dataset metadata, curation report, split strategy, hyperparameters, full metric table with CV ± std, Y-scramble baseline, AD definition, intended use, known limitations. This is increasingly an EU regulatory expectation under the AI Act and a EFSA/EPA hygiene factor for QSAR submissions.

Bridge to MPO scoring. Currently scoring.py ignores the saved-models table entirely. Add a custom_models weight stage to compute_mpo_score and a model-picker in the MPO weights UI. At scoring time, load the relevant model's metrics, features, and serialized estimator (joblib pickle stored on disk under ~/.edeon/models/{id}.joblib), run prediction with AD check, and feed the value into the composite score with confidence-weighting.

Export. Allow exporting saved models as joblib (sklearn-native), ONNX (cross-platform inference), and a self-contained Python package with predict.py script for IT-restricted environments. ONNX is non-trivial for tree models with skl2onnx but worth it for the deployment story.

4. Cross-Cutting Improvements
These touch every phase and should be developed in parallel.

Backend architecture. The current trainer is a single ~400-line monolith. Split models_training.py into modules: curation.py, featurizers.py, splitters.py, trainers.py, evaluators.py, interpreters.py, persistence.py. Each is independently testable, and the IPC surface from Rust simplifies to four calls (curate, featurize_preview, train, predict).

Streaming progress instead of fake logs. The current trainModel in modelStore.ts emits scripted progress lines on a timer while the real work happens opaquely. Replace with a Tauri event channel (tauri::EventHandler) that the Python side emits structured JSON events to: {stage: "curation"|"featurize"|"cv_fold"|"hpo_trial"|"final", progress: 0–1, message: "...", payload: {...}}. The frontend renders a real progress bar with stage chips. This is also necessary for HPO which can take minutes.

Cancellation. Long HPO runs need a cancel button wired through mpsc::channel to the Python process so users aren't held hostage by a runaway grid search.

UI design system consistency. The current styling (config-section-title, evaluation-kpi-card, etc.) is good but dense. For the diagnostic plots tab, adopt a consistent chart wrapper component (<DiagnosticChart title icon helpText>{children}</DiagnosticChart>) with a consistent help-tooltip pattern using lucide-react's HelpCircle so every chart gets a one-sentence layperson explanation. Industrial QSAR tools succeed or fail on whether non-statisticians trust the output, and inline help is the cheapest trust-builder.

Tests. Add a backend test fixture using the public Delaney solubility set (n=1128) and AMES mutagenicity (n=6512) — these are gold-standard QSAR benchmarks. CI should fail if model R² regresses below known thresholds (~0.85 for Delaney with Morgan+RF). Without this, refactors silently degrade scientific quality.

5. Prioritisation & Quick Wins
If only one week of work is available before a demo, the highest-value moves are: fix the broken split (random shuffle + k-fold), add the curation report, add scaffold split, and replace the synthetic learning curve in models_training.py (r2_tr_sim = metrics["r2_train"] + noise) with a real sklearn.model_selection.learning_curve call. Those four changes alone move the tool from "demo-grade" to "defensible".

If two weeks: add the Arena multi-model comparison and SHAP-based feature importance — both have outsized perceived value relative to implementation cost because tree-based SHAP is one library import and a few hundred lines of plotting.

If a quarter: execute the full Phase 1–3 plan, ship Phase 4 in increments. The deployment-to-MPO bridge is the single feature that converts the Models tab from an isolated playground into a competitive moat for Edeon, because it operationalises bespoke chemistry models inside the screening pipeline — something Schrödinger and StarDrop charge five-figure annual seats for.

6. Risks & Mitigations
The largest technical risk is dataset size. The current presets are n=20, which is below the 50–100 minimum for honest QSAR. Mitigate by (a) bundling a few public reference datasets (Delaney, Lipophilicity, Tox21 subsets) explicitly labelled as "Reference benchmarks", and (b) showing a hard-coded warning when n < 50 explaining that the model is illustrative.

The second risk is Python dependency weight: SHAP, Optuna, XGBoost, LightGBM, imbalanced-learn, ONNX add ~400 MB to the bundle. Mitigate by lazy-importing inside trainer functions and shipping them as optional plugins that download on first use — Tauri's sidecar mechanism handles this cleanly.

The third risk is overfitting the wizard with options. The wizard already has four steps; adding HPO modes, scaffold splits, fingerprint radius selectors, etc. risks paralysis. Mitigate with a strong "Quick" / "Advanced" toggle at the top of Step 2 that hides 80% of controls behind sensible defaults — defaults that are themselves a feature of an industrial tool.Edeon QSAR Studio — Industrial-Grade Development Plan
1. Strategic Vision
The current Models tab is functionally a wizard for fitting one estimator at a time. To match industrial QSAR platforms (Schrödinger AutoQSAR, StarDrop, MOE, ChemAxon Trainer, KNIME), it needs to evolve into a chemoinformatically-aware modelling workbench that an agrochemical scientist can defend in a regulatory or patent context. The five competencies that separate an industrial tool from a tutorial-grade one are: defensible data curation, scientifically valid splitting (scaffold-aware, not random), applicability-domain analysis, model comparison and interpretability, and reproducible deployment to the downstream screening pipeline.

Concretely, the north-star user story is: "A discovery chemist uploads a proprietary compound set, the platform automatically curates and characterises the chemical space, trains and benchmarks a portfolio of models with chemistry-appropriate validation, surfaces interpretable structure–activity insights, and one-click deploys the best model into the MPO scoring engine — with a model card the chemist can hand to regulators."

Everything below is anchored to that story.

2. Current State Assessment
The existing implementation has a solid skeleton: a four-step wizard, a presets library, a clean Rust↔Python IPC, a sklearn dual-path trainer, and a saved-model library card. The major gaps are scientific rather than cosmetic:

The data layer is opaque — there is no curation visible to the user (no canonicalisation report, salt stripping, mixture handling, duplicate aggregation, activity unit normalisation, or class-imbalance check), and the activity distribution is never shown. The splitting strategy is a positional [:split_idx] slice in models_training.py which will silently produce optimistic metrics whenever the input CSV is sorted by activity; there is no random shuffling, no stratification, no scaffold split, and no k-fold CV. The featurization layer has no MACCS, Avalon, RDKit topological, atom-pair, or pharmacophore fingerprints; descriptor selection is hardcoded to six values; fingerprint radius and bit count are not configurable. The training offers no hyperparameter search, no class weighting, no early stopping, and no Y-scrambling/permutation test. The evaluation lacks ROC/PR curves, calibration plots, residual diagnostics, applicability-domain analysis, and external test set support. The interpretability is limited to global feature importances — no SHAP values, no per-prediction explanations, no atom-level contribution maps. The sandbox prediction described in the file overview is not actually implemented in the UI. The library is a flat list with no versioning, lineage, model cards, or deployment status. And there is no bridge to the MPO scoring engine in scoring.py — saved models are dead weights.

3. Phased Roadmap
The plan is structured in four phases over what would realistically be a 10–14 week roll-out. Each phase ends with a usable, shippable increment.

Phase 1 — Scientific Foundations (Weeks 1–3)
Goal: Make every metric that comes out of the trainer defensible. Nothing else matters until this is true.

Data curation pipeline. Insert a deterministic pre-processing step in models_training.py that runs before featurization: SMILES canonicalisation via RDKit, salt/solvent stripping using SaltRemover, neutralisation of charged forms, fragment selection (keep largest organic component), rejection of compounds with disallowed atoms, and aggregation of duplicates by mean (regression) or majority vote (classification) with conflict warnings. Return a structured curation_report to the UI: {n_input, n_canonicalised, n_salts_stripped, n_duplicates_merged, n_invalid, n_final, warnings: []}. Surface this as a dedicated "Curation Report" panel between Step 1 and Step 2 of the wizard so the user explicitly accepts the cleaned set before training.

Activity distribution & class-balance preview. Right after curation, render a histogram (regression) or stacked bar (classification) of activities using recharts. For regression, show min/max/median/IQR and flag if the dynamic range is < 2 log units (insufficient signal). For classification, show class counts and flag imbalance ratios > 3:1 with a recommendation for class weighting or SMOTE.

Replace the broken split with proper validation. This is the single most important change. Implement three split modes in models_training.py:

Random shuffle split with seed (default for novice users)
Scaffold split using Bemis–Murcko scaffolds via rdkit.Chem.Scaffolds.MurckoScaffold (default for chemistry-aware users — single most differentiated feature)
Stratified split (classification) and activity-stratified (regression, binned)
Add k-fold cross-validation (default k=5) and surface fold-by-fold scores (mean ± std) in the evaluation panel. The current point-estimate metrics are misleading on the small datasets in PRESETS (n=20).

Y-scrambling test. Run a 10-iteration permutation test with shuffled labels and report the mean R²/accuracy of scrambled models. The user must see a clear gap between true and scrambled performance to trust the model. This is an OECD QSAR validation principle and a regulatory expectation.

Reproducibility. Persist random_state, RDKit version, sklearn version, feature list, hyperparameters, and curation flags into the SavedModel record so any model can be retrained byte-identically.

Phase 2 — Chemistry-Aware Featurization & Model Portfolio (Weeks 4–6)
Goal: Move from "one model, one feature set" to "compare a portfolio of models on the same data".

Featurization expansion. Refactor the descriptor checklist into a tabbed featurizer panel:

2D Descriptors: full RDKit set (~200), with a search/filter input and pre-baked groups (Lipinski, Tice, Constitutional, Topological, Electrotopological)
Fingerprints: Morgan/ECFP (configurable radius 1–4, bits 512/1024/2048), FCFP (feature-based Morgan), MACCS (166), Avalon, RDKit topological, atom-pair, topological torsion
Pharmacophore-based: 2D pharmacophore fingerprints, Gobbi 2D pharm
Custom: free-text RDKit descriptor expression for power users
Each featurizer block reports its dimensionality and computation cost in real time so the user understands the train-time implications.

Hyperparameter search. Replace the static hyperparameter inputs with three modes: Manual (current behaviour), Grid Search (user-defined grid with checkbox presets), Bayesian (Optuna with n_trials slider). Stream search progress through the same training-log channel — each trial reports its CV score so the terminal becomes a live optimisation dashboard.

Model portfolio / arena mode. Introduce an "Arena" entry point alongside the single-model wizard: the user picks a featurization once and ticks 2–6 algorithms to train in parallel (RF, GBM, XGBoost via xgboost, LightGBM, SVM, Ridge, ElasticNet, k-NN, MLP). Results display as a sortable table with R²/RMSE/AUC/F1 columns and small inline parity-plot sparklines per model. Selecting a row drills into the full evaluation dashboard. This single feature collapses what is currently 6 wizard runs into one and is the headline differentiator vs. tutorial-grade tools.

Class weighting and resampling for imbalance. When the imbalance flag fires in Phase 1, enable a "Handle imbalance" dropdown: None / class_weight=balanced / SMOTE / undersample. Wire to imbalanced-learn (imblearn).

Phase 3 — Interpretability, Applicability Domain & Diagnostics (Weeks 7–9)
Goal: Tell the chemist why a prediction is what it is, and when not to trust the model.

Applicability Domain (AD). Implement two complementary AD methods:

Tanimoto-based: for any query compound, distance to k-nearest training compounds in fingerprint space. Threshold = 95th percentile of training intra-distance.
Leverage / hat matrix: for descriptor-based models, classical Williams plot.
Render a Williams plot (standardised residual vs leverage) on the evaluation dashboard with the AD threshold marked, and tag every validation-set prediction as In-AD / Borderline / Out-of-AD. Critically, at prediction time in scoring.py, return the AD flag alongside the prediction so the MPO engine can downweight low-confidence predictions.

SHAP-based interpretability. Add a "Why?" tab in the evaluation dashboard. For tree models, compute TreeSHAP on the validation set and render: (1) a global feature-importance bar with proper SHAP values replacing the current Gini importances; (2) a beeswarm summary plot; (3) per-compound waterfall plots — clickable from the parity plot points. For linear models, fall back to standardised coefficients.

Atom-level contribution maps. For Morgan-based models, compute per-bit SHAP and project back to atoms via the bit-info dict from GetMorganFingerprintAsBitVect(useFeatures=False, bitInfo=...). Render the molecule as 2D depiction with red/blue atom highlights using RDKit's SimilarityMaps.GetSimilarityMapFromWeights rasterised to PNG. This is the visual that sells the tool to a medicinal chemist — and it is fully implementable on top of your current Morgan featurizer.

Diagnostic plot suite. Replace the single parity plot / confusion matrix with a tabbed diagnostics panel:

Regression: parity (with AD colouring), residual-vs-fitted, residual histogram, Q-Q plot, learning curve, Y-scrambling distribution
Classification: confusion matrix, ROC curve (with CI band from CV folds), Precision-Recall curve, calibration plot, threshold-vs-F1 sweep slider, class-probability histogram
Use recharts for everything except the molecular images.

Activity cliffs panel. Identify pairs in the training set with high structural similarity (Tanimoto > 0.85) but large activity gap (>1 log unit) and show them in a small "Activity Cliffs Detected" warning card with thumbnails. This is what separates a chemist's tool from a generic ML tool.

Phase 4 — Deployment, Library & Sandbox (Weeks 10–12)
Goal: Turn the trained model into something the rest of Edeon and the user actually use.

Prediction sandbox. Implement the missing prediction UI: a drawer-style panel accessible from any saved model card, with three input modes — single SMILES (with RDKit-rendered preview as the user types), batch paste (one SMILES per line), CSV upload. Predictions render in a sortable table with: structure thumbnail, prediction value, prediction interval (from CV-based bootstrap or quantile RF), AD flag, top-3 SHAP contributors. Add an "Add to Project" button that pushes results into the existing screening dataset.

Model versioning & lineage. Extend the saved_models schema with version, parent_id, dataset_hash, git_like_changelog. When a user retrains with a tweaked hyperparameter, it becomes v2 of the same logical model rather than a new entry. Render the library as collapsible groups with version chips, last-trained date, and a deployment-status badge (Draft / Validated / Production).

Model cards. Auto-generate a one-page Markdown/PDF model card per saved model containing: dataset metadata, curation report, split strategy, hyperparameters, full metric table with CV ± std, Y-scramble baseline, AD definition, intended use, known limitations. This is increasingly an EU regulatory expectation under the AI Act and a EFSA/EPA hygiene factor for QSAR submissions.

Bridge to MPO scoring. Currently scoring.py ignores the saved-models table entirely. Add a custom_models weight stage to compute_mpo_score and a model-picker in the MPO weights UI. At scoring time, load the relevant model's metrics, features, and serialized estimator (joblib pickle stored on disk under ~/.edeon/models/{id}.joblib), run prediction with AD check, and feed the value into the composite score with confidence-weighting.

Export. Allow exporting saved models as joblib (sklearn-native), ONNX (cross-platform inference), and a self-contained Python package with predict.py script for IT-restricted environments. ONNX is non-trivial for tree models with skl2onnx but worth it for the deployment story.

4. Cross-Cutting Improvements
These touch every phase and should be developed in parallel.

Backend architecture. The current trainer is a single ~400-line monolith. Split models_training.py into modules: curation.py, featurizers.py, splitters.py, trainers.py, evaluators.py, interpreters.py, persistence.py. Each is independently testable, and the IPC surface from Rust simplifies to four calls (curate, featurize_preview, train, predict).

Streaming progress instead of fake logs. The current trainModel in modelStore.ts emits scripted progress lines on a timer while the real work happens opaquely. Replace with a Tauri event channel (tauri::EventHandler) that the Python side emits structured JSON events to: {stage: "curation"|"featurize"|"cv_fold"|"hpo_trial"|"final", progress: 0–1, message: "...", payload: {...}}. The frontend renders a real progress bar with stage chips. This is also necessary for HPO which can take minutes.

Cancellation. Long HPO runs need a cancel button wired through mpsc::channel to the Python process so users aren't held hostage by a runaway grid search.

UI design system consistency. The current styling (config-section-title, evaluation-kpi-card, etc.) is good but dense. For the diagnostic plots tab, adopt a consistent chart wrapper component (<DiagnosticChart title icon helpText>{children}</DiagnosticChart>) with a consistent help-tooltip pattern using lucide-react's HelpCircle so every chart gets a one-sentence layperson explanation. Industrial QSAR tools succeed or fail on whether non-statisticians trust the output, and inline help is the cheapest trust-builder.

Tests. Add a backend test fixture using the public Delaney solubility set (n=1128) and AMES mutagenicity (n=6512) — these are gold-standard QSAR benchmarks. CI should fail if model R² regresses below known thresholds (~0.85 for Delaney with Morgan+RF). Without this, refactors silently degrade scientific quality.

5. Prioritisation & Quick Wins
If only one week of work is available before a demo, the highest-value moves are: fix the broken split (random shuffle + k-fold), add the curation report, add scaffold split, and replace the synthetic learning curve in models_training.py (r2_tr_sim = metrics["r2_train"] + noise) with a real sklearn.model_selection.learning_curve call. Those four changes alone move the tool from "demo-grade" to "defensible".

If two weeks: add the Arena multi-model comparison and SHAP-based feature importance — both have outsized perceived value relative to implementation cost because tree-based SHAP is one library import and a few hundred lines of plotting.

If a quarter: execute the full Phase 1–3 plan, ship Phase 4 in increments. The deployment-to-MPO bridge is the single feature that converts the Models tab from an isolated playground into a competitive moat for Edeon, because it operationalises bespoke chemistry models inside the screening pipeline — something Schrödinger and StarDrop charge five-figure annual seats for.

6. Risks & Mitigations
The largest technical risk is dataset size. The current presets are n=20, which is below the 50–100 minimum for honest QSAR. Mitigate by (a) bundling a few public reference datasets (Delaney, Lipophilicity, Tox21 subsets) explicitly labelled as "Reference benchmarks", and (b) showing a hard-coded warning when n < 50 explaining that the model is illustrative.

The second risk is Python dependency weight: SHAP, Optuna, XGBoost, LightGBM, imbalanced-learn, ONNX add ~400 MB to the bundle. Mitigate by lazy-importing inside trainer functions and shipping them as optional plugins that download on first use — Tauri's sidecar mechanism handles this cleanly.

The third risk is overfitting the wizard with options. The wizard already has four steps; adding HPO modes, scaffold splits, fingerprint radius selectors, etc. risks paralysis. Mitigate with a strong "Quick" / "Advanced" toggle at the top of Step 2 that hides 80% of controls behind sensible defaults — defaults that are themselves a feature of an industrial tool.
The existing implementation has a solid skeleton: a four-step wizard, a presets library, a clean Rust↔Python IPC, a sklearn dual-path trainer, and a saved-model library card. The major gaps are scientific rather than cosmetic:

The data layer is opaque — there is no curation visible to the user (no canonicalisation report, salt stripping, mixture handling, duplicate aggregation, activity unit normalisation, or class-imbalance check), and the activity distribution is never shown. The splitting strategy is a positional [:split_idx] slice in models_training.py which will silently produce optimistic metrics whenever the input CSV is sorted by activity; there is no random shuffling, no stratification, no scaffold split, and no k-fold CV. The featurization layer has no MACCS, Avalon, RDKit topological, atom-pair, or pharmacophore fingerprints; descriptor selection is hardcoded to six values; fingerprint radius and bit count are not configurable. The training offers no hyperparameter search, no class weighting, no early stopping, and no Y-scrambling/permutation test. The evaluation lacks ROC/PR curves, calibration plots, residual diagnostics, applicability-domain analysis, and external test set support. The interpretability is limited to global feature importances — no SHAP values, no per-prediction explanations, no atom-level contribution maps. The sandbox prediction described in the file overview is not actually implemented in the UI. The library is a flat list with no versioning, lineage, model cards, or deployment status. And there is no bridge to the MPO scoring engine in scoring.py — saved models are dead weights.

3. Phased Roadmap
The plan is structured in four phases over what would realistically be a 10–14 week roll-out. Each phase ends with a usable, shippable increment.

Phase 1 — Scientific Foundations (Weeks 1–3)
Goal: Make every metric that comes out of the trainer defensible. Nothing else matters until this is true.

Data curation pipeline. Insert a deterministic pre-processing step in models_training.py that runs before featurization: SMILES canonicalisation via RDKit, salt/solvent stripping using SaltRemover, neutralisation of charged forms, fragment selection (keep largest organic component), rejection of compounds with disallowed atoms, and aggregation of duplicates by mean (regression) or majority vote (classification) with conflict warnings. Return a structured curation_report to the UI: {n_input, n_canonicalised, n_salts_stripped, n_duplicates_merged, n_invalid, n_final, warnings: []}. Surface this as a dedicated "Curation Report" panel between Step 1 and Step 2 of the wizard so the user explicitly accepts the cleaned set before training.

Activity distribution & class-balance preview. Right after curation, render a histogram (regression) or stacked bar (classification) of activities using recharts. For regression, show min/max/median/IQR and flag if the dynamic range is < 2 log units (insufficient signal). For classification, show class counts and flag imbalance ratios > 3:1 with a recommendation for class weighting or SMOTE.

Replace the broken split with proper validation. This is the single most important change. Implement three split modes in models_training.py:

Random shuffle split with seed (default for novice users)
Scaffold split using Bemis–Murcko scaffolds via rdkit.Chem.Scaffolds.MurckoScaffold (default for chemistry-aware users — single most differentiated feature)
Stratified split (classification) and activity-stratified (regression, binned)
Add k-fold cross-validation (default k=5) and surface fold-by-fold scores (mean ± std) in the evaluation panel. The current point-estimate metrics are misleading on the small datasets in PRESETS (n=20).

Y-scrambling test. Run a 10-iteration permutation test with shuffled labels and report the mean R²/accuracy of scrambled models. The user must see a clear gap between true and scrambled performance to trust the model. This is an OECD QSAR validation principle and a regulatory expectation.

Reproducibility. Persist random_state, RDKit version, sklearn version, feature list, hyperparameters, and curation flags into the SavedModel record so any model can be retrained byte-identically.

Phase 2 — Chemistry-Aware Featurization & Model Portfolio (Weeks 4–6)
Goal: Move from "one model, one feature set" to "compare a portfolio of models on the same data".

Featurization expansion. Refactor the descriptor checklist into a tabbed featurizer panel:

2D Descriptors: full RDKit set (~200), with a search/filter input and pre-baked groups (Lipinski, Tice, Constitutional, Topological, Electrotopological)
Fingerprints: Morgan/ECFP (configurable radius 1–4, bits 512/1024/2048), FCFP (feature-based Morgan), MACCS (166), Avalon, RDKit topological, atom-pair, topological torsion
Pharmacophore-based: 2D pharmacophore fingerprints, Gobbi 2D pharm
Custom: free-text RDKit descriptor expression for power users
Each featurizer block reports its dimensionality and computation cost in real time so the user understands the train-time implications.

Hyperparameter search. Replace the static hyperparameter inputs with three modes: Manual (current behaviour), Grid Search (user-defined grid with checkbox presets), Bayesian (Optuna with n_trials slider). Stream search progress through the same training-log channel — each trial reports its CV score so the terminal becomes a live optimisation dashboard.

Model portfolio / arena mode. Introduce an "Arena" entry point alongside the single-model wizard: the user picks a featurization once and ticks 2–6 algorithms to train in parallel (RF, GBM, XGBoost via xgboost, LightGBM, SVM, Ridge, ElasticNet, k-NN, MLP). Results display as a sortable table with R²/RMSE/AUC/F1 columns and small inline parity-plot sparklines per model. Selecting a row drills into the full evaluation dashboard. This single feature collapses what is currently 6 wizard runs into one and is the headline differentiator vs. tutorial-grade tools.

Class weighting and resampling for imbalance. When the imbalance flag fires in Phase 1, enable a "Handle imbalance" dropdown: None / class_weight=balanced / SMOTE / undersample. Wire to imbalanced-learn (imblearn).

Phase 3 — Interpretability, Applicability Domain & Diagnostics (Weeks 7–9)
Goal: Tell the chemist why a prediction is what it is, and when not to trust the model.

Applicability Domain (AD). Implement two complementary AD methods:

Tanimoto-based: for any query compound, distance to k-nearest training compounds in fingerprint space. Threshold = 95th percentile of training intra-distance.
Leverage / hat matrix: for descriptor-based models, classical Williams plot.
Render a Williams plot (standardised residual vs leverage) on the evaluation dashboard with the AD threshold marked, and tag every validation-set prediction as In-AD / Borderline / Out-of-AD. Critically, at prediction time in scoring.py, return the AD flag alongside the prediction so the MPO engine can downweight low-confidence predictions.

SHAP-based interpretability. Add a "Why?" tab in the evaluation dashboard. For tree models, compute TreeSHAP on the validation set and render: (1) a global feature-importance bar with proper SHAP values replacing the current Gini importances; (2) a beeswarm summary plot; (3) per-compound waterfall plots — clickable from the parity plot points. For linear models, fall back to standardised coefficients.

Atom-level contribution maps. For Morgan-based models, compute per-bit SHAP and project back to atoms via the bit-info dict from GetMorganFingerprintAsBitVect(useFeatures=False, bitInfo=...). Render the molecule as 2D depiction with red/blue atom highlights using RDKit's SimilarityMaps.GetSimilarityMapFromWeights rasterised to PNG. This is the visual that sells the tool to a medicinal chemist — and it is fully implementable on top of your current Morgan featurizer.

Diagnostic plot suite. Replace the single parity plot / confusion matrix with a tabbed diagnostics panel:

Regression: parity (with AD colouring), residual-vs-fitted, residual histogram, Q-Q plot, learning curve, Y-scrambling distribution
Classification: confusion matrix, ROC curve (with CI band from CV folds), Precision-Recall curve, calibration plot, threshold-vs-F1 sweep slider, class-probability histogram
Use recharts for everything except the molecular images.

Activity cliffs panel. Identify pairs in the training set with high structural similarity (Tanimoto > 0.85) but large activity gap (>1 log unit) and show them in a small "Activity Cliffs Detected" warning card with thumbnails. This is what separates a chemist's tool from a generic ML tool.

Phase 4 — Deployment, Library & Sandbox (Weeks 10–12)
Goal: Turn the trained model into something the rest of Edeon and the user actually use.

Prediction sandbox. Implement the missing prediction UI: a drawer-style panel accessible from any saved model card, with three input modes — single SMILES (with RDKit-rendered preview as the user types), batch paste (one SMILES per line), CSV upload. Predictions render in a sortable table with: structure thumbnail, prediction value, prediction interval (from CV-based bootstrap or quantile RF), AD flag, top-3 SHAP contributors. Add an "Add to Project" button that pushes results into the existing screening dataset.

Model versioning & lineage. Extend the saved_models schema with version, parent_id, dataset_hash, git_like_changelog. When a user retrains with a tweaked hyperparameter, it becomes v2 of the same logical model rather than a new entry. Render the library as collapsible groups with version chips, last-trained date, and a deployment-status badge (Draft / Validated / Production).

Model cards. Auto-generate a one-page Markdown/PDF model card per saved model containing: dataset metadata, curation report, split strategy, hyperparameters, full metric table with CV ± std, Y-scramble baseline, AD definition, intended use, known limitations. This is increasingly an EU regulatory expectation under the AI Act and a EFSA/EPA hygiene factor for QSAR submissions.

Bridge to MPO scoring. Currently scoring.py ignores the saved-models table entirely. Add a custom_models weight stage to compute_mpo_score and a model-picker in the MPO weights UI. At scoring time, load the relevant model's metrics, features, and serialized estimator (joblib pickle stored on disk under ~/.edeon/models/{id}.joblib), run prediction with AD check, and feed the value into the composite score with confidence-weighting.

Export. Allow exporting saved models as joblib (sklearn-native), ONNX (cross-platform inference), and a self-contained Python package with predict.py script for IT-restricted environments. ONNX is non-trivial for tree models with skl2onnx but worth it for the deployment story.

4. Cross-Cutting Improvements
These touch every phase and should be developed in parallel.

Backend architecture. The current trainer is a single ~400-line monolith. Split models_training.py into modules: curation.py, featurizers.py, splitters.py, trainers.py, evaluators.py, interpreters.py, persistence.py. Each is independently testable, and the IPC surface from Rust simplifies to four calls (curate, featurize_preview, train, predict).

Streaming progress instead of fake logs. The current trainModel in modelStore.ts emits scripted progress lines on a timer while the real work happens opaquely. Replace with a Tauri event channel (tauri::EventHandler) that the Python side emits structured JSON events to: {stage: "curation"|"featurize"|"cv_fold"|"hpo_trial"|"final", progress: 0–1, message: "...", payload: {...}}. The frontend renders a real progress bar with stage chips. This is also necessary for HPO which can take minutes.

Cancellation. Long HPO runs need a cancel button wired through mpsc::channel to the Python process so users aren't held hostage by a runaway grid search.

UI design system consistency. The current styling (config-section-title, evaluation-kpi-card, etc.) is good but dense. For the diagnostic plots tab, adopt a consistent chart wrapper component (<DiagnosticChart title icon helpText>{children}</DiagnosticChart>) with a consistent help-tooltip pattern using lucide-react's HelpCircle so every chart gets a one-sentence layperson explanation. Industrial QSAR tools succeed or fail on whether non-statisticians trust the output, and inline help is the cheapest trust-builder.

Tests. Add a backend test fixture using the public Delaney solubility set (n=1128) and AMES mutagenicity (n=6512) — these are gold-standard QSAR benchmarks. CI should fail if model R² regresses below known thresholds (~0.85 for Delaney with Morgan+RF). Without this, refactors silently degrade scientific quality.

5. Prioritisation & Quick Wins
If only one week of work is available before a demo, the highest-value moves are: fix the broken split (random shuffle + k-fold), add the curation report, add scaffold split, and replace the synthetic learning curve in models_training.py (r2_tr_sim = metrics["r2_train"] + noise) with a real sklearn.model_selection.learning_curve call. Those four changes alone move the tool from "demo-grade" to "defensible".

If two weeks: add the Arena multi-model comparison and SHAP-based feature importance — both have outsized perceived value relative to implementation cost because tree-based SHAP is one library import and a few hundred lines of plotting.

If a quarter: execute the full Phase 1–3 plan, ship Phase 4 in increments. The deployment-to-MPO bridge is the single feature that converts the Models tab from an isolated playground into a competitive moat for Edeon, because it operationalises bespoke chemistry models inside the screening pipeline — something Schrödinger and StarDrop charge five-figure annual seats for.

6. Risks & Mitigations
The largest technical risk is dataset size. The current presets are n=20, which is below the 50–100 minimum for honest QSAR. Mitigate by (a) bundling a few public reference datasets (Delaney, Lipophilicity, Tox21 subsets) explicitly labelled as "Reference benchmarks", and (b) showing a hard-coded warning when n < 50 explaining that the model is illustrative.

The second risk is Python dependency weight: SHAP, Optuna, XGBoost, LightGBM, imbalanced-learn, ONNX add ~400 MB to the bundle. Mitigate by lazy-importing inside trainer functions and shipping them as optional plugins that download on first use — Tauri's sidecar mechanism handles this cleanly.

The third risk is overfitting the wizard with options. The wizard already has four steps; adding HPO modes, scaffold splits, fingerprint radius selectors, etc. risks paralysis. Mitigate with a strong "Quick" / "Advanced" toggle at the top of Step 2 that hides 80% of controls behind sensible defaults — defaults that are themselves a feature of an industrial tool.