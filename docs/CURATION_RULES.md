# Edeon Data Curation Pipeline Rules Specification

This document details the shared standardisation, curation, normalisation, and aggregation protocols applied across all endpoints in Phase 1 of the Edeon project.

---

## 1. Structure Standardisation Rules

All structures undergo a unified curation sequence using RDKit and `chembl-structure-pipeline`. The steps are applied in strict order:

1. **SMILES Parsing**: Structures are parsed with `Chem.MolFromSmiles(smiles, sanitize=True)`. Parse failures are rejected immediately.
2. **Charged Salt Pre-stripping**: RDKit's `rdMolStandardize.FragmentParent` is applied to robustly strip charged simple counterions (e.g. `Na+`, `Cl-`) and isolate the largest organic fragment.
3. **ChEMBL Normalisation & Parent Selection**:
   - `chembl_structure_pipeline.standardize_mol()` handles aromaticity perception and functional group normalisation.
   - `chembl_structure_pipeline.get_parent_mol()` applies USAN-standard salt/solvent stripping and neutralisation of common charged forms.
4. **Atom Allowlist Filtering**: Compounds containing any atom symbols outside the canonical organic set are rejected:
   - Canonical Organic Set: `{H, B, C, N, O, F, Si, P, S, Cl, Se, Br, I}`
   - *Note*: Specific legacy endpoints may optionally include a restricted agro-metals allowlist (`{Cu, Zn, Mn, Sn, Hg}`) if historically justified, documented in the data card.
5. **Molecular Weight (MW) Size Filter**: Compounds are rejected if their parent MW is outside:
   - `50.0 Da <= MW <= 1500.0 Da`
6. **Tautomer Canonicalisation**: RDKit's `MolStandardize.rdMolStandardize.TautomerEnumerator().Canonicalize()` selects a deterministic canonical tautomer.
7. **InChIKey & Canonical SMILES Generation**:
   - Canonical isomeric SMILES generated using `Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)`.
   - Authoritative 14-block InChIKey generated using `Chem.MolToInchiKey(mol)`.

### 1.1 Rejection Logging

Any rejected record is logged to `curation_log.json` containing:
- Original SMILES (if present)
- Rejection stage (`parse`, `chembl_pipeline`, `atom_filter`, `size_filter`, `generation`)
- Rejection reason

---

## 2. Activity Curation & Normalisation

### 2.1 Regression Endpoints
- **Canonical Units**: All values converted to their respective canonical units (e.g., `ug/bee` for bees, `mg/L` for aquatic organisms, `mg/kg` for rats/birds).
- **Log10 Transformation**: Right-skewed distributions are transformed to logarithmic scales:
  - Concentrations: `value_log = log10(molar_concentration)` or `-log10(molar_concentration)` (pLC50/pEC50).
  - Doses: `value_log = log10(mg_per_kg)` or `-log10(mg_per_kg)`.
- **Censored Qualifiers**: Records containing `>`, `<`, `>=`, `<=` are flagged kept (`["censored_upper"]` or `["censored_lower"]`).
- **Non-positive Values**: Records with values <= 0 are rejected as they cannot be log-transformed.

### 2.2 Classification Endpoints
- Source categorical labels are mapped to explicit canonical class sets.
- Mappings are declared in the endpoint's respective Data Card.

---

## 3. Duplicate Aggregation Protocols

For records sharing the identical canonical `inchikey`:

- **Regression**:
  - `value` is the geometric mean of the raw values.
  - `value_log` is the arithmetic mean of the raw `value_log`s.
  - `aggregation_cv` is the coefficient of variation (`std / mean`).
  - Flag `"high_cv"` is added if CV > 0.5.
  - Flag `"extreme_variance"` is added if count > 10 and CV > 1.0.
- **Classification**:
  - Majority vote selects the target category.
  - In case of a tie, the flag `"class_conflict"` is appended and the *more conservative* (higher concern/toxicity) class is chosen.

---

## 4. Per-Endpoint Curation Rules

The rules, canonical units, transform strategies, and exclusion criteria for individual endpoints are detailed in the following sections:

### 4.1 bee_acute_oral_ld50 & bee_acute_contact_ld50
- **Primary Source**: ApisTox Zenodo archive (v1.0).
- **Inclusion Criteria**:
  - Acute oral or contact honeybee toxicity records (LD50).
  - Target species: *Apis mellifera* only.
  - Retain the ApisTox time-split as the canonical time split.
- **Exclusion Criteria**:
  - Mixtures, formulations, or records with missing structures.
  - Records with non-positive values.
  - Compounds containing atoms outside default allowlist + `{Cu}` (copper-based apiary treatments).
