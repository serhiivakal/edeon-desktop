# Mechanistic Systemic-Mobility Model (Kleier & Bromilow Ion-Trap Models)

## 1. Executive Summary
This document specifies the mechanistic phloem and xylem systemic mobility model integrated into Edeon Desktop (Feature J8). Rather than relying on simple 2D structural heuristics, Edeon employs the published ion-trap concentration relationships established by Kleier (1988) and Bromilow et al. (1990).

## 2. Model Physics & Mechanics

### 2.1 Apoplast vs Phloem pH Gradient
Weak-acid agrochemicals enter plant cells via passive permeability in the apoplast (pH ≈ 5.5). Inside the phloem symplast (pH ≈ 8.0), weak acids ionize into their conjugate base forms ($A^-$). Because membranes are significantly less permeable to charged ions than neutral molecules ($HA$), the compound becomes trapped inside the phloem sieve tubes and undergoes long-distance basipetal translocation toward sink tissues (roots, young leaves).

### 2.2 Bromilow Weak-Acid Phloem Concentration Factor (CF)
The equilibrium phloem concentration factor $CF_{phloem}$ is derived from the Henderson-Hasselbalch ratio across apoplastic ($pH_{apo} = 5.5$) and phloem ($pH_{phloem} = 8.0$) compartments:

$$CF_{phloem} = \frac{1 + 10^{(pH_{phloem} - pKa)}}{1 + 10^{(pH_{apo} - pKa)}}$$

For weak acids with $pKa \in [3.0, 6.0]$, $CF_{phloem}$ ranges from 10 to >300, providing strong thermodynamic driving force for phloem translocation.

### 2.3 Kleier Permeability & Mobility Indices
Extremely hydrophilic compounds ($log K_{ow} < -1$) cannot permeate plant cell membranes (immobile).
Extremely lipophilic compounds ($log K_{ow} > 3.5$) partition too strongly into lipophilic cuticle and organelle membranes, preventing systemic translocation (immobile / retained).
Compounds in the optimal permeability window ($log K_{ow} \in [0, 3]$, $pKa \in [3, 6.5]$) demonstrate **ambimobility** (moving via both xylem and phloem).

- **Xylem Index ($I_{xylem}$):** Function of $log K_{ow}$ governing transpiration stream movement in apoplast.
- **Phloem Index ($I_{phloem}$):** Product of membrane permeability and $CF_{phloem}$.

## 3. Classification Taxonomy
- **Phloem-Mobile (`phloem`):** $CF_{phloem} > 2.0$ and $log K_{ow} \in [-0.5, 3.5]$.
- **Xylem-Mobile (`xylem`):** Non-ionized or basic compound with $log K_{ow} \in [-1.0, 2.5]$ and low $CF_{phloem}$.
- **Ambimobile (`ambimobile`):** High $CF_{phloem}$ combined with balanced lipophilicity enabling both xylem and phloem translocation.
- **Immobile (`immobile`):** Either excessive lipophilicity ($log K_{ow} > 4.0$) or extreme hydrophilicity without acidic ion trapping.
