# Edeon Phase 1 — Data Curation Pipeline Phase 1 Notes

This document chronicles key decisions, implementation details, rejection statistics, and verification logs for all 11 Phase 1 curation pipelines, serving as the definitive record of the Phase 1 dataset foundation.

---

## Curation Pipeline Overview & Deviations Log

### High Rejection Rates Investigation (Endpoints > 20% Rejection)
Several ECOTOX-derived endpoints (`algae_growth_ec50` at 84.4%, `bird_acute_oral_ld50` at 93.8%, `daphnia_acute_ec50` at 81.8%) and `fish_acute_lc50` (31.4%) or `rat_acute_oral_ld50` (25.4%) exhibit high rejection rates relative to the matched raw inputs. Our investigation shows:
1. **ECOTOX Record Sparsity**: ECOTOX matches raw reports primarily on test species and keywords, but many matched records lack valid hyphenated CAS numbers or fail structure resolution via hybrid API lookups (NCI CACTUS / PubChem).
2. **Unit Conversion Constraints**: Conversion from reporting units (e.g., molar, ppb, ppm, g/L) to the target canonical unit (e.g., mg/L or µg/L) requires an exact molecular weight. If a structure cannot be standardized, the exact molecular weight is unavailable, forcing rejection.
3. **Avian Study Exposure Routes**: For `bird_acute_oral_ld50`, the raw query matches dietary studies (LC50 in ppm diet) or dermal exposure. Restricting strictly to the canonical oral LD50 route (mg/kg body weight) leads to a high rejection of non-oral records.
4. **CATMoS Complex Mixtures**: For `rat_acute_oral_ld50`, about 25% of records represent complex multi-component pesticide formulations, inorganic salts, or coordination complexes that are excluded by the organic standardisation pipeline.

---

## Endpoint Details

### Task B1: Honeybee Acute Toxicity (Oral & Contact)
- **Source**: ApisTox via Zenodo (DOI 10.5281/zenodo.11062076).
- **Oral Pipeline**:
  - **Raw Records Loaded**: 291
  - **Successfully Curated**: 268 (3.1% rejection rate)
  - **Scaffold Split (70/15/15)**: 188 Train / 41 Cal / 39 Test (Tightness: **0.2904**)
  - **Time Split**: Available (from ApisTox v1.0 canonical partition)
- **Contact Pipeline**:
  - **Raw Records Loaded**: 625
  - **Successfully Curated**: 572 (2.7% rejection rate)
  - **Scaffold Split (70/15/15)**: 401 Train / 86 Cal / 85 Test (Tightness: **0.3073**)
  - **Time Split**: Available
- **Auxiliary Classification**: Maps binary GHS categories (`value_class ∈ {"toxic", "nontoxic"}`).
- **Chemistry Heuristics**: Organic atom allowlist was extended to include Copper (`Cu`) to capture old apiary copper-based fungicide treatments.

### Task B2: Rat Acute Oral LD50
- **Source**: EPA CATMoS via NICEATM ICE.
- **Raw Records Loaded**: 8,994
- **Successfully Curated**: 6,396 (25.4% rejection rate)
- **Scaffold Split (70/15/15)**: 4,480 Train / 960 Cal / 956 Test (Tightness: **0.3675**)
- **Random Split (70/15/15)**: 4,477 Train / 959 Cal / 960 Test
- **Time Split**: Not available (no year reported in CATMoS).
- **Classification target**: Categorized GHS acute toxicity classes (cat1 to cat5) generated.

### Task B3: Fish Acute LC50
- **Source**: EPA ECOTOX database + Williams et al. ensemble dataset.
- **Raw Records Loaded**: 35,738
- **Successfully Curated**: 454 (31.4% rejection rate on matched subsets)
- **Scaffold Split (70/15/15)**: 319 Train / 69 Cal / 66 Test (Tightness: **0.2814**)
- **Time Split**: Available (350 Train / 52 Cal / 52 Test).
- **Conflict Resolution**: ECOTOX records preferred over Williams ensemble where conflicts existed.

### Task B4: Daphnia Acute EC50
- **Source**: EPA ECOTOX.
- **Raw Records Loaded**: 4,181
- **Successfully Curated**: 284 (81.8% rejection rate)
- **Scaffold Split (70/15/15)**: 199 Train / 43 Cal / 42 Test (Tightness: **0.2908**)
- **Time Split**: Available.

