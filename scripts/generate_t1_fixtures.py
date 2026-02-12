"""Generate Tier-1 regression test fixtures and MANIFEST.json for the checkpoint integrity check.

Run from the project root:
    cd /home/svakal/Projects/Edeon
    PYTHONPATH=python python scripts/generate_t1_fixtures.py
"""

import os
import sys
import json
import hashlib
import csv
from pathlib import Path
from datetime import datetime, timezone

# Add python/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

CHECKPOINTS_ROOT = Path("data/checkpoints")
FIXTURES_DIR = Path("tests/regression/fixtures/tier1")

# Reference compounds for regression testing (well-known agrochemicals)
REFERENCE_SMILES = [
    ("imidacloprid", "C1=C(Cl)C=NC(=C1)CN2C(=N[N+](=O)[O-])NCC2"),
    ("glyphosate", "OC(=O)CNCP(O)(O)=O"),
    ("atrazine", "CCNc1nc(Cl)nc(NC(C)C)n1"),
    ("chlorpyrifos", "CCOP(=S)(OCC)Oc1nc(Cl)c(Cl)cc1Cl"),
    ("azoxystrobin", "CO/C=C(/C(=O)OC)c1ccccc1Oc1cc(Oc2ccccc2C#N)ncn1"),
    ("cypermethrin", "CC1(C)C(C=C(Cl)Cl)C1C(=O)OC(C#N)c1cccc(Oc2ccccc2)c1"),
    ("carbendazim", "COC(=O)Nc1[nH]c2ccccc2n1"),
    ("malathion", "CCOC(=O)CC(SP(=S)(OC)OC)C(=O)OCC"),
    ("diuron", "CN(C)C(=O)Nc1ccc(Cl)c(Cl)c1"),
    ("2,4-D", "OC(=O)COc1ccc(Cl)cc1Cl"),
    ("thiamethoxam", "CN1COCN(Cc2cnc(Cl)s2)/C1=N/[N+]([O-])=O"),
    ("acetamiprid", "CC(=N/C#N)/NCc1ccc(Cl)nc1"),
    ("propiconazole", "CCCC1COC(Cn2cncn2)(O1)c1ccc(Cl)cc1Cl"),
    ("fipronil", "N#Cc1nn(-c2c(Cl)cc(C(F)(F)F)cc2Cl)c(N)c1S(=O)C(F)(F)F"),
    ("dimethoate", "CNC(=O)CSP(=S)(OC)OC"),
    ("paraquat", "C[n+]1ccc(-c2cc[n+](C)cc2)cc1"),
    ("metribuzin", "CSc1nnc2c(n1)c(=O)n(C)n2C"),
    ("pendimethalin", "CCC(CC)Nc1c([N+](=O)[O-])cc(C)c(C)c1[N+](=O)[O-]"),
    ("mancozeb", "[Mn++].[S-]C(=S)NCCNC(=S)[S-]"),
    ("fenvalerate", "CC(C)C(=O)OC(C#N)c1cccc(Oc2ccccc2)c1"),
]


def sha256sum(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(128 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest():
    """Generate MANIFEST.json for all checkpoint endpoints."""
    manifest = {}
    
    for ep_dir in sorted(CHECKPOINTS_ROOT.iterdir()):
        if not ep_dir.is_dir():
            continue
        endpoint = ep_dir.name
        
        # Prefer v1.0_cls if it exists, otherwise fall back to v1.0
        v_dir = ep_dir / "v1.0_cls"
        version_str = "v1.0_cls"
        if not v_dir.exists():
            v_dir = ep_dir / "v1.0"
            version_str = "v1.0"
            
        if not v_dir.exists():
            continue
            
        artifacts = {}
        for root, dirs, files in os.walk(v_dir):
            # Skip __pycache__ and hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for f in files:
                if f.startswith(".") or f.endswith(".pyc"):
                    continue
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, CHECKPOINTS_ROOT)
                artifacts[rel_path] = sha256sum(full_path)
        
        # Calculate total size
        total_size = sum(
            os.path.getsize(os.path.join(root, f))
            for root, _, files in os.walk(v_dir)
            for f in files if not f.startswith(".")
        )
        
        manifest[endpoint] = {
            "version": version_str,
            "total_size_bytes": total_size,
            "artifact_count": len(artifacts),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": artifacts,
        }
        
    manifest_path = CHECKPOINTS_ROOT / "MANIFEST.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    
    print(f"Generated MANIFEST.json with {len(manifest)} endpoints at {manifest_path}")
    return manifest


def generate_fixtures():
    """Generate regression test fixture CSVs for each trained endpoint."""
    try:
        from edeon_models import build_default_registry
        from edeon_models.endpoints import Endpoint
    except ImportError:
        print("WARNING: Cannot import edeon_models — skipping fixture generation.")
        print("Run with PYTHONPATH=python to enable.")
        return
    
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    
    registry = build_default_registry()
    
    for endpoint in Endpoint:
        try:
            backend = registry.get(endpoint)
        except Exception:
            print(f"  Skipping {endpoint.value} — no backend available")
            continue
        
        if backend.tier() != 1:
            print(f"  Skipping {endpoint.value} — not Tier-1 (tier={backend.tier()})")
            continue
        
        print(f"  Generating fixture for {endpoint.value}...")
        
        # Use the reference compounds
        smiles_list = [s for _, s in REFERENCE_SMILES]
        
        try:
            predictions = backend.predict(smiles_list)
        except Exception as e:
            print(f"    ERROR predicting: {e}")
            continue
        
        fixture_path = FIXTURES_DIR / f"{endpoint.value}_v1.csv"
        with open(fixture_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "endpoint", "name", "smiles", "expected_value",
                "expected_value_lower", "expected_value_upper",
                "expected_ad_status"
            ])
            
            for (name, smiles), pred in zip(REFERENCE_SMILES, predictions):
                if pred.value and pred.value.kind == "binary":
                    # Convert binary prediction to 1.0 (toxic) or 0.0 (nontoxic) for easy float handling in tests
                    value = 1.0 if pred.value.binary else 0.0
                else:
                    value = pred.value.numeric if pred.value and pred.value.numeric is not None else float("nan")
                    
                ci_lower = pred.ci_lower if pred.ci_lower is not None else ""
                ci_upper = pred.ci_upper if pred.ci_upper is not None else ""
                ad_status = pred.ad_status.value if pred.ad_status else ""
                
                writer.writerow([
                    endpoint.value, name, smiles, value,
                    ci_lower, ci_upper, ad_status
                ])
        
        print(f"    Written {len(predictions)} predictions to {fixture_path}")
    
    print(f"\nFixtures generated in {FIXTURES_DIR}")


if __name__ == "__main__":
    print("=== Generating MANIFEST.json ===")
    generate_manifest()
    
    print("\n=== Generating T1 Regression Fixtures ===")
    generate_fixtures()
    
    print("\nDone.")
