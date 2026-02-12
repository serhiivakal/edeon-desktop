import sys, platform, hashlib, json, datetime

def collect_provenance(config: dict, smiles: list[str], activities: list[float]) -> dict:
    import rdkit, sklearn, numpy
    payload = {
        "schema_version": 1,
        "trained_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "library_versions": {
            "rdkit": rdkit.__version__,
            "sklearn": sklearn.__version__,
            "numpy": numpy.__version__,
        },
        "config": config,                       # full unmodified config dict
        "random_state": config.get("random_state", 42),
        "split_mode": config.get("split_mode", "random"),
        "cv_k": config.get("cv_k", 5),
        "n_scramble": config.get("n_scramble", 10),
        "dataset_hash": _hash_dataset(smiles, activities),
        "n_compounds_input": len(smiles),
    }
    return payload

def _hash_dataset(smiles, activities) -> str:
    items = sorted(zip(smiles, activities), key=lambda p: p[0])
    raw = json.dumps(items, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()