- **Canonical Units**: `ug/bee`.
- **Activity Transform**: continuous regression where `value_log = log10(LD50_ug_per_bee)`.
- **Classification Version**: auxiliary labels saved under `value_class` using `{"toxic", "nontoxic"}` binary toxicity labels.

### 4.2 rat_acute_oral_ld50
- **Primary Source**: EPA CATMoS via NICEATM ICE.
- **Inclusion Criteria**:
  - In vivo rat acute oral toxicity records (LD50).
  - Restricted to experimental in vivo assays (no in vitro or read-across estimates).
- **Exclusion Criteria**:
  - Mixtures, formulations, or records with missing structures.
  - Non-positive numeric values.
  - Compounds containing atoms outside default organic allowlist.
- **Canonical Units**: `mg/kg bw`.
- **Activity Transform**: continuous regression where `value_log = log10(LD50_mmol_per_kg)` (computed with MW where molecular weight is available, falling back to `log10(LD50_mg_per_kg)`).
- **Classification Version**: maps to GHS acute oral categories 1–5, encoded as `value_class`.

### 4.3 fish_acute_lc50
- **Primary Sources**: US EPA ECOTOX ASCII bulk download and Williams et al. ensemble fish toxicity training data.
- **Inclusion Criteria**:
  - In vivo fish acute LC50 toxicity records.
  - Endpoint = `LC50`, Effect = `MOR` (mortality), test duration = 96h (with 5% tolerance: 91.2h - 100.8h).
  - Species restricted to 6 target regulatory fish species: *Oncorhynchus mykiss*, *Pimephales promelas*, *Lepomis macrochirus*, *Cyprinus carpio*, *Danio rerio*, *Salmo salar*.
  - Exposure type = aquatic.
- **Exclusion Criteria**:
  - Non-aquatic exposure routes (injection, dietary, dermal, oral gavage, etc.).
  - Mixtures, formulations, or records with missing structures.
  - Non-positive values and compounds violating default organic allowlist.
- **Canonical Units**: `mg/L`.
- **Activity Transform**: continuous regression where `value_log = log10(LC50_mol_per_L)` (pLC50). Prefer ECOTOX over Williams ensemble during cross-merge deduplication.

### 4.4 daphnia_acute_ec50
- **Primary Source**: US EPA ECOTOX database.
- **Inclusion Criteria**:
  - In vivo Daphnia acute EC50 toxicity records.
  - Endpoint = `EC50`, Effect = `IMM` (immobilisation) or `MOR` (mortality), test duration = 48h (with 5% tolerance: 45.6h - 50.4h).
  - Target species: *Daphnia magna* (primary) and *Daphnia pulex* (secondary, flagged).
- **Exclusion Criteria**:
  - Non-aquatic exposure, mixtures, formulations, or missing structures.
  - Non-positive values and compounds violating default organic allowlist.
- **Canonical Units**: `mg/L`.
- **Activity Transform**: continuous regression where `value_log = log10(EC50_mol_per_L)`.

### 4.5 algae_growth_ec50
- **Primary Source**: US EPA ECOTOX database.
- **Inclusion Criteria**:
  - In vivo green algae growth EC50/ErC50/EbC50 toxicity records.
  - Endpoint ∈ {`EC50`, `ErC50`, `EbC50`}, Effect = `GRO` (growth) or `POP` (population), test duration = 72h (with 10% tolerance: 64.8h - 79.2h).
  - Target species: *Raphidocelis subcapitata*, *Chlorella vulgaris*, *Selenastrum capricornutum*, *Desmodesmus subspicatus*.
  - Preference: growth-rate-based `ErC50` is preferred over biomass-based `EbC50` where both exist.
- **Exclusion Criteria**:
  - Mixtures, formulations, non-positive values, and compounds violating organic allowlist.
- **Canonical Units**: `mg/L`.
- **Activity Transform**: continuous regression where `value_log = log10(EC50_mol_per_L)`.

### 4.6 earthworm_acute_lc50
- **Primary Sources**: Kotli et al. 2024 / QsarDB supplementary compilation and Pore et al. 2024 supplementary database.
- **Inclusion Criteria**:
  - In vivo earthworm acute toxicity (LC50) records.
  - Species restricted to *Eisenia fetida* or *Eisenia andrei*.
  - Assumed OECD 207 (14-day test, soil exposure route, 336h exposure duration) if unspecified.
- **Exclusion Criteria**:
  - Mixtures, formulations, non-positive values, and compounds violating organic allowlist.
