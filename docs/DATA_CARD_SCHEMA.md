# Edeon Data Card Schema Specification

This document details the YAML schema structure of the `data_card.yaml` generated for each curated endpoint in Phase 1 of the Edeon project.

---

## Data Card Structure Reference

The data card is compiled at the end of each curation run and contains key metadata about dataset provenance, curation details, train/cal/test split sizes, chemical statistics, and security hashes.

### Root Fields

| Field Name | Type | Description |
|---|---|---|
| `dataset_id` | `str` | A unique identifier for the curated dataset (e.g. `edeon-soil-dt50-v1.0`). |
| `endpoint` | `str` | The canonical endpoint identifier matching the Phase 0 Endpoint enum. |
| `version` | `str` | The semantic version of the curated dataset (e.g. `1.0.0`). |
| `created` | `str` | The ISO 8601 UTC timestamp of data card generation (e.g. `2026-06-02T15:00:00Z`). |
| `created_by` | `str` | The agent or system that ran the pipeline (default: `edeon-data-pipeline`). |
| `sources` | `list[SourceMetadata]` | Metadata details of the source database(s) from which the raw data was acquired. |
| `inclusion_criteria` | `list[str]` | The explicit criteria used for including records in the curation pipeline. |
| `exclusion_criteria` | `list[str]` | The explicit criteria used for rejecting records (e.g., disallowed atoms, MW). |
| `standardisation` | `StandardisationMetadata` | Configuration details of the chemical structure standardisation pipeline. |
| `activity` | `ActivityMetadata` | Metadata of the activity transformations and aggregations applied to raw values. |
| `curation_summary` | `CurationSummary` | Record counts at each stage of curation and standardisation. |
| `splits` | `SplitsMetadata` | record sizes and quality statistics for scaffold, random, and time-based splits. |
| `known_biases` | `list[str]` | A list of known scientific or database representation biases in the dataset. |
| `intended_use` | `str` | The recommended use cases for the curated dataset. |
| `not_intended_for` | `list[str]` | Expressly out-of-scope use cases for the curated dataset. |
| `sha256` | `dict[str, str]` | SHA-256 hashes of the output Parquet files (e.g., `curated_parquet`, `scaffold_train`, etc.). |

---

## Sub-Component Schemas

### 1. `SourceMetadata`

Describes the provenance of the raw data.

- `name` (`str`): The common name of the source (e.g. `ApisTox`, `US EPA ECOTOX`).
- `citation` (`str`): The primary bibliographic citation (e.g., academic paper title/journal).
- `doi` (`str`, optional): Digital Object Identifier.
- `url` (`str`, optional): Direct download link or website URL.
- `license` (`str`, optional): The database licensing terms (e.g., `CC BY 4.0`, `Public Domain`).
- `access_date` (`str`, optional): The retrieval date in ISO 8601 format.
- `raw_records` (`int`, optional): Number of records initially loaded from this source.

### 2. `StandardisationMetadata`

Describes standardisation parameters applied during curation.

- `tool` (`str`): The name of the standardisation tool (default: `chembl_structure_pipeline`).
- `version` (`str`): The package version used (e.g., `1.2.4`).
- `tautomer` (`str`): Tautomer enumeration method (default: `rdkit-canonical`).
- `atom_allowlist` (`list[str]`): List of chemical elements allowed (e.g., `["H", "C", "N", "O", ...]`).
- `mw_range` (`list[float]`): A two-element list specifying `[min_mw, max_mw]` (e.g. `[50.0, 1500.0]`).

### 3. `ActivityMetadata`

Describes physical normalisation and transformations.

- `units_canonical` (`str`): The physical units of the final curated values (e.g. `mg/L`, `mg/kg bw`, `days`).
- `log_transform` (`str`, optional): The logarithmic scale type applied (e.g. `log10_molar`, `log10_mg_per_kg`).
- `aggregation` (`str`, optional): Compound-level duplicate aggregation method (e.g. `geometric_mean`, `majority_vote`, `none`).
- `censored_handling` (`str`, optional): Treatment of right- and left-censored boundaries (e.g. `flagged_kept`).

### 4. `CurationSummary`

Represents pipeline attrition statistics.

- `raw_records` (`int`): Initial count of loaded raw records.
- `after_parse` (`int`): Records successfully parsed (chemical structure and targets resolved).
- `after_standardisation` (`int`): Records successfully standardizing to neutral parents.
- `after_filter` (`int`): Records remaining after atom allowlist and mass filters are applied.
- `after_aggregation` (`int`): Records remaining after aggregating duplicate compounds.
- `rejection_rate` (`float`): Ratio of rejected raw records to total loaded records.

### 5. `SplitsMetadata`

Provides partitioning size data for all three frozen split layouts.

- `scaffold` (`ScaffoldSplitMetadata`):
  - `train` (`int`): Number of training records.
  - `cal` (`int`): Number of conformal prediction calibration records.
  - `test` (`int`): Number of test records.
  - `test_to_train_nn_tanimoto_mean` (`float`, optional): Mean Tanimoto similarity of each test compound to its nearest neighbour in the training split.
- `random` (`RandomSplitMetadata`):
  - `train` (`int`): Number of training records.
  - `cal` (`int`): Number of conformal prediction calibration records.
  - `test` (`int`): Number of test records.
  - `seed` (`int`): Random state seed (default: `42`).
- `time` (`TimeSplitMetadata`, optional):
  - `train` (`int`): Number of training records.
  - `cal` (`int`): Number of conformal prediction calibration records.
  - `test` (`int`): Number of test records.
  - `train_year_max` (`int`, optional): Maximum reporting year in train partition.
  - `cal_year_range` (`list[int]`, optional): Min and max year in cal partition.
  - `test_year_range` (`list[int]`, optional): Min and max year in test partition.
  - `status` (`str`, optional): Status of temporal metadata (e.g. `available`, `not_available`).