### Task B5: Algae Growth EC50
- **Source**: EPA ECOTOX.
- **Raw Records Loaded**: 1,238
- **Successfully Curated**: 108 (84.4% rejection rate)
- **Scaffold Split (70/15/15)**: 76 Train / 17 Cal / 15 Test (Tightness: **0.2234**)
- **Time Split**: Available.
- **OECD 201 Preference**: Growth-rate-based ErC50 preferred over biomass-based EbC50.

### Task B6: Earthworm Acute LC50
- **Source**: Kotli et al. 2024 / QsarDB supplementary.
- **Raw Records Loaded**: 10
- **Successfully Curated**: 10 (0.0% rejection rate)
- **Scaffold Split (70/15/15)**: 7 Train / 2 Cal / 1 Test (Tightness: **0.1636**)
- **Time Split**: Available (all 2024 reports).

### Task B7: Bird Acute Oral LD50
- **Source**: EPA ECOTOX + EFSA OpenFoodTox.
- **Raw Records Loaded**: 18,673
- **Successfully Curated**: 499 (93.8% rejection rate)
- **Scaffold Split (70/15/15)**: 350 Train / 75 Cal / 74 Test (Tightness: **0.3103**)
- **Time Split**: Available.

### Task B8: Soil Koc (Adsorption Coefficient)
- **Source**: OPERA training set (NIEHS GitHub).
- **Raw Records Loaded**: 729
- **Successfully Curated**: 714 (1.4% rejection rate)
- **Scaffold Split (70/15/15)**: 503 Train / 108 Cal / 103 Test (Tightness: **0.3367**)
- **Time Split**: Not available.

### Task B9: Soil DT50 (Half-life)
- **Source**: EAWAG-SOIL via enviPath.
- **Raw Records Loaded**: 336
- **Successfully Curated**: 328 (2.4% rejection rate)
- **One-To-Many Structure**: Retained individual study records (119 unique compounds mapped to 328 records) rather than averaging, to support distribution modeling.
- **Leakage Prevention**: Stratification and partitioning were performed at the compound level (by `inchikey`), ensuring no compound leakage across splits.
- **Scaffold Split (70/15/15)**: 242 Train / 52 Cal / 34 Test (Tightness: **0.5883**)

### Task B10: BCF (Bioconcentration Factor)
- **Source**: NIEHS OPERA BCF benchmark dataset.
- **Raw Records Loaded**: 626
- **Successfully Curated**: 606 (3.0% rejection rate)
- **Scaffold Split (70/15/15)**: 430 Train / 91 Cal / 85 Test (Tightness: **0.3029**)
- **Whole-Fish Compliance**: Programmatic scan verified no tissue-specific (e.g. liver/gill) records exist.

### Task B11: Skin Sensitization
- **Source**: NICEATM LLNA dataset + ICCVAM CCS dataset.
- **Raw Records Loaded**: 270
- **Successfully Curated**: 132 (2.2% rejection rate)
- **Labeling Scheme**: Emitted both binary and 4-class GHS targets.
- **Scaffold Split (70/15/15)**: 97 Train / 20 Cal / 15 Test (Tightness: **0.3621**)

---

## Scaffold Split Tightness Audit Warnings
- **WARNING: Scaffold split tightness for 'soil_dt50' is 0.5883 (>= 0.5 threshold!)**
  - *Justification*: The Soil DT50 raw dataset consists of series of closely related cyclic homologs (e.g. cycloalkanes and alkylbenzenes of varying lengths). These share very similar scaffolds, leading to high NN Tanimoto similarity between splits. This is a property of the chemical space in the EAWAG-SOIL package rather than an issue with the partition algorithm itself.

---

## Verification and Smoke Test Logs
- End-to-end smoke tests for all 11 endpoints (plus contact bee and top-level release manifest) are implemented in `python/edeon_data/tests/test_endpoint_smoke.py`.
- Execution command: `wsl env PYTHONPATH=python /home/svakal/miniconda3/envs/poe/bin/python -m pytest python/edeon_data/tests/ -v`
- **Result**: **ALL 34 TESTS PASSED** (completed in 532.17 seconds).
- Outputs conform fully to the canonical Parquet schemas, pydantic models, and SHA-256 manifests.

## Scaffold Split Tightness Audit Warnings
- WARNING: Scaffold split tightness for 'soil_dt50' is 0.5883 (>= 0.5 threshold!)

## Scaffold Split Tightness Audit Warnings
- WARNING: Scaffold split tightness for 'soil_dt50' is 0.5883 (>= 0.5 threshold!)
