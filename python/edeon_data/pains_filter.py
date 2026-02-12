"""
Edeon Engine — PAINS and Toxicophore Filtering
Uses RDKit FilterCatalog to detect pan-assay interference and reactive alerts.
"""

from rdkit import Chem
from rdkit.Chem import FilterCatalog

# Initialize filter catalogs
_pains_params = FilterCatalog.FilterCatalogParams()
_pains_params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS_A)
_pains_params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS_B)
_pains_params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS_C)
_pains_catalog = FilterCatalog.FilterCatalog(_pains_params)

_reactive_params = FilterCatalog.FilterCatalogParams()
_reactive_params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.BRENK)
_reactive_params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.NIH)
_reactive_catalog = FilterCatalog.FilterCatalog(_reactive_params)


def check_molecule_alerts(smiles: str) -> dict:
    """
    Check if a molecule violates PAINS or reactive/toxicophore alert libraries.
    Returns a dictionary of results.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"valid": False, "pains": False, "reactive": False, "matches": []}

    pains_matches = []
    reactive_matches = []

    # Get details for PAINS matches
    pains_entries = _pains_catalog.GetMatches(mol)
    for entry in pains_entries:
        pains_matches.append(entry.GetDescription())

    # Get details for Reactive/NIH/BRENK matches
    reactive_entries = _reactive_catalog.GetMatches(mol)
    for entry in reactive_entries:
        reactive_matches.append(entry.GetDescription())

    return {
        "valid": True,
        "pains": len(pains_matches) > 0,
        "reactive": len(reactive_matches) > 0,
        "pains_alerts": list(set(pains_matches)),
        "reactive_alerts": list(set(reactive_matches)),
    }


def filter_pains_batch(smiles_list: list[str], num_workers: int = 1) -> list[dict]:
    """Filter a batch of SMILES strings for PAINS and reactive alerts."""
    if num_workers <= 1 or len(smiles_list) < 5:
        return [check_molecule_alerts(s) for s in smiles_list]
    from joblib import Parallel, delayed
    return Parallel(n_jobs=num_workers, prefer="threads")(
        delayed(check_molecule_alerts)(s) for s in smiles_list
    )
