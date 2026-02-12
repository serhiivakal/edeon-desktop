#!/usr/bin/env python3
"""Script to generate the reference Tier-1 regression test fixtures after training completes."""

import os
import csv
import sys
import math
from pathlib import Path

# Ensure Edeon packages are on the PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../python")))

from edeon_models import build_default_registry, Endpoint

SMILES_SET = [
    ("imidacloprid", "C1=C(Cl)C=NC(=C1)CN2C(=N[N+](=O)[O-])NCC2", "Insecticide (imidacloprid)"),
    ("chlorpyrifos", "CCOP(=S)(OCC)Oc1nc(Cl)c(Cl)cc1Cl", "Insecticide (chlorpyrifos)"),
    ("deltamethrin", "CC1(C)C(C1C(=O)OC(C#N)c2cccc(Oc3ccccc3)c2)C=C(Br)Br", "Insecticide (deltamethrin)"),
    ("fipronil", "N#Cc1c(S(=O)C(F)(F)F)c(N)nn1-c2c(Cl)cc(Cl)cc2Cl", "Insecticide (fipronil)"),
    ("chlorantraniliprole", "Cc1c(C(=O)Nc2cc(Cl)cc(C(=O)NC(C)C)c2Cl)nn(-c3c(Cl)cccn3)c1Br", "Insecticide (chlorantraniliprole)"),
    ("glyphosate", "C(C(=O)O)NCP(=O)(O)O", "Herbicide (glyphosate)"),
    ("atrazine", "CCNC1=NC(=NC(=N1)Cl)NC(C)C", "Herbicide (atrazine)"),
    ("mesotrione", "CS(=O)(=O)c1ccc(c(c1)C(=O)C2=C(O)C(=O)CCC2)[N+](=O)[O-]", "Herbicide (mesotrione)"),
    ("chlorsulfuron", "COc1nc(NS(=O)(=O)c2ccccc2Cl)nc(C)n1", "Herbicide (chlorsulfuron)"),
    ("glufosinate", "CP(=O)(O)CCC(N)C(=O)O", "Herbicide (glufosinate)"),
    ("azoxystrobin", "COC(=CO)c1ccccc1Oc2cc(Oc3ccccc3C#N)ncn2", "Fungicide (azoxystrobin)"),
    ("propiconazole", "CCCC1COC(O1)(CN2C=NC=N2)C3=C(C=C(C=C3)Cl)Cl", "Fungicide (propiconazole)"),
    ("boscalid", "O=C(Nc1ccc(Cl)cc1)c2ccccc2-c3ccc(Cl)cn3", "Fungicide (boscalid)"),
    ("tebuconazole", "CC(C)(C)C(O)(CC1=CC=C(C=C1)Cl)CN2C=NC=N2", "Fungicide (tebuconazole)"),
    ("carbendazim", "COC(=O)Nc1nc2ccccc2n1", "Fungicide (carbendazim)"),
    ("ethanol", "CCO", "Reference Chem (ethanol)"),
    ("benzene", "c1ccccc1", "Reference Chem (benzene)"),
    ("caffeine", "CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "Reference Chem (caffeine)"),
    ("paracetamol", "CC(=O)NC1=CC=C(O)C=C1", "Reference Chem (paracetamol)"),
    ("4-chlorophenol", "c1cc(O)ccc1Cl", "Reference Chem (4-chlorophenol)"),
]

def main():
    print("Building default Tier-1 registry...")
    reg = build_default_registry()
    
    fixtures_dir = Path(__file__).parent / "tier1"
    fixtures_dir.mkdir(exist_ok=True)
    
    print("Generating Tier-1 predictions for each available endpoint...")
    for endpoint in Endpoint:
        backend = reg.get(endpoint)
        
        # Only generate for Tier-1 backends
        if backend.tier() != 1:
            print(f"Skipping endpoint {endpoint.value}: resolves to Tier-{backend.tier()} (untrained)")
            continue
            
        csv_filename = fixtures_dir / f"{endpoint.value}_v1.csv"
        print(f"Writing Tier-1 reference expected values to {csv_filename}...")
        
        with open(csv_filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                "smiles",
                "endpoint",
                "expected_value",
                "expected_value_lower",
                "expected_value_upper",
                "expected_ad_status",
                "notes",
            ])
            
            for name, smiles, desc in SMILES_SET:
                preds = backend.predict([smiles])
                p = preds[0]
                
                expected_val = str(p.value.numeric) if p.value.kind == "numeric" else ""
                expected_lower = str(p.ci_lower) if p.ci_lower is not None else ""
                expected_upper = str(p.ci_upper) if p.ci_upper is not None else ""
                expected_ad = p.ad_status.value if p.ad_status else ""
                
                notes = f"Tier-1 Reference Model for {name} ({desc})"
                
                writer.writerow([
                    smiles,
                    endpoint.value,
                    expected_val,
                    expected_lower,
                    expected_upper,
                    expected_ad,
                    notes,
                ])
                
    print("Tier-1 regression fixtures generated successfully!")

if __name__ == "__main__":
    main()