- **Canonical Units**: `mg/kg soil` (dry soil weight).
- **Activity Transform**: continuous regression where `value_log = log10(LC50_mg_per_kg)`.

### 4.7 bird_acute_oral_ld50
- **Primary Sources**: US EPA ECOTOX database and EFSA OpenFoodTox chemical hazards database.
- **Inclusion Criteria**:
  - In vivo bird acute oral toxicity records (LD50).
  - Endpoint = `LD50`, exposure route = oral.
  - Species pooled: *Colinus virginianus* (bobwhite quail), *Anas platyrhynchos* (mallard duck), *Coturnix japonica*, *Phasianus colchicus*, *Passer domesticus*.
- **Exclusion Criteria**:
  - Non-oral routes (dermal, inhalation, dietary feed, etc.), mixtures, formulations, non-positive values.
  - Compounds violating default organic allowlist.
- **Canonical Units**: `mg/kg bw`.
- **Activity Transform**: continuous regression where `value_log = log10(LD50_mg_per_kg)`.

### 4.8 soil_koc
- **Primary Sources**: NIEHS OPERA benchmark training/testing datasets and OECD 121 / OECD 106 compilations.
- **Inclusion Criteria**:
  - Soil organic carbon-water partition coefficient (Koc) measurements.
  - Prefer Koc values measured at pH 5.5–7 for ionizable compounds.
- **Exclusion Criteria**:
  - Mixtures, formulations, or compounds violating default organic allowlist.
- **Canonical Units**: `log10 L/kg` (reported as log Koc directly).
- **Activity Transform**: `value_log = log10(Koc)`.
- **Quality / Flagging Heuristics**:
  - `ph_outside_range`: Tagged if Koc measured at pH < 5.5 or pH > 7.0 for ionizables.

### 4.9 soil_dt50
- **Primary Source**: EAWAG-SOIL database via enviPath soil package export.
- **Inclusion Criteria**:
  - Soil half-life (DT50) degradation studies.
  - **One-To-Many Retention**: Retain all individual study measurements per compound to capture irreducible soil study variance; do not average them into a single compound row.
- **Exclusion Criteria**:
  - Mixtures, formulations, non-positive half-lives, and compounds violating organic allowlist.
- **Canonical Units**: `days`.
- **Activity Transform**: continuous regression where `value_log = log10(DT50_days)`.
- **Group Statistics**:
  - `aggregation_n`: represents the total study count for that InChIKey.
  - `aggregation_cv`: represents the coefficient of variation (CV) of DT50 values for the compound.
  - `extreme_variance`: flagged if study count > 10 and CV > 1.0.
  - `high_cv`: flagged if CV > 0.5.

### 4.10 bcf
- **Primary Sources**: NIEHS OPERA BCF benchmark dataset.
- **Inclusion Criteria**: Experimentally measured bioconcentration factors (BCF) on whole-fish organisms.
- **Exclusion Criteria**:
  - Mixtures, formulations, or records lacking chemical structure.
  - Non-organic compounds (violating standard set `{H, B, C, N, O, F, Si, P, S, Cl, Se, Br, I}` or MW outside 50-1500 Da).
  - Tissue-specific BCF records (measurements restricted to liver, gills, kidney, muscle, etc.).
- **Canonical Units**: `L/kg` (wet weight).
- **Activity Transform**: Continuous regression where `value_log = log10(BCF)`.
- **Quality / Flagging Heuristics**:
  - `ionizable`: Compounds matching standard SMARTS patterns for carboxylic acids, phenols, sulfonamides, or aliphatic amines are flagged, as their bioconcentration behaviour deviates from simple neutral logP partition coefficients.

### 4.11 skin_sensitization
- **Primary Sources**: NICEATM LLNA dataset and ICCVAM Cosmetics Substance (CCS) dataset.
- **Inclusion Criteria**:
  - Skin sensitization binary and categorical classification records.
  - Prefer LLNA measurements over CCS in overlapping compound records.
- **Exclusion Criteria**:
  - Mixtures, formulations, and compounds violating default organic allowlist.
- **Canonical Units**: `class`.
- **Activity Transform**:
  - Primary target GHS categories: `"non"`, `"weak"`, `"moderate"`, `"strong"`, and `"sensitizer"` (unknown grade from CCS).
  - Binary categories: `"sensitizer"`, `"non_sensitizer"`.
  - Majority vote used for duplicate resolution, picking the more conservative class in tie conflicts.
  - Standard columns hold the GHS categories, with extra columns `value_class_binary`, `value_binary`, `value_class_ghs`, and `value_ghs` added.
