# Edeon — 90-Day Implementation Plan for Coding Agent

**Audience:** coding agent.
**Goal:** execute the six highest-leverage engineering workstreams to convert Edeon from "technically defensible" to "commercially closeable" across the regulatory affairs, small CRO, and mid-tier agrochem segments.

This document is a portfolio of independent workstreams, not a single monolithic phase. Each workstream is feedable as one agent run. They have explicit dependencies; some can run in parallel.

**This plan excludes items not implementable by a coding agent**:
- Paper 3 manuscript writing (human researcher task)
- Pricing decisions (business decision)
- Design partner outreach (sales work)

Those happen in parallel with the engineering work but are outside this spec.

---

## 0. Context

Edeon is now a working agrochem platform with:
- Phase 0 architecture (tiered ModelBackend registry, deployment bridge, UQ/AD wrappers, model cards)
- Phase 1 curated datasets at `data/curated/<endpoint>/v1.0/`
- Phase 2 trained Tier-1 ensembles (RF + XGBoost + Chemprop) for ecotox endpoints with conformal CIs and Tanimoto k-NN AD
- Phase 3 heteroscedastic DT50 model + Monte Carlo GUS composite
- Phase 4 mammalian tox + skin sensitization + Ames + structural alerts for eye irritation
- QSAR Studio with SHAP, scaffold splits, Optuna HPO, model arena, deployment bridge
- Experimental value overlay (InChIKey → measured values from Phase 1 data)
- Knowledge Hub Layers 1+2 (federated registry searches across PPDB, ECOTOX, OpenFoodTox, ChEMBL)
- W1–W8 workflow gallery + interactive legacy workflows
- Three operational dossier report templates (MPO, Environmental, Selectivity)

What's missing for the next commercial tier:
- Empirical verification that the deployed T1 models are actually serving live predictions (not LogP fallbacks)
- Reference-compound demonstration artifacts for sales conversations
- Knowledge Hub Layer 3 (Claude-powered RAG Q&A over the federated content)
- Real OPERA T3 integration (currently mocked per audit)
- CReM ecosystem generative chemistry integration paired with deployed ecotox scoring
- Interactive calibration diagnostics in the GUI (currently HTML-only)

---

## 1. Workstream Map and Dependencies

```
Week 1     2     3     4     5     6     7     8     9    10    11    12
─────────────────────────────────────────────────────────────────────────
A: Verification Suite ◾◾                                            (3 days)
B: Reference Demos     ◾◾◾                                          (1 week)
                          │
                          ▼ (B blocks E because demos use E's screenshots)
C: KH Layer 3 RAG          ◾◾◾◾◾◾◾◾◾◾◾◾◾◾◾◾                       (4-5 wks)
D: OPERA T3                ◾◾◾◾◾◾◾◾◾◾◾◾                            (3-4 wks)
E: GUI Cal Diagnostics                ◾◾◾◾◾◾◾◾                      (2-3 wks)
F: CReM + EasyDock                       ◾◾◾◾◾◾◾◾◾◾◾◾◾◾◾◾◾◾◾◾◾◾   (6-8 wks)
   F-pre: License Audit               ◾                                (1 day)
─────────────────────────────────────────────────────────────────────────
```

**Hard execution rules:**
- **A runs first.** A protects every claim made by every subsequent workstream. If A finds problems, fix them before B–F.
- **B runs second** and produces artifacts used in B, E, and sales conversations.
- **C, D, E, F can run in parallel** after A and B complete, if multiple agents are available. Single-agent: run them sequentially in the order C → D → E → F.
- **F-pre (license audit) is non-negotiable** before any F implementation work begins.

---

## 2. Tech Stack Assumptions (carry-over)

- Python 3.11+, RDKit, pydantic v2, pytest, scikit-learn, xgboost, chemprop, conformal libraries
- Rust + Tauri + React + TypeScript + Zustand state stores
- SQLite for persistence, JSON-over-stdio IPC
- Anthropic SDK for Claude API integration in Workstream C
- Bundled binaries pattern from Phase 6 docking workbench (Vina, fpocket) — reuse for CReM/EasyDock binaries where applicable
- For RAG: `sentence-transformers` (local embeddings) or `nomic-embed-text-v1.5`; vector store via SQLite-VSS or LanceDB

No new heavy dependencies unless workstream specifies otherwise.

---

## 3. Workstream A — Verification Suite

**Goal:** empirically verify the three commercially load-bearing claims from the audit. These claims are stated as fact in sales conversations; they must be verified before any external use.

**Time estimate:** 2–3 days.

### A1: Live T1 backend serving verification

**Goal:** prove that when a user opens the Inspector and predicts on a compound, the value comes from the deployed Tier-1 ensemble, not a LogP fallback.

**File:** `tests/verification/test_t1_serving.py`

**Implementation:**

