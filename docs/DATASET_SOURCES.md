# Edeon Phase 1 — Dataset Provenance and Sources

This document details the provenance, citation, access details, licensing terms, and retrieval methods for all raw datasets consumed by Phase 1 of the Edeon project.

---

## Source Inventory

The following table summarizes the primary public sources used to construct the Edeon data foundation:

| Source Identifier | Associated Endpoints | License | Retrieval Method |
|---|---|---|---|
| **ApisTox** | `bee_acute_oral_ld50`, `bee_acute_contact_ld50` | CC BY-NC 4.0 | Zenodo bulk download |
| **NICEATM ICE / CATMoS** | `rat_acute_oral_ld50` | Public Domain | ICE API / download |
| **US EPA ECOTOX** | `fish_acute_lc50`, `daphnia_acute_ec50`, `algae_growth_ec50`, `bird_acute_oral_ld50` | Public Domain | ASCII bulk download |
| **EPA Williams Ensemble** | `fish_acute_lc50` | Open Access | Supp. Excel sheet |
| **QsarDB (Kotli 2024)** | `earthworm_acute_lc50` | CC BY-NC-ND 3.0 | QDB repository zip |
| **Pore et al. 2024** | `earthworm_acute_lc50` | Open Access | Supp. Excel sheet |
| **EFSA OpenFoodTox** | `bird_acute_oral_ld50` | CC BY 4.0 | Zenodo deposit |
| **NIEHS OPERA** | `soil_koc`, `bcf` | MIT License | GitHub repository |
| **enviPath (EAWAG-SOIL)** | `soil_dt50` | CC BY 4.0 | Manual package export |
| **NICEATM LLNA** | `skin_sensitization` | Public Domain | NIEHS site download |
| **ICCVAM CCS** | `skin_sensitization` | Public Domain | NIEHS site download |

---

## Detailed Provenance Metadata

