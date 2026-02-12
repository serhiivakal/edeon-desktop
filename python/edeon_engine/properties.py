"""
Edeon Engine — Molecular Property Calculation

Computes physicochemical properties using RDKit Descriptors:
- MW (molecular weight)
- LogP (Crippen)
- TPSA (topological polar surface area)
- HBD (hydrogen bond donors)
- HBA (hydrogen bond acceptors)
- RotatableBonds
"""

from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen


def compute_properties_single(smiles: str) -> dict:
    """Compute molecular properties for a single SMILES.

    Returns dict with property values, or None values if SMILES is invalid.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {
            "smiles": smiles,
            "valid": False,
            "mol_weight": None,
            "logp": None,
            "tpsa": None,
            "hbd": None,
            "hba": None,
            "rotatable_bonds": None,
        }

    return {
        "smiles": smiles,
        "valid": True,
        "mol_weight": round(Descriptors.MolWt(mol), 2),
        "logp": round(Crippen.MolLogP(mol), 2),
        "tpsa": round(Descriptors.TPSA(mol), 1),
        "hbd": Descriptors.NumHDonors(mol),
        "hba": Descriptors.NumHAcceptors(mol),
        "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
    }


def compute_properties_batch(smiles_list: list[str], num_workers: int = 1) -> list[dict]:
    """Compute properties for a batch of SMILES strings."""
    if num_workers <= 1 or len(smiles_list) < 5:
        return [compute_properties_single(s) for s in smiles_list]
    from joblib import Parallel, delayed
    return Parallel(n_jobs=num_workers, prefer="threads")(
        delayed(compute_properties_single)(s) for s in smiles_list
    )


def export_results_sdf_batch(compounds: list[dict]) -> str:
    """Assembles a multi-molecule SDF string from SMILES and property data using RDKit."""
    import io
    from rdkit.Chem import AllChem

    out = io.StringIO()
    writer = Chem.SDWriter(out)

    for c in compounds:
        smiles = c.get("smiles", "")
        if not smiles:
            continue
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue

        # Set compound name as molecule title
        name = c.get("name", "Unnamed")
        mol.SetProp("_Name", name)

        # Compute 2D coordinates so standard SDF viewers don't break
        try:
            AllChem.Compute2DCoords(mol)
        except Exception:
            pass

        # Set SDF property tags
        tags = {
            "SMILES": smiles,
            "MW": c.get("mol_weight"),
            "LogP": c.get("logp"),
            "TPSA": c.get("tpsa"),
            "HBD": c.get("hbd"),
            "HBA": c.get("hba"),
            "RotBonds": c.get("rotatable_bonds"),
            "MPO_Score": c.get("score"),
            "Rank": c.get("rank"),
            "Pesticide_Likeness": c.get("pesticide_likeness"),
            "Selectivity_Level": c.get("selectivity_level"),
            "Resistance_Level": c.get("resistance_level"),
            "Toxicity_Level": c.get("toxicity_level"),
        }

        for k, v in tags.items():
            if v is not None:
                mol.SetProp(k, str(v))

        writer.write(mol)

    writer.close()
    return out.getvalue()