```python
"""
Verifies that production predictions come from Tier-1 ensembles, not fallbacks.

For each ecotox endpoint with a deployed T1 backend:
1. Load the registry as the live app would
2. Predict on a fixed reference panel of 10 marketed pesticides
3. Assert prediction.tier == 1
4. Assert prediction.model_id contains the ensemble identifier (not 'legacy')
5. Assert provenance.ensemble_components includes RF + XGBoost + Chemprop predictions
6. Compare against the legacy LogP backend's prediction — assert they differ by > 0.2 log
   for at least 5 of 10 compounds (proves the T1 isn't accidentally collapsing to LogP)
"""

import pytest
from edeon_models import build_default_registry, Endpoint

T1_ENDPOINTS = [
    Endpoint.BEE_ACUTE_ORAL_LD50,
    Endpoint.BEE_ACUTE_CONTACT_LD50,
    Endpoint.FISH_ACUTE_LC50,
    Endpoint.DAPHNIA_ACUTE_EC50,
    Endpoint.ALGAE_GROWTH_EC50,
    Endpoint.EARTHWORM_ACUTE_LC50,
    Endpoint.BIRD_ACUTE_ORAL_LD50,
    Endpoint.RAT_ACUTE_ORAL_LD50,
    Endpoint.SOIL_KOC,
    Endpoint.SOIL_DT50,
    Endpoint.SKIN_SENSITIZATION,
    Endpoint.MUTAGENICITY_AMES,
    Endpoint.BCF,
]

REFERENCE_PANEL = [
    ("CCN1C=NC(=N1)N(C)C(=O)C", "Imidacloprid"),  # Replace with correct canonical SMILES
    ("OC(=O)CN(CP(=O)(O)O)CCO", "Glyphosate"),
    # ... 8 more
]


@pytest.fixture(scope="module")
def registry():
    return build_default_registry()


@pytest.mark.parametrize("endpoint", T1_ENDPOINTS)
def test_t1_serves_predictions(endpoint, registry):
    backend = registry.get(endpoint)
    assert backend.tier() == 1, (
        f"Endpoint {endpoint.value} is being served by tier {backend.tier()} "
        f"backend, not Tier-1. Live predictions are LogP fallback or other tier."
    )
    # Predict on full panel
    smiles_list = [s for s, _ in REFERENCE_PANEL]
    predictions = backend.predict(smiles_list)
    # Every prediction must have provenance indicating ensemble components
    for pred, (_, name) in zip(predictions, REFERENCE_PANEL):
        assert pred.tier == 1
        provenance = pred.provenance
        if endpoint != Endpoint.BCF:  # BCF may be optional
            assert "ensemble_components" in provenance or "model_id" in provenance, (
                f"{name} prediction for {endpoint.value} lacks ensemble provenance"
            )


@pytest.mark.parametrize("endpoint", T1_ENDPOINTS[:6])  # Sample of endpoints
def test_t1_differs_from_legacy(endpoint, registry):
    """Confirm T1 isn't accidentally producing LogP-derived values."""
    t1 = registry.get(endpoint, preferred_tier=1)
    t2 = registry.get(endpoint, preferred_tier=2)
    smiles_list = [s for s, _ in REFERENCE_PANEL]
    t1_preds = t1.predict(smiles_list)
    t2_preds = t2.predict(smiles_list)
    differences = []
    for p1, p2 in zip(t1_preds, t2_preds):
        if p1.value.numeric is not None and p2.value.numeric is not None:
            differences.append(abs(p1.value.numeric - p2.value.numeric))
    differences = [d for d in differences if d > 0]
    n_significant = sum(1 for d in differences if d > 0.2)
    assert n_significant >= 5, (
        f"T1 and T2 predictions for {endpoint.value} differ significantly "
        f"on only {n_significant}/10 compounds. T1 may be collapsing to LogP."
    )
```

**Acceptance criteria:**
- Every T1 endpoint in `T1_ENDPOINTS` returns predictions with `tier=1` for the reference panel.
- Provenance includes ensemble components or non-legacy model_id.
- T1 vs T2 differ significantly on ≥ 5/10 compounds per endpoint, proving non-collapse.
- If any test fails, the agent stops and writes a clear failure report in `docs/VERIFICATION_NOTES.md` describing which endpoint failed and which test.

---

### A2: Empirical conformal coverage check

**Goal:** verify that the calibrated 95% CIs empirically contain truth in the [0.90, 0.97] range on held-out test sets.

**File:** `tests/verification/test_conformal_coverage.py`

**Implementation:**

```python
"""
For each Tier-1 backend with conformal calibration:
1. Load the held-out test set from Phase 1
2. Run predictions
3. Compute empirical coverage of 95% CIs
4. Assert coverage in [0.90, 0.97]
5. Generate calibration report at docs/verification/calibration_<endpoint>.md
"""

import json
from pathlib import Path
import pandas as pd
from edeon_models import build_default_registry, Endpoint

COVERAGE_TARGETS = {
    "default": (0.90, 0.97),
    Endpoint.BIRD_ACUTE_ORAL_LD50: (0.85, 1.00),  # Small dataset, looser
    Endpoint.SOIL_DT50: (0.88, 0.98),  # Heteroscedastic, slightly different
}


@pytest.mark.parametrize("endpoint", T1_ENDPOINTS_WITH_CONFORMAL)
def test_conformal_coverage(endpoint, registry):
    test_path = Path(f"data/curated/{endpoint.value}/v1.0/splits/scaffold/test.parquet")
    if not test_path.exists():
        pytest.skip(f"Test split not available for {endpoint.value}")
    
    test_df = pd.read_parquet(test_path)
    backend = registry.get(endpoint, preferred_tier=1)
    
    predictions = backend.predict(test_df["smiles_canonical"].tolist())
    
    in_interval = 0
    total = 0
    for pred, true_value in zip(predictions, test_df["value_log"]):
        if pred.ci_lower is None or pred.ci_upper is None:
            continue
        if pd.isna(true_value):
            continue
        if pred.ci_lower <= true_value <= pred.ci_upper:
            in_interval += 1
        total += 1
    
    coverage = in_interval / total
    lower_bound, upper_bound = COVERAGE_TARGETS.get(endpoint, COVERAGE_TARGETS["default"])
    
    assert lower_bound <= coverage <= upper_bound, (
        f"Endpoint {endpoint.value} 95% CI empirical coverage = {coverage:.3f}, "
        f"target [{lower_bound}, {upper_bound}]. Calibration is broken or "
        f"calibration set is unrepresentative of test set."
    )
    
    # Generate calibration report
    report_path = Path(f"docs/verification/calibration_{endpoint.value}.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(f"""# Calibration Report: {endpoint.value}

**Empirical 95% CI coverage on test set:** {coverage:.4f}
**Target range:** [{lower_bound}, {upper_bound}]
**Status:** {'✅ Passing' if lower_bound <= coverage <= upper_bound else '❌ Failing'}

**Test set size:** {total}
**Predictions in interval:** {in_interval}
**Predictions out of interval:** {total - in_interval}
""")
```

**Acceptance criteria:**
- Each T1 endpoint with conformal calibration achieves empirical 95% coverage within target range.
- Per-endpoint calibration reports generated.
- If failures, agent documents in `VERIFICATION_NOTES.md` with proposed remediation.

---

### A3: DT50 heteroscedastic-model integrity check

**Goal:** verify the publishable claims about the heteroscedastic DT50 model — NLL in target range and predicted-vs-observed σ correlation is meaningfully positive.

**File:** `tests/verification/test_dt50_heteroscedastic.py`

**Implementation:**

