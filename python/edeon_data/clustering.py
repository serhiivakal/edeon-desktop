"""
Edeon Engine — Chemical Diversity Clustering and Down-sampling
Uses RDKit Morgan fingerprints, Butina clustering, and MaxMin picker,
or Bemis-Murcko scaffolds.
"""

from rdkit import Chem
from rdkit import DataStructs
from rdkit.Chem import AllChem
from rdkit.SimDivFilters.rdSimDivPickers import MaxMinPicker
from rdkit.ML.Cluster import Butina
from rdkit.Chem.Scaffolds import MurckoScaffold


def compute_fingerprints(mols: list) -> list:
    """Compute 2048-bit Morgan fingerprints (R=2) for RDKit molecules."""
    fps = []
    for mol in mols:
        if mol is None:
            fps.append(None)
        else:
            fps.append(AllChem.GetMorganFingerprintAsBitVect(mol, 2, 2048))
    return fps


def select_diverse_subset_bemis_murcko(
    smiles_list: list[str],
    target_size: int = 500,
) -> list[int]:
    """
    Select a diverse subset using Bemis-Murcko scaffolds.
    Molecules are grouped by their Murcko scaffold SMILES.
    Representatives are chosen in a round-robin fashion from each scaffold group.
    """
    mols = [Chem.MolFromSmiles(s) for s in smiles_list]
    valid_mols = []
    index_map = []
    for idx, mol in enumerate(mols):
        if mol is not None:
            valid_mols.append(mol)
            index_map.append(idx)

    if not valid_mols:
        return []

    scaffolds = {}
    for i, mol in enumerate(valid_mols):
        orig_idx = index_map[i]
        try:
            scf = MurckoScaffold.GetScaffoldForMol(mol)
            scf_smiles = Chem.MolToSmiles(scf)
        except Exception:
            scf_smiles = ""

        # Treat acyclic molecules as unique scaffolds so they are not collapsed
        if not scf_smiles:
            scf_key = f"acyclic-{orig_idx}"
        else:
            scf_key = scf_smiles

        if scf_key not in scaffolds:
            scaffolds[scf_key] = []
        scaffolds[scf_key].append(orig_idx)

    # Round-robin selection
    selected_indices = []
    scaffold_keys = list(scaffolds.keys())
    scaffold_keys.sort()  # Stable order

    while len(selected_indices) < target_size:
        added_any = False
        for key in scaffold_keys:
            if scaffolds[key]:
                selected_indices.append(scaffolds[key].pop(0))
                added_any = True
                if len(selected_indices) == target_size:
                    break
        if not added_any:
            break

    return sorted(selected_indices)


def select_diverse_subset(
    smiles_list: list[str],
    similarity_threshold: float = 0.7,
    target_size: int = 500,
    algorithm: str = "morgan",
) -> list[int]:
    """
    Select a diverse subset of compounds using either:
    - 'morgan': Butina clustering followed by MaxMin picker down-sampling
    - 'bemis_murcko': Bemis-Murcko scaffold round-robin selection
    """
    if algorithm == "bemis_murcko":
        return select_diverse_subset_bemis_murcko(smiles_list, target_size)

    mols = [Chem.MolFromSmiles(s) for s in smiles_list]
    fps = compute_fingerprints(mols)

    # Filter out None values and keep mapping of valid indexes
    valid_fps = []
    index_map = []
    for idx, fp in enumerate(fps):
        if fp is not None:
            valid_fps.append(fp)
            index_map.append(idx)

    nPts = len(valid_fps)
    if nPts == 0:
        return []

    # If pool is small enough, return all valid indices
    if nPts <= 1:
        return index_map

    # Step 1: Butina clustering to filter by similarity threshold
    dist_thresh = 1.0 - similarity_threshold
    dists = []
    for i in range(1, nPts):
        sims = DataStructs.BulkTanimotoSimilarity(valid_fps[i], valid_fps[:i])
        for j in range(i):
            dists.append(1.0 - sims[j])

    # Cluster data
    clusters = Butina.ClusterData(dists, nPts, dist_thresh, isDistData=True)

    # Pick the cluster centroid (first element in each cluster tuple)
    butina_indices = [c[0] for c in clusters]

    # Map back to original list indices
    representatives = [index_map[i] for i in butina_indices]

    # Step 2: If we have more compounds than target_size, run MaxMin picker to get target_size
    if len(representatives) > target_size:
        rep_fps = [fps[i] for i in representatives]
        n_reps = len(rep_fps)

        def dist_fn(i, j):
            return 1.0 - DataStructs.TanimotoSimilarity(rep_fps[i], rep_fps[j])

        picker = MaxMinPicker()
        picked_subset_indices = list(picker.LazyPick(dist_fn, n_reps, target_size))
        representatives = [representatives[i] for i in picked_subset_indices]

    return sorted(representatives)
