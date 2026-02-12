# Environmental Transformation Rules (Feature I6 Provenance & Audit)

## 1. BioTransformer & Commercial Exclusion Audit
BioTransformer is a published rule-based metabolite prediction tool. However, its licensing terms impose commercial redistribution restrictions. Consequently, BioTransformer binaries and network calls are **excluded** from Edeon Desktop. All SMIRKS rules in Edeon are authored and maintained directly within the engine under open permissive terms.

## 2. Rule Classes & Scientific Literature Provenance

### 2.1 Soil Microbial Transformation Rules (`soil_microbial`)
- **N-Dealkylation:** Cleavage of alkyl groups from amine or amide nitrogens (common in chloroacetamide and triazine herbicides).
- **O-Demethylation:** Cleavage of methyl ethers to phenols (e.g. methoxychlor, dicamba derivatives).
- **Nitroreduction:** Reduction of aromatic nitro groups ($Ar-NO_2 \rightarrow Ar-NH_2$) via microbial nitroreductases.
- **Aromatic Hydroxylation:** Insertion of hydroxyl groups onto aromatic rings by soil Pseudomonas species.

### 2.2 Photolysis Rules (`photolysis`)
- **Reductive Dehalogenation:** Loss of halogen atoms ($Cl, Br$) from aromatic rings under solar UV irradiation.
- **Di-aryl Ether Cleavage:** Cleavage of diphenyl ether linkages under sunlight (e.g. diphenyl ether herbicides).

### 2.3 Hydrolysis Rules (`hydrolysis`)
- **Ester Hydrolysis:** Cleavage of esters to carboxylic acid and alcohol microspecies (pH-dependent).
- **Carbamate Cleavage:** Cleavage of carbamate linkages to amines, $CO_2$, and alcohols.
- **Nitrile Hydrolysis:** Conversion of cyano groups ($R-CN$) to primary amides and carboxylic acids.

## 3. Metabolite Rescoring & Liability Flagging
Each generated metabolite undergoes automatic rescoring against parent compound benchmarks:
- **DT50 Soil Persistence:** If metabolite $DT50 > 1.2 \times \text{parent } DT50$, it is flagged for accumulation risk.
- **Aquatic Ecotox:** If metabolite fish or bee toxicity level exceeds the parent toxicity class, it receives `liability_flag: true`.