```python
"""
For the soil_dt50 endpoint:
1. Load test set predictions
2. Compute NLL on test set
3. Assert NLL ≤ 1.5 (log10 days target from Phase 3 spec)
4. For compounds with multiple test records, compute observed within-compound σ
5. Correlate observed σ with predicted σ (mean over the compound's predictions)
6. Assert Spearman ρ ≥ 0.3
7. Generate diagnostic plot: predicted σ vs observed σ
"""

import numpy as np
from scipy.stats import spearmanr
import matplotlib.pyplot as plt


def test_dt50_nll_in_range(registry):
    backend = registry.get(Endpoint.SOIL_DT50, preferred_tier=1)
    test_df = pd.read_parquet("data/curated/soil_dt50/v1.0/splits/scaffold/test.parquet")
    predictions = backend.predict(test_df["smiles_canonical"].tolist())
    
    nll_values = []
    for pred, true_y in zip(predictions, test_df["value_log"]):
        mu = pred.value.numeric
        # Extract sigma from CI: assumed symmetric in log space, 95% CI = ±1.96σ
        sigma = (pred.ci_upper - pred.ci_lower) / (2 * 1.96)
        sigma2 = sigma ** 2
        nll = 0.5 * (np.log(sigma2) + (true_y - mu) ** 2 / sigma2)
        nll_values.append(nll)
    
    mean_nll = np.mean(nll_values)
    assert mean_nll <= 1.5, (
        f"DT50 mean NLL = {mean_nll:.3f}, target ≤ 1.5. "
        f"Heteroscedastic model isn't calibrated properly."
    )


def test_dt50_sigma_prediction_quality(registry):
    """Compounds with multiple test records: do we predict their σ well?"""
    backend = registry.get(Endpoint.SOIL_DT50, preferred_tier=1)
    test_df = pd.read_parquet("data/curated/soil_dt50/v1.0/splits/scaffold/test.parquet")
    
    # Group by InChIKey, find compounds with ≥ 3 measurements
    grouped = test_df.groupby("inchikey").filter(lambda g: len(g) >= 3)
    if len(grouped) == 0:
        pytest.skip("No multi-record compounds in test set")
    
    observed_sigma = []
    predicted_sigma = []
    for inchikey, group in grouped.groupby("inchikey"):
        observed_sigma.append(group["value_log"].std())
        smiles = group["smiles_canonical"].iloc[0]
        pred = backend.predict([smiles])[0]
        pred_sigma = (pred.ci_upper - pred.ci_lower) / (2 * 1.96)
        predicted_sigma.append(pred_sigma)
    
    rho, p_value = spearmanr(observed_sigma, predicted_sigma)
    assert rho >= 0.3, (
        f"σ-prediction quality: Spearman ρ = {rho:.3f}, target ≥ 0.3. "
        f"Variance head isn't learning meaningful structure."
    )
    
    # Save diagnostic plot
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(observed_sigma, predicted_sigma, alpha=0.6)
    ax.set_xlabel("Observed within-compound σ (log10 days)")
    ax.set_ylabel("Predicted σ (log10 days)")
    ax.set_title(f"DT50 σ-prediction quality (Spearman ρ = {rho:.3f})")
    fig.savefig("docs/verification/dt50_sigma_correlation.png", dpi=150)
```

**Acceptance criteria:**
- DT50 NLL ≤ 1.5 on test set
- σ-prediction Spearman ρ ≥ 0.3 on multi-record compounds
- Diagnostic plot generated

---

### A4: Verification summary report

**File:** `docs/verification/SUMMARY.md`

**Action:** Auto-generated summary after all A1–A3 tests run. Includes:
- Pass/fail status per check
- Empirical coverage values per endpoint
- DT50 metrics
- Overall verification status: PASS / PARTIAL / FAIL

**Acceptance:** Summary committed. If status is not PASS, agent writes specific failure modes and stops Workstream A. Other workstreams should not proceed until A is PASS or known limitations are accepted.

---

### A — Workstream Acceptance

Workstream A is complete when:
1. All A1–A3 tests run as part of the CI pipeline
2. Summary report at `docs/verification/SUMMARY.md` shows PASS or documented known limitations
3. If FAIL: report identifies the specific endpoint and failure mode; halt other workstreams until resolved

---

## 4. Workstream B — Reference Compound Demonstrations

**Goal:** produce reproducible, screenshot-ready demonstration artifacts using 5 marketed pesticides. Output is a self-contained demo bundle for sales conversations.

**Time estimate:** 1 week.

### B1: Reference compound selection and metadata

**File:** `data/demos/reference_compounds.yaml`

**Action:** Author a YAML manifest of 5 reference compounds with rich public data:

```yaml
reference_compounds:
  - id: imidacloprid
    name: Imidacloprid
    chembl_id: CHEMBL96
    cas: 138261-41-3
    smiles_canonical: "CN1CCN(C1=NC2=NC=CC(=N2)Cl)C[N+](=O)[O-]"
    class: insecticide
    class_subtype: neonicotinoid
    irac_group: "4A"
    hrac_group: null
    measured_values:
      bee_acute_oral_ld50:
        value: 0.018
        units: ug/bee
        source: ApisTox
        reference: Adamczyk 2025
      bee_acute_contact_ld50:
        value: 0.024
        units: ug/bee
        source: ApisTox
      rat_acute_oral_ld50:
        value: 450
        units: mg/kg
        source: PPDB
      soil_dt50_median:
        value: 174
        units: days
        source: EFSA DAR
    regulatory_status:
      eu_1107_2009: restricted_2018
      us_epa: restricted_outdoor
      brazil: registered
  - id: glyphosate
    # ... full entry
  - id: azoxystrobin
    # ...
  - id: mesotrione
    # ...
  - id: chlorantraniliprole
    # ...
```

Each compound must have:
- Canonical SMILES (verified via RDKit)
- ≥ 4 measured endpoint values from authoritative sources
- IRAC/HRAC/FRAC classification
- Regulatory status across ≥ 2 jurisdictions

**Acceptance:** YAML validates against a pydantic schema; all SMILES parse; all measured value references are citable.

---

### B2: Demo pipeline orchestrator

**File:** `scripts/generate_reference_demos.py`

**Action:** For each reference compound, run the complete Edeon pipeline and capture:

1. **Inspector predictions table** — every T1 endpoint, predicted value with CI, AD status, tier, measured value (when in overlay index), delta
2. **Honeycomb screenshot** — call the backend, render the honeycomb cells programmatically, save as PNG
3. **Fate gauge screenshot** — same for Koc/DT50/GUS
4. **Toxicity panel screenshot** — rat LD50, skin sens, Ames, eye alerts
5. **Workflow run** — execute W1 (Registration Readiness) and W3 (TP Liability Sweep), save dossier PDFs
6. **QSAR Studio screenshot** — load a pre-trained model card, capture full diagnostic view

