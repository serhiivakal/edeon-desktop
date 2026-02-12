import hashlib
import json
from datetime import datetime

def build_provenance_manifest(workflow_id: str, params: dict, smiles_list: list[str]) -> dict:
    """Builds a reproducibility manifest for the workflow execution."""
    # Hash input
    hasher = hashlib.sha256()
    for smiles in smiles_list:
        hasher.update(str(smiles).encode("utf-8"))
    input_hash = f"sha256:{hasher.hexdigest()}"

    return {
        "edeon_version": "0.1.0",
        "workflow_id": workflow_id,
        "workflow_version": "1.0",
        "params": params,
        "model_ids": {
            "standardize": "v1.0",
            "environmental_fate": "v1.0",
            "pains_filter": "v1.0",
            "selectivity": "v1.0",
            "resistance": "v1.0",
            "toxicity": "v1.0",
            "mpo_score": "v1.0",
            "systemicity": "v1.0"
        },
        "data_versions": {
            "opera": "2.9",
            "ecotox": "2026-03",
            "pains_catalog": "RDKit-2023.09",
            "systemicity_rules": "Briggs/Kleier"
        },
        "run_utc": datetime.utcnow().isoformat() + "Z",
        "input_hash": input_hash
    }