### 1. ApisTox
- **Primary Citation**: Adamczyk J, Poziemski J, Siedlecki P (2025). ApisTox: a comprehensive database of honey bee acute toxicity. *Sci Data* 12:5.
- **DOI**: [10.1038/s41597-024-04232-w](https://doi.org/10.1038/s41597-024-04232-w)
- **Access URL**: [https://zenodo.org/records/11062076](https://zenodo.org/records/11062076)
- **Access Date**: 2026-05-30
- **File Format**: CSV (`dataset_final.csv`)
- **Retrieval Method**: Programmatically verified from Zenodo bulk release.

### 2. NICEATM ICE / CATMoS
- **Primary Citation**: Mansouri K, et al. (2021). CATMoS: Collaborative Acute Toxicity Modeling Suite. *Environ Health Perspect* 129(4):47013.
- **DOI**: [10.1289/EHP8495](https://doi.org/10.1289/EHP8495)
- **Access URL**: [https://ice.ntp.niehs.nih.gov/](https://ice.ntp.niehs.nih.gov/)
- **Access Date**: 2026-05-30
- **File Format**: TSV / CSV
- **Retrieval Method**: Downloaded from the NTP Interagency Center for the Evaluation of Alternative Toxicological Methods (NICEATM) Integrated Chemical Environment (ICE).

### 3. US EPA ECOTOX
- **Primary Citation**: US Environmental Protection Agency (EPA). ECOTOXicology Knowledgebase (ECOTOX).
- **Access URL**: [https://cfpub.epa.gov/ecotox/](https://cfpub.epa.gov/ecotox/)
- **Access Date**: 2026-05-31
- **File Format**: ASCII text delimited tables (bulk export)
- **Retrieval Method**: Downloaded as bulk ASCII database tables; parsed using custom Polars/Pandas scripts.

### 4. EPA Williams Ensemble
- **Primary Citation**: Williams AJ, et al. (2017). The CompTox Chemistry Dashboard: a community data resource. *Bioinformatics* 33(21):3396–3402.
- **DOI**: [10.1021/acs.est.9b03063](https://doi.org/10.1021/acs.est.9b03063)
- **Access URL**: [https://doi.org/10.1021/acs.est.9b03063](https://doi.org/10.1021/acs.est.9b03063)
- **Access Date**: 2026-05-30
- **File Format**: Excel Spreadsheet (`williams_ensemble.xlsx`)
- **Retrieval Method**: Extracted from journal supplementary resources.

### 5. QsarDB (Kotli 2024)
- **Primary Citation**: Kotli M, Piir G, Maran U (2024). Quantitative structure-activity relationships for the acute toxicity of chemicals to earthworm (Eisenia fetida). *J. Hazard. Mater.* 461:132577.
- **DOI**: [10.15152/QDB.258](https://doi.org/10.15152/QDB.258)
- **Access URL**: [https://qsardb.org/repository/handle/10967/258](https://qsardb.org/repository/handle/10967/258)
- **Access Date**: 2026-06-02
- **File Format**: QsarDB zip repository archive (`final_arch_exp.zip`)
- **Retrieval Method**: Manual retrieval from the QsarDB open repository.

### 6. Pore et al. 2024
- **Primary Citation**: Pore S, et al. (2024). Development of global and local QSAR models for predicting earthworm toxicity of pesticides. *J. Hazard. Mater.* 479:135725.
- **DOI**: [10.1016/j.jhazmat.2024.135725](https://doi.org/10.1016/j.jhazmat.2024.135725)
- **Access URL**: [https://doi.org/10.1016/j.jhazmat.2024.135725](https://doi.org/10.1016/j.jhazmat.2024.135725)
- **Access Date**: 2026-06-02
- **File Format**: Excel Spreadsheet (`pore_2024.xlsx`)
- **Retrieval Method**: Downloaded from the publisher's supplementary resources.

### 7. EFSA OpenFoodTox
- **Primary Citation**: European Food Safety Authority (EFSA). OpenFoodTox: EFSA's chemical hazards database.
- **DOI**: [10.5281/zenodo.8120114](https://doi.org/10.5281/zenodo.8120114)
- **Access URL**: [https://www.efsa.europa.eu/en/data-report/chemical-hazards-database-openfoodtox](https://www.efsa.europa.eu/en/data-report/chemical-hazards-database-openfoodtox)
- **Access Date**: 2026-05-31
- **File Format**: CSV Zenodo deposit
- **Retrieval Method**: Retained from the official Zenodo OpenFoodTox bulk package.

### 8. NIEHS OPERA
- **Primary Citation**: Mansouri K, et al. (2018). OPERA models for predicting physicochemical properties and environmental fate endpoints. *J. Cheminform.* 10:10.
- **DOI**: [10.1186/s13321-018-0263-1](https://doi.org/10.1186/s13321-018-0263-1)
- **Access URL**: [https://github.com/NIEHS/OPERA](https://github.com/NIEHS/OPERA)
- **Access Date**: 2026-05-31
- **File Format**: SDF (Structured Data File)
- **Retrieval Method**: Cloned training/testing partitions directly from the open source GitHub repository.

### 9. enviPath (EAWAG-SOIL)
- **Primary Citation**: Wicker J, Fenner K, Ellis L, Wackett L, Griebel S (2016). enviPath - The environmental fate pathway database. *Nucleic Acids Res.* 44(D1):D502-D508.
- **DOI**: [10.1093/nar/gkw974](https://doi.org/10.1093/nar/gkw974)
- **Access URL**: [https://envipath.org/](https://envipath.org/)
- **Access Date**: 2026-06-02
- **File Format**: CSV Soil package export (`soil_package.csv`)
- **Retrieval Method**: Manually exported from the enviPath web system (requires authenticated account).

### 10. NICEATM LLNA
- **Primary Citation**: National Toxicology Program Interagency Center for the Evaluation of Alternative Toxicological Methods (NICEATM). Local Lymph Node Assay (LLNA) database.
- **Access URL**: [https://ntp.niehs.nih.gov/whatwestudy/topics/toxico/niceatm](https://ntp.niehs.nih.gov/whatwestudy/topics/toxico/niceatm)
- **Access Date**: 2026-06-02
- **File Format**: CSV (`niceatm_llna.csv`)
- **Retrieval Method**: Manually retrieved from NICEATM public data releases.

### 11. ICCVAM CCS
- **Primary Citation**: Interagency Coordinating Committee on the Validation of Alternative Methods (ICCVAM). Cosmetics Substance (CCS) sensitization dataset.
- **Access URL**: [https://ntp.niehs.nih.gov/whatwestudy/topics/toxico/niceatm](https://ntp.niehs.nih.gov/whatwestudy/topics/toxico/niceatm)
- **Access Date**: 2026-06-02
- **File Format**: CSV (`iccvam_ccs.csv`)
- **Retrieval Method**: Manually retrieved from NICEATM/ICCVAM reference substance databases.