```python
"""
For each reference compound:
1. Load the compound into a temporary project
2. Run all T1 backends → assemble prediction table
3. Render honeycomb, fate gauge, toxicity panel via headless rendering
4. Run W1 + W3 workflows → export PDF dossiers
5. Bundle outputs at data/demos/<compound_id>/
"""

from pathlib import Path
import yaml
from edeon_models import build_default_registry, Endpoint

OUTPUT_DIR = Path("data/demos")


def generate_demo(compound: dict, registry):
    output_dir = OUTPUT_DIR / compound["id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Predictions table
    predictions = run_all_predictions(compound["smiles_canonical"], registry)
    prediction_table = build_comparison_table(predictions, compound["measured_values"])
    save_html_table(prediction_table, output_dir / "predictions.html")
    save_pdf_table(prediction_table, output_dir / "predictions.pdf")
    
    # 2-4. Visualizations via headless rendering
    render_honeycomb(predictions, output_dir / "honeycomb.png")
    render_fate_gauge(predictions, output_dir / "fate_gauge.png")
    render_toxicity_panel(predictions, output_dir / "toxicity_panel.png")
    
    # 5. Workflow execution
    run_workflow_w1(compound, output_dir / "W1_registration.pdf")
    run_workflow_w3(compound, output_dir / "W3_tp_sweep.pdf")
    
    # 6. Summary card
    generate_summary_card(compound, predictions, output_dir / "summary.md")


def main():
    with open("data/demos/reference_compounds.yaml") as f:
        compounds = yaml.safe_load(f)["reference_compounds"]
    registry = build_default_registry()
    for compound in compounds:
        print(f"Generating demo for {compound['name']}...")
        generate_demo(compound, registry)
    
    # Master index
    generate_master_demo_index(compounds, OUTPUT_DIR / "INDEX.md")


if __name__ == "__main__":
    main()
```

The "headless rendering" step needs a small headless rendering harness — likely using Playwright or similar to drive the Tauri app in a headless mode, or alternatively a pure-Python rendering of the same visualisations using matplotlib/Plotly for the honeycomb and gauges. Either approach is acceptable; document the choice.

**Acceptance:**
- All 5 compounds generate complete demo bundles
- Each bundle has: predictions.pdf, honeycomb.png, fate_gauge.png, toxicity_panel.png, W1_registration.pdf, W3_tp_sweep.pdf, summary.md
- Predictions table shows predicted vs. measured side by side
- Total bundle generation takes < 10 minutes

---

### B3: Demo selection rationale document

**File:** `data/demos/DEMO_RATIONALE.md`

**Action:** Auto-generate a markdown document explaining why each reference compound was chosen and what it demonstrates:

- Imidacloprid: bee toxicity baseline (well-characterised in ApisTox); illustrates honeycomb experimental overlay
- Glyphosate: low mammalian tox, environmental persistence concern (shows fate gauge + GUS)
- Azoxystrobin: fungicide standard (shows multi-target coverage)
- Mesotrione: HPPD inhibitor with mammalian target ortholog (foreshadows selectivity story)
- Chlorantraniliprole: modern, highly selective insecticide (shows the positive case)

**Acceptance:** Document committed.

---

### B4: Demo CI integration

**File:** `.github/workflows/regenerate_demos.yml`

**Action:** Add a GitHub Action that regenerates all demo bundles on every release tag. Ensures demos always reflect current model behavior.

**Acceptance:** Workflow triggers on tag; produces fresh demo bundles.

---

### B — Workstream Acceptance

Workstream B is complete when:
1. 5 reference compound demo bundles exist at `data/demos/<id>/`
2. Each bundle includes predictions, 3 visualisations, 2 dossier PDFs, summary card
3. `DEMO_RATIONALE.md` documents the curation choices
4. CI workflow regenerates bundles on releases
5. The agent has verified by inspection that the honeycomb screenshots show real T1 predictions with CIs and experimental overlays (not LogP fallbacks)

---

## 5. Workstream C — Knowledge Hub Layer 3 (RAG)

**Goal:** add Claude-powered Q&A grounded in the federated Knowledge Hub content. Citation-traced answers, strict context-only system prompts, local embedding store.

**Time estimate:** 4–5 weeks.

**Depends on:** Workstream A complete (verification of underlying predictions).

### C1: Embedding infrastructure

**File:** `python/edeon_knowledge/embedding/`

**Action:** Build the embedding pipeline:

```python
class KnowledgeEmbeddingStore:
    """Embeds Knowledge Hub entries and stores vectors for retrieval."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2",
                 store_path: Path = Path("data/knowledge/embeddings.db")):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)
        self._store_path = store_path
        self._init_store()
    
    def _init_store(self):
        # SQLite with VSS extension for vector search
        import sqlite3
        # Schema: id TEXT PK, entity_type TEXT, entity_id TEXT, 
        #         text TEXT, embedding BLOB, updated_at TEXT
        ...
    
    def index_knowledge_hub(self, knowledge_root: Path) -> int:
        """Walk the Knowledge Hub content and index every searchable entry.
        Returns number of vectors indexed."""
        ...
    
    def search(self, query: str, top_k: int = 10, 
               entity_types: Optional[list[str]] = None) -> list[KnowledgeMatch]:
        """Embedding-based retrieval."""
        ...


@dataclass
class KnowledgeMatch:
    entity_id: str
    entity_type: str
    text: str
    similarity: float
    source_url: Optional[str] = None
    citation: Optional[str] = None
```

Use `all-MiniLM-L6-v2` (384-dim, fast) for default. Allow upgrading to `nomic-embed-text-v1.5` (768-dim, higher quality) via config.

Index all Knowledge Hub content:
- Pesticide reference entries (PPDB, ECOTOX, OpenFoodTox, ChEMBL fetched data)
- HRAC/IRAC/FRAC classifications
- Target mechanism descriptions
- Regulatory framework summaries
- Workflow descriptions (W1–W8)
- Internal Edeon model cards

**Acceptance:**
- Index builds without error
- Search query "neonicotinoid bee toxicity" returns relevant entries about imidacloprid, clothianidin, sulfoxaflor in top 10
- Indexing takes < 5 minutes for current Knowledge Hub content
- Re-indexing is incremental (only changed entries)

---

### C2: Claude API integration with strict prompting

**File:** `python/edeon_knowledge/qa/claude_service.py`

