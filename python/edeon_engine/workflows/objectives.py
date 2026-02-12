import os
import sqlite3
from rdkit import Chem
from rdkit import DataStructs
from rdkit.Chem import AllChem
from rdkit.Chem.Scaffolds import MurckoScaffold

# Standard selectivity thresholds for non-target organisms
SELECTIVITY_THRESHOLDS = {
    "Mammal": 10.0,
    "Honeybee": 3.0,
    "Earthworm": 3.0,
    "Fish": 3.0,
    "Daphnia": 3.0,
    "Bird": 5.0
}

def get_bemis_murcko_scaffold(smiles: str) -> str:
    """Returns the canonical Bemis-Murcko scaffold SMILES for a given SMILES."""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return ""
    try:
        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        return Chem.MolToSmiles(scaffold)
    except Exception:
        return ""

def maximin_selectivity(analog_selectivity: dict, lead_selectivity: dict, penalize_ood: bool = False) -> dict:
    """
    Evaluates maximin selectivity:
    - score = min(selectivity_index over non-targets)
    - lift = analog_min_margin - lead_min_margin
    - checks if any other margin drops below threshold compared to the lead
    - optionally penalizes if predictions are Out-Of-Domain
    
    Returns:
        dict with:
            score: float (analog's minimum margin)
            lift: float
            collapses_margin: bool (whether any margin dropped below threshold AND below lead's margin)
            is_ood: bool
            final_rank_score: float (score with penalties applied)
    """
    # 1. Extract analog margins
    analog_margins = {}
    is_ood = False
    for p in analog_selectivity.get("profiles", []):
        org = p.get("organism")
        val = p.get("selectivity_index", 0.0)
        analog_margins[org] = val
        if p.get("ad_status") in ["out", "out_of_domain"]:
            is_ood = True
            
    # 2. Extract lead margins
    lead_margins = {}
    for p in lead_selectivity.get("profiles", []):
        org = p.get("organism")
        val = p.get("selectivity_index", 0.0)
        lead_margins[org] = val

    if not analog_margins:
        return {
            "score": 0.0,
            "lift": 0.0,
            "collapses_margin": True,
            "is_ood": True,
            "final_rank_score": -9999.0
        }

    # 3. Compute minimin margins
    analog_min = min(analog_margins.values())
    lead_min = min(lead_margins.values()) if lead_margins else 0.0
    lift = analog_min - lead_min

    # 4. Check if any other margin drops below threshold
    collapses_margin = False
    for org, threshold in SELECTIVITY_THRESHOLDS.items():
        a_val = analog_margins.get(org, 0.0)
        l_val = lead_margins.get(org, 0.0)
        # It collapses if the analog margin is below threshold AND is worse than the lead margin
        if a_val < threshold and a_val < l_val:
            collapses_margin = True
            break

    # 5. Compute ranking score
    # Primary sort by lift, but penalize heavily if we collapse margins
    final_rank_score = lift
    if collapses_margin:
        final_rank_score -= 1000.0
    if penalize_ood and is_ood:
        final_rank_score -= 100.0

    return {
        "score": round(analog_min, 1),
        "lift": round(lift, 1),
        "collapses_margin": collapses_margin,
        "is_ood": is_ood,
        "final_rank_score": round(final_rank_score, 1)
    }

def scaffold_novelty(candidate_smiles: str, lead_smiles: str) -> dict:
    """
    Computes scaffold novelty metrics between a candidate and a lead molecule.
    Returns:
        dict with:
            novelty: float (1 - Tanimoto similarity)
            is_novel_scaffold: bool (different Bemis-Murcko scaffolds)
            min_ref_distance: float (minimum Tanimoto distance to reference actives)
            nearest_ref_active: str (name of the closest reference active)
    """
    cand_mol = Chem.MolFromSmiles(candidate_smiles)
    lead_mol = Chem.MolFromSmiles(lead_smiles)
    
    if not cand_mol or not lead_mol:
        return {
            "novelty": 0.0,
            "is_novel_scaffold": False,
            "min_ref_distance": 0.0,
            "nearest_ref_active": "Unknown"
        }
        
    cand_fp = AllChem.GetMorganFingerprintAsBitVect(cand_mol, 2, nBits=2048)
    lead_fp = AllChem.GetMorganFingerprintAsBitVect(lead_mol, 2, nBits=2048)
    
    sim = DataStructs.TanimotoSimilarity(cand_fp, lead_fp)
    novelty = 1.0 - sim
    
    # Bemis-Murcko scaffold comparison
    cand_scaffold = get_bemis_murcko_scaffold(candidate_smiles)
    lead_scaffold = get_bemis_murcko_scaffold(lead_smiles)
    
    # Scaffolds are novel if they are different, and candidate actually has a scaffold (or lead has one)
    # If both have no ring, they have empty scaffolds which is equal, but that's not a scaffold hop
    is_novel_scaffold = (cand_scaffold != lead_scaffold) and (cand_scaffold != "")
    
    # Min distance to reference active library
    min_ref_distance = 1.0
    nearest_ref_active = "None"
    
    try:
        db_path = os.path.join(os.path.dirname(__file__), "..", "reference", "reference_actives.sqlite")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name, smiles FROM actives")
            rows = cursor.fetchall()
            
            for row in rows:
                ref_smiles = row["smiles"]
                ref_mol = Chem.MolFromSmiles(ref_smiles)
                if not ref_mol:
                    continue
                ref_fp = AllChem.GetMorganFingerprintAsBitVect(ref_mol, 2, nBits=2048)
                ref_sim = DataStructs.TanimotoSimilarity(cand_fp, ref_fp)
                ref_dist = 1.0 - ref_sim
                if ref_dist < min_ref_distance:
                    min_ref_distance = ref_dist
                    nearest_ref_active = row["name"]
            conn.close()
    except Exception:
        pass
        
    return {
        "novelty": round(novelty, 4),
        "is_novel_scaffold": is_novel_scaffold,
        "min_ref_distance": round(min_ref_distance, 4),
        "nearest_ref_active": nearest_ref_active
    }
