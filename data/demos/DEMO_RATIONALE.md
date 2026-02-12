# Edeon Demo Suite — Compound Selection Rationale

This document outlines the rationale behind the selection of the five reference pesticides featured in Edeon's Workstream B demonstration bundle. These compounds represent diverse chemical classes, modes of action (insecticide, herbicide, fungicide), and physical-chemical profiles. Together, they demonstrate Edeon's Tier-1 QSAR model accuracy, multi-endpoint ecotoxicity profiling, and environmental fate analysis.

---

## 1. Imidacloprid (Insecticide)
* **Chemical Class:** Neonicotinoid
* **Target Site / MOA:** Nicotinic acetylcholine receptor (nAChR) competitive modulator (IRAC Group 4A)
* **CAS Registry Number:** 138261-41-3
* **Demonstration Value:**
  * **High Ecotoxicity Sensitivity:** Imidacloprid is notorious for high acute toxicity to honeybees. Edeon's Tier-1 classification models for honeybee acute oral and contact LD50 successfully flag it as "Toxic" with high confidence.
  * **Regulatory Triage Alignment:** Demonstrates how Edeon's early-screening workflows align with real-world regulatory decisions (restricted in the EU since 2018 due to pollinator risks).
  * **Metabolite Liability Sweep (W3):** Neonicotinoid metabolites (like imidacloprid-olefin) can retain or exceed parent toxicity. W3 showcases how Edeon tracks these liabilities across predicted degradation pathways.

## 2. Glyphosate (Herbicide)
* **Chemical Class:** Glycine derivative
* **Target Site / MOA:** EPSP synthase inhibitor (HRAC Group G / 9)
* **CAS Registry Number:** 1071-83-6
* **Demonstration Value:**
  * **Polar Zwitterionic Chemistry:** Glyphosate is a small, highly polar, zwitterionic molecule. Many QSAR models collapse on such structures. Edeon's models accurately predict its high mobility (low Koc) and low bioaccumulation potential without generating false toxicity alerts.
  * **Low Mammalian Toxicity Profile:** Shows Edeon's ability to clear a compound on mammalian acute oral toxicity (GHS Category 5 or unclassified) while highlighting high mobility warnings.
  * **Environmental Fate Gauges:** Glyphosate's low Koc and low persistence are displayed in contrast to other more persistent pesticides, demonstrating Edeon's linear gauges.

## 3. Azoxystrobin (Fungicide)
* **Chemical Class:** Strobilurin
* **Target Site / MOA:** Complex III respiration inhibitor (FRAC Group 11)
* **CAS Registry Number:** 131860-33-8
* **Demonstration Value:**
  * **Aquatic Ecotox Profiling:** Azoxystrobin is highly toxic to aquatic organisms (fish and daphnia). Demonstrates Edeon's aquatic hazard profiling and GHS/CLP hazard classification (H400 / H410).
  * **Moderate Persistence:** Demonstrates the boundary evaluation of persistence triggers (DT50 around 84 days) where Edeon flags a "Watch" status rather than a complete showstopper.

## 4. Mesotrione (Herbicide)
* **Chemical Class:** Triketone
* **Target Site / MOA:** HPPD inhibitor (HRAC Group F2 / 27)
* **CAS Registry Number:** 104206-82-8
* **Demonstration Value:**
  * **High Mobility & Leaching Risk:** Mesotrione is highly mobile in soil (low Koc). Demonstrates Edeon's GUS Leaching Index composite model, which combines predicted Koc and Soil DT50 to classify leaching potential.
  * **Low Bioaccumulation:** Shows Edeon's bioconcentration factor (BCF) predictions for hydrophilic compounds.

## 5. Chlorantraniliprole (Insecticide)
* **Chemical Class:** Anthranilic diamide
* **Target Site / MOA:** Ryanodine receptor modulator (IRAC Group 28)
* **CAS Registry Number:** 500008-45-7
* **Demonstration Value:**
  * **Selectivity Window:** Chlorantraniliprole is highly selective toward insect ryanodine receptors, exhibiting low toxicity to mammalian, avian, and honeybee non-target species. Demonstrates Edeon's ability to show high safety margins across species.
  * **High Persistence in Soil:** Shows Edeon's soil persistence cutoff triggers (DT50 > 120 days). Chlorantraniliprole's predicted DT50 (measured ~233 days) triggers a persistent showstopper flag, demonstrating Edeon's safety boundary enforcement.

---

## Summary of Coverage

| Compound | Class | Primary Highlight | Ecotox Concern | Fate Concern |
| :--- | :--- | :--- | :--- | :--- |
| **Imidacloprid** | Insecticide | Pollinator risk & metabolite triage | Honeybees (Oral/Contact) | Moderate persistence |
| **Glyphosate** | Herbicide | Polar chemistry & low ecotox profile | None (Low ecotox) | High mobility (Low Koc) |
| **Azoxystrobin** | Fungicide | CLP Aquatic classification | Fish & Daphnia | Moderate persistence |
| **Mesotrione** | Herbicide | Groundwater leaching index (GUS) | None (Low ecotox) | High mobility / Leaching |
| **Chlorantraniliprole** | Insecticide | Selectivity window & high persistence | Daphnia (high) | High persistence (DT50 > 120d) |