```python
class ClaudeQAService:
    """Provides RAG-based Q&A using the Anthropic API.
    
    Hard rules:
    - System prompt strictly limits Claude to answer only from provided context
    - Every fact must be citation-anchored
    - "I don't know" is the correct answer when context is insufficient
    """
    
    SYSTEM_PROMPT = """You are Edeon's research assistant. You answer questions about
agrochemicals, pesticides, and related regulatory science. You answer ONLY from the
context provided in each user message. If the context does not contain the answer,
say "I don't have information about that in the Knowledge Hub" — do NOT use general
knowledge.

For every factual claim in your answer, cite the supporting source using inline
citations in the format [SourceID]. Do NOT make up citations.

Be concise. Be technically accurate. Do not speculate. Do not extrapolate beyond
the provided context."""
    
    def __init__(self, anthropic_api_key: str, 
                 embedding_store: KnowledgeEmbeddingStore,
                 model: str = "claude-haiku-4-5",
                 max_context_tokens: int = 30000):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=anthropic_api_key)
        self._embedding_store = embedding_store
        self._model = model
        self._max_context_tokens = max_context_tokens
    
    async def answer(self, query: str, conversation_history: list[dict] = None
                     ) -> ClaudeQAResponse:
        # 1. Embed query
        # 2. Retrieve top-k matches from embedding store
        # 3. Build context from matches with source IDs
        # 4. Call Claude with strict system prompt + context + query
        # 5. Extract citations from response
        # 6. Validate citations against retrieved sources
        # 7. Return structured response
        ...


@dataclass
class ClaudeQAResponse:
    query: str
    answer: str
    citations: list[Citation]  # Validated against retrieved sources
    retrieved_sources: list[KnowledgeMatch]
    model: str
    tokens_used: dict[str, int]
    timestamp: datetime
```

**Acceptance:**
- Answers contain citations in `[SourceID]` format
- Each citation resolves to a retrieved source
- When asked outside-context questions, model responds "I don't have information..."
- API calls log token usage for cost tracking

---

### C3: Conversation persistence

**File:** `python/edeon_knowledge/qa/conversation_store.py`

```python
# SQLite schema
"""
CREATE TABLE knowledge_conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id TEXT,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    starred INTEGER DEFAULT 0
);

CREATE TABLE knowledge_messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES knowledge_conversations(conversation_id),
    role TEXT NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    citations_json TEXT,
    retrieved_sources_json TEXT,
    tokens_used_json TEXT,
    timestamp TEXT NOT NULL
);
"""
```

Provide CRUD operations for conversations and messages.

**Acceptance:** Conversations persist; can be reloaded; searchable by title or content.

---

### C4: IPC commands and Tauri integration

**File:** Extend Python IPC server + add Tauri commands:

- `knowledge_qa_ask(query: str, conversation_id: str | None) -> ClaudeQAResponse`
- `knowledge_qa_list_conversations() -> list[ConversationSummary]`
- `knowledge_qa_load_conversation(conversation_id: str) -> Conversation`
- `knowledge_qa_star_conversation(conversation_id: str, starred: bool) -> bool`
- `knowledge_qa_delete_conversation(conversation_id: str) -> bool`
- `knowledge_qa_reindex(force: bool = False) -> dict`

**Acceptance:** All callable from frontend.

---

### C5: Frontend chat UI

**File:** `src/components/knowledge/KnowledgeChatPanel.tsx` (added as a new tab in `KnowledgeView`)

Layout:
- Conversation list (left, collapsible)
- Chat thread (center): user messages + Claude responses
- Citation panel (right, expandable): for the currently-selected assistant message, shows the cited sources with full text
- Input box (bottom) with send button, model selector dropdown, "Clear conversation" button

Each assistant message renders inline citations as clickable badges. Clicking a citation scrolls to/opens the source in the right panel.

"Cost indicator" at bottom: small text showing tokens used in the current conversation and approximate USD cost.

**Acceptance:**
- Chat panel renders cleanly
- Conversations persist across app restarts
- Citations are clickable and resolve correctly
- Token/cost indicator updates as conversation progresses

---

### C6: Settings integration

**File:** Extend Settings view.

- Anthropic API key entry (encrypted at rest in SQLite)
- Default model selector: Claude Haiku 4.5 (default, fastest) | Claude Sonnet 4.6 | Claude Opus
- Embedding model selector
- "Reindex Knowledge Hub" button
- Monthly token usage display

**Acceptance:** Settings work; API key persists encrypted.

---

### C7: Local-LLM fallback (Optional, deferred to C-v2)

**Action:** Document the architectural hooks for future Ollama or llama.cpp integration. Don't implement; just ensure the QA service interface doesn't lock the system into Claude.

**Acceptance:** Architecture document mentions fallback path.

---

### C — Workstream Acceptance

Workstream C is complete when:
1. Knowledge Hub content embedded and indexed in local vector store
2. Claude API integration works with strict context-only prompting
3. Citations are correctly extracted and validated
4. Chat UI renders, persists conversations, displays citations
5. Settings allow API key configuration and model selection
6. Cost indicator shows token usage
7. Documentation at `docs/KNOWLEDGE_HUB_RAG.md` describes architecture and usage

---

## 6. Workstream D — OPERA Tier-3 Integration

**Goal:** replace mocked Tier-3 backends with real OPERA integration. OPERA is EPA-published, public domain, regulator-recognised, locally executable as a Python package.

**Time estimate:** 3–4 weeks.

### D1: OPERA installation and verification

**Files:** Add dependency; verify per-endpoint outputs.

**Action:** Install OPERA via:
- pip install if a maintained Python wrapper exists
- Otherwise clone the NIEHS OPERA repo and integrate the CLI tool

Verify which OPERA endpoints are usable for Edeon's endpoint set:

| Edeon Endpoint | OPERA endpoint | Notes |
|---|---|---|
| bcf | BCF | Direct match |
| soil_koc | KOC | Direct match |
| logp | LogP | Direct match |
| logd | LogD | Direct match |
| pka | pKa | Direct match (acid/base) |
| solubility | WS | Water solubility |
| boiling_point | BP | Direct match |
| melting_point | MP | Direct match |
| vapor_pressure | VP | Direct match |
| henrys_law | HL | Direct match |
| biodegradation | BIODEG | Useful as DT50 reference |

Document available endpoints in `docs/OPERA_ENDPOINT_MAPPING.md`.

**Acceptance:** OPERA runs locally on a test compound; verified mapping document committed.

---

### D2: OperaBackend implementation

**File:** `python/edeon_models/backends/external/opera_backend.py`

```python
class OperaTier3Backend(ModelBackend):
    """Tier-3 backend wrapping EPA OPERA predictions."""
    
    def __init__(self, endpoint: Endpoint, opera_endpoint: str):
        self._endpoint = endpoint
        self._opera_endpoint = opera_endpoint
        # Cache for OPERA results (subprocess overhead is significant)
        self._cache_db = Path("data/cache/opera_cache.db")
    
    def endpoint(self) -> Endpoint:
        return self._endpoint
    
    def tier(self) -> int:
        return 3
    
    def predict(self, smiles, conditions=None) -> list[Prediction]:
        results = []
        for s in smiles:
            cached = self._lookup_cache(s)
            if cached:
                results.append(cached)
                continue
            # Run OPERA via subprocess
            opera_result = self._run_opera(s, self._opera_endpoint)
            prediction = self._build_prediction(s, opera_result)
            self._store_cache(s, prediction)
            results.append(prediction)
        return results
    
    def _run_opera(self, smiles: str, endpoint: str) -> dict:
        # Subprocess invocation of OPERA's CLI
        # Parse output
        # Return value, AD status, prediction class
        ...
    
    def applicability_domain(self, smiles):
        # OPERA reports its own AD; pass through
        ...
    
    def metadata(self) -> ModelCard:
        return ModelCard(
            model_id=f"opera_{self._opera_endpoint}",
            name=f"EPA OPERA {self._opera_endpoint}",
            tier=3,
            description="EPA OPERA QSAR model — regulator-recognised reference.",
            intended_use="External regulatory-aligned reference comparison.",
            references=[
                "Mansouri K et al. 2018 J Cheminform 10:10 (OPERA)",
                "https://github.com/NIEHS/OPERA"
            ],
            license="Public domain (US Gov)",
            ...
        )
```

**Acceptance:** Backend predicts on 10 reference compounds; matches OPERA CLI output exactly; caching reduces second-call latency to < 100ms.

---

### D3: Registry integration

**File:** Extend `build_default_registry()`.

**Action:** For each endpoint where OPERA provides a corresponding prediction, register an OperaTier3Backend instance. T3 doesn't replace T1; it sits alongside, available for explicit comparison.

```python
def _register_opera_backends(registry: BackendRegistry):
    OPERA_MAPPINGS = [
        (Endpoint.BCF, "BCF"),
        (Endpoint.SOIL_KOC, "KOC"),
        # ... etc
    ]
    for endpoint, opera_endpoint in OPERA_MAPPINGS:
        try:
            backend = OperaTier3Backend(endpoint, opera_endpoint)
            registry.register(backend)
        except Exception as e:
            logger.warning(f"Failed to register OPERA backend for {endpoint}: {e}")
```

**Acceptance:** `reg.list_for_endpoint(Endpoint.SOIL_KOC)` includes both T1 and T3 backends.

---

### D4: "Compare with OPERA" UI affordance

**File:** Extend `PredictionDisplay.tsx`.

**Action:** Add a small "compare" button next to T1 predictions for endpoints with OPERA coverage. Clicking shows the OPERA prediction alongside the T1 prediction in a comparison popup:

```
Edeon Tier-1:     log Koc = 2.45 ± 0.31    AD: In domain
EPA OPERA Tier-3: log Koc = 2.38           AD: In domain
Δ:                0.07 log units
```

When OPERA AD is OUT but T1 AD is IN, prominently display the disagreement.

**Acceptance:** Compare button renders for OPERA-covered endpoints; comparison popup shows both predictions.

---

### D5: Documentation

**File:** `docs/OPERA_INTEGRATION.md`

Document the integration:
- OPERA version used
- Endpoint mapping
- Caching strategy
- When OPERA and T1 disagree, what it means
- License and citation requirements

**Acceptance:** Document committed.

---

### D — Workstream Acceptance

Workstream D is complete when:
1. OPERA installs and runs locally on all target platforms
2. OperaTier3Backend implementations exist for ≥ 6 endpoints
3. T3 backends registered alongside T1 (not replacing)
4. "Compare with OPERA" UI affordance functional
5. Caching reduces subsequent calls to < 100ms
6. `OPERA_INTEGRATION.md` documents the integration

---

## 7. Workstream E — GUI Calibration Diagnostics

**Goal:** expose interactive calibration curves, AD distance histograms, and per-class performance breakdowns directly in the Edeon GUI. Currently in HTML exports only per the audit.

**Time estimate:** 2–3 weeks.

**Depends on:** Workstream A.

### E1: Calibration data endpoint

**File:** Extend backend with `get_calibration_diagnostics(endpoint: Endpoint) -> CalibrationDiagnostics`.

```python
class CalibrationDiagnostics(BaseModel):
    endpoint: str
    model_id: str
    test_set_size: int
    
    # For regression
    parity_data: Optional[ParityPlotData] = None
    calibration_curve: Optional[CalibrationCurveData] = None
    coverage_per_quantile: Optional[CoveragePerQuantileData] = None
    residual_distribution: Optional[ResidualDistData] = None
    
    # For classification
    roc_curve: Optional[ROCData] = None
    pr_curve: Optional[PRData] = None
    reliability_diagram: Optional[ReliabilityData] = None
    confusion_matrix: Optional[ConfusionMatrixData] = None
    
    # For all
    ad_distance_histogram: ADHistogramData
    per_chemical_class_metrics: dict[str, dict[str, float]]
```

The diagnostics are computed once during Phase 2/3/4 training and saved alongside the model card. The IPC handler reads from these saved artifacts.

**Acceptance:** IPC command returns valid CalibrationDiagnostics for any deployed T1 endpoint.

---

### E2: ModelCardViewer extension

**File:** Extend `ModelCardViewer.tsx` from Phase 0.

**Action:** Add a "Diagnostics" tab to the model card viewer. Renders:

- **Parity plot** (regression): observed vs predicted with diagonal line, color-coded by AD status
- **Calibration curve** (regression): predicted CI vs empirical coverage at multiple confidence levels
- **Reliability diagram** (classification): predicted probability vs observed frequency in bins
- **Per-class breakdown**: heatmap of RMSE/F1 per chemical class
- **AD distance histogram**: training set + test set + query compounds overlaid

Use Recharts or similar for chart rendering.

**Acceptance:**
- Tab renders for every endpoint with diagnostics data
- Charts are interactive (hover tooltips, zoom)
- Per-class heatmap is sortable

---

### E3: Live AD distance for query compounds

**File:** When a user opens the Inspector with a compound, the ModelCardViewer's AD distance histogram shows the current compound's distance to training set, highlighted distinctly. Visual feedback: green if in-domain, yellow borderline, red out-of-domain.

**Acceptance:** Inspector compound's AD distance is visually highlighted on the histogram.

---

### E4: Documentation

**File:** `docs/CALIBRATION_DIAGNOSTICS.md`

Document how to read each diagnostic chart and what acceptable values look like.

**Acceptance:** Document committed.

---

### E — Workstream Acceptance

Workstream E is complete when:
1. CalibrationDiagnostics data available via IPC for every T1 endpoint
2. ModelCardViewer has Diagnostics tab with parity, calibration, reliability, per-class, AD histogram charts
3. Inspector compound's AD distance visually highlighted
4. `docs/CALIBRATION_DIAGNOSTICS.md` explains reading the diagnostics

---

## 8. Workstream F — CReM + EasyDock Integration

**Goal:** integrate the CReM ecosystem and EasyDock for chemically-reasonable molecular generation paired with Edeon's deployed Tier-1 scoring. This is the biggest commercial differentiator in the plan.

**Time estimate:** 6–8 weeks.

**Depends on:** Workstream A complete (T1 backends verified), F-pre license audit complete.

### F-pre: License audit (BLOCKING)

**Duration:** 1 day.
**File:** `docs/CREM_LICENSE_AUDIT.md`

**Action:** For each of the following components, verify license and compatibility with bundling in a commercial closed-source desktop product:

- CReM (core): https://github.com/DrrDom/crem
- CReM-pharm: https://github.com/imolecule/crem-pharm
- CReM-dock: https://github.com/imolecule/crem-dock
- CReM-opt: TBD release
- EasyDock: https://github.com/ci-lab-cz/easydock

For each:
- License (look for LICENSE file)
- Dependencies and their licenses (check pyproject.toml / setup.py / requirements.txt)
- Whether bundling is permitted under the license
- Whether dependencies introduce GPL contamination

Produce a recommendation table:

| Component | License | Dependencies | Bundling OK? | Action |
|---|---|---|---|---|
| CReM | BSD-3 | RDKit | Yes | Bundle |
| CReM-dock | ? | ? + Vina | ? | Decide |
| ... | | | | |

**HALT condition:** if any component's license forbids bundling or introduces GPL contamination through dependencies, document the issue and propose alternatives (manual SMARTS-based generation, or user-provided installation). DO NOT proceed with bundling without resolution.

**Acceptance:** Audit document committed; clear go/no-go decision per component.

---

### F1: CReM core integration

**File:** `python/edeon_generation/crem_engine.py`

**Action:** Wrap CReM's mutation engine as an Edeon-callable service:

```python
class CReMGenerationEngine:
    """Edeon wrapper around the CReM mutation engine."""
    
    def __init__(self, fragments_db_path: Path, max_mutations: int = 50):
        from crem.crem import mutate_mol
        self._mutate_mol = mutate_mol
        self._fragments_db = fragments_db_path
        self._max_mutations = max_mutations
    
    def generate_mutants(
        self,
        parent_smiles: str,
        radius: int = 2,
        min_size: int = 1,
        max_size: int = 5,
        max_mutants: int = 50,
        return_smiles_only: bool = False,
    ) -> list[GenerationResult]:
        """Apply CReM mutations to parent. Returns list of mutant compounds."""
        ...


@dataclass
class GenerationResult:
    parent_smiles: str
    mutant_smiles: str
    transformation: str           # SMARTS describing the change
    fragment_id: str              # Reference into CReM fragments DB
    similarity_to_parent: float   # Tanimoto
```

Bundle the CReM fragments database (pre-computed, public) at `data/generation/crem_fragments_v0.3.db`.

**Acceptance:** Generates 50 mutants for imidacloprid in < 10 seconds. All mutants are valid SMILES.

---

### F2: EasyDock integration

**File:** `python/edeon_generation/easydock_wrapper.py`

**Action:** EasyDock provides a higher-level docking pipeline with multi-engine support. Wrap as a service:

```python
class EasyDockService:
    """Edeon wrapper around EasyDock for high-throughput docking."""
    
    async def dock_batch(
        self,
        receptor: PreparedReceptor,
        ligand_smiles: list[str],
        box_center: tuple[float, float, float],
        box_size: tuple[float, float, float],
        engine: Literal["vina", "smina", "gnina"] = "vina",
        n_workers: int = None,
    ) -> list[EasyDockResult]:
        """Batch docking. Parallelizes across CPU cores."""
        ...
```

EasyDock primarily orchestrates Vina (and optionally other engines) with better error handling and parallelization than naked Vina. The wrapper preserves Edeon's IPC pattern (progress events, cancellation).

**Acceptance:** Batch-docking 20 compounds against an ALS receptor completes in < 5 minutes on 8 cores.

---

### F3: CReM-dock integration

**File:** `python/edeon_generation/crem_dock.py`

**Action:** CReM-dock is the closed-loop pipeline: generate → dock → re-generate from top scoring. Wrap:

```python
class CReMDockPipeline:
    """Docking-guided generation. Iteratively mutates parent, docks each mutant,
    keeps top scoring, re-mutates from those."""
    
    async def run(
        self,
        parent_smiles: str,
        receptor: PreparedReceptor,
        box_config: BoxConfig,
        n_iterations: int = 3,
        population_size: int = 20,
        keep_top_n: int = 5,
    ) -> CReMDockResult:
        ...


@dataclass
class CReMDockResult:
    parent_smiles: str
    receptor_id: str
    best_compounds: list[GenerationCompound]  # Top scoring by docking
    iterations: list[IterationResult]         # Generation per iteration
    total_compounds_generated: int
    total_compounds_docked: int
    elapsed_seconds: float


@dataclass
class GenerationCompound:
    smiles: str
    docking_score: float
    generation: int                # Which iteration produced this
    parent_in_generation: str
    
    # Edeon-specific: predicted ecotox/fate properties
    predicted_properties: dict[str, Prediction]   # All T1 endpoints
    selectivity_score: Optional[float] = None     # If Paper 2 backend present
    
    # Composite ranking
    composite_score: float
```

**The closed-loop scoring** is the unique Edeon value: every generated mutant gets scored against the full Tier-1 stack (bee, fish, rat LD50, BCF, DT50, Ames, etc.) and ranked by a composite that balances docking score with safety profile.

**Acceptance:** CReM-dock pipeline runs on imidacloprid + ALS receptor; produces ≥ 50 mutants across 3 iterations; each with full T1 property predictions.

---

### F4: CReM-pharm integration (optional secondary)

**Action:** CReM-pharm uses pharmacophore queries to guide generation. Implement only if F1-F3 complete and time permits.

```python
class CReMPharmService:
    async def generate_for_pharmacophore(
        self,
        parent_smiles: str,
        pharmacophore_features: list[PharmFeature],
        n_mutants: int = 50,
    ) -> list[GenerationResult]:
        ...
```

**Acceptance:** Generates compounds matching a 3-point pharmacophore from a known active.

---

### F5: Generation Workbench UI

**File:** `src/views/GenerationWorkbenchView.tsx` (new top-level view)

Layout:
- **Mode selector** (top): CReM Mutation | CReM-dock | CReM-pharm | EasyDock Batch
- **Parent compound panel**: SMILES input, 2D preview, "Load from Inspector" button
- **Receptor selection** (for CReM-dock/EasyDock modes): integrate the docking workbench's receptor selector
- **Generation parameters**: mode-specific controls
- **Run** button with progress streaming
- **Results table**: each generated compound with composite score, docking score, predicted ecotox profile (compact)
- **Compound detail** (right panel): selected compound's full property profile with comparison to parent

The results table supports sorting/filtering by any property column. Click a result to load it into the Inspector for full evaluation.

**Acceptance:**
- Workbench accessible from main navigation
- All 4 modes selectable
- Results table renders with sortable columns
- Click → Inspector navigation works

---

### F6: Generation history

**File:** Extend SQLite schema with `generation_jobs` table.

**Action:** Persist every generation job with parameters + top results. Allow reloading.

**Acceptance:** Jobs persist across app restarts.

---

### F7: Documentation

**Files:**
- `docs/GENERATION_WORKBENCH_GUIDE.md` — user-facing
- `docs/CREM_INTEGRATION_NOTES.md` — developer/maintainer
- `docs/CREM_LICENSE_AUDIT.md` — already from F-pre

**Acceptance:** Documents committed.

---

### F — Workstream Acceptance

Workstream F is complete when:
1. F-pre license audit complete with go/no-go decisions
2. CReM core integration generates valid mutants
3. EasyDock service performs batch docking
4. CReM-dock pipeline runs closed-loop generation + docking + Tier-1 property scoring
5. (Optional) CReM-pharm integration
6. Generation Workbench UI renders with all 4 modes
7. Generated compound results show composite scoring across docking + ecotox/fate properties
8. Generation history persists
9. Documentation complete

---

## 9. Cross-Cutting Tasks

### X1: Integration tests for new workstreams

**File:** `tests/integration/`

For each workstream completed, add an end-to-end integration test:

- `test_verification_e2e.py` — runs A1, A2, A3 against current models
- `test_demos_e2e.py` — regenerates one reference compound demo and validates output structure
- `test_rag_e2e.py` — embeds, retrieves, calls Claude (with mock or real key), validates citations
- `test_opera_e2e.py` — runs OPERA on test compound; compares against T1
- `test_calibration_diagnostics_e2e.py` — fetches diagnostics; validates schema
- `test_generation_e2e.py` — runs CReM-dock pipeline end-to-end on small example

**Acceptance:** All integration tests pass in CI.

---

### X2: 90-day rollup documentation

**File:** `docs/90_DAY_PROGRESS_REPORT.md`

**Action:** Auto-generated rollup document covering:
- What was implemented per workstream
- Verification results from Workstream A
- Performance metrics for new features
- Known limitations
- Recommended next steps

**Acceptance:** Document generated at the end of the 90-day window.

---

### X3: Master CI workflow

**File:** `.github/workflows/master_ci.yml`

**Action:** Aggregate all per-workstream CI workflows into one master pipeline. Runs all verification, regression, and integration tests on every PR.

**Acceptance:** Master workflow passes.

---

## 10. Acceptance Criteria for 90-Day Plan Complete

All of the following hold:

1. **Workstream A passes**: T1 backends verified to serve live predictions; conformal coverage in range; DT50 NLL and σ-correlation meeting targets.

2. **Workstream B**: 5 reference compound demo bundles exist with predictions, screenshots, dossier PDFs. CI regenerates on releases.

3. **Workstream C**: Knowledge Hub RAG live. Citations validated. Conversation persistence works. Settings configurable.

4. **Workstream D**: OPERA Tier-3 backends registered for ≥ 6 endpoints. Compare-with-OPERA UI affordance functional.

5. **Workstream E**: Interactive calibration diagnostics in ModelCardViewer. Live AD distance for Inspector compounds.

6. **Workstream F**: CReM + EasyDock integrated. License audit completed and clean. Generation Workbench UI functional. Closed-loop scoring via T1 backends works.

7. All integration tests pass in CI.

8. 90-day progress report generated.

---

## 11. Out of Scope

Do NOT in the 90-day window:

- Train any new ML models (use what Phase 2-5 produced)
- Modify Phase 1 datasets
- Build the Phase 6 bioisostere engine (deferred to next quarter)
- Build the Docking Workbench from scratch (assume existing Vina integration; CReM uses it)
- Add new endpoints to the model registry
- Implement local-LLM fallback for Workstream C (deferred)
- Build multi-user features
- Build cloud sync
- Implement Paper 2 selectivity integration (deferred until Paper 2 ready)
- Replace NGL.js with a different 3D viewer
- Implement covalent or flexible-sidechain docking

---

## 12. Risk Register

| Risk | Mitigation |
|---|---|
| Workstream A finds failures | Stop and remediate before B-F; document remediation |
| OPERA installation breaks on a target platform | Document; mark as optional T3 on that platform |
| Anthropic API costs are higher than projected | Default to Haiku 4.5; expose token monitoring; rate-limit per session |
| CReM ecosystem dependencies introduce GPL contamination | License audit (F-pre) catches; halt that component; document alternatives |
| Knowledge Hub embeddings model is slow on Windows | Provide fallback to remote embedding API (Voyage AI or OpenAI) — document the privacy tradeoff |
| CReM-dock pipeline is too slow for interactive use | Run in background worker; show progress; cache aggressively |
| Reference compound demo bundles drift as models retrain | CI regeneration on releases; commit reference values to expected_predictions/ for drift detection |
| GUI calibration diagnostics chart rendering is slow on large test sets | Subsample diagnostics data above N=1000 with appropriate stratification; document |
| EasyDock multi-engine support broken on one engine | Default to Vina; mark others as opt-in |

---

## 13. Workstream Sequencing Decision Tree

If single agent, execute in this order:
1. **A (mandatory first)** — 2-3 days
2. **B** — 1 week
3. **D** — 3-4 weeks (faster than C; unblocks more T3 conversations)
4. **C** — 4-5 weeks (interleaved with E start)
5. **E** — 2-3 weeks
6. **F** — 6-8 weeks (largest; ends the 90-day window)

If multiple agents available:
- Agent 1: A → B → D → E
- Agent 2: F-pre → C → F
- Both converge for X1-X3 cross-cutting work

---

## 14. Deviation Log

Maintain `docs/90_DAY_NOTES.md` recording:
- Workstream completion dates
- License audit results per CReM component
- Anthropic API cost incurred during development
- Any verification (Workstream A) failures and resolutions
- Per-endpoint OPERA mapping decisions
- Performance benchmarks for generation pipeline
- Documentation gaps to fix in subsequent quarters

---

**End of 90-Day Implementation Plan.**
