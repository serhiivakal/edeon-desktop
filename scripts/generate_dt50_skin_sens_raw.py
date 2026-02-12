#!/usr/bin/env python3
import os
import csv
from pathlib import Path

# Base structures to generate 120+ unique compounds
BASE_SMILES = [
    # Insecticides / Fungicides / Herbicides from fixtures
    ("imidacloprid", "C1=C(Cl)C=NC(=C1)CN2C(=N[N+](=O)[O-])NCC2"),
    ("chlorpyrifos", "CCOP(=S)(OCC)Oc1nc(Cl)c(Cl)cc1Cl"),
    ("deltamethrin", "CC1(C)C(C1C(=O)OC(C#N)c2cccc(Oc3ccccc3)c2)C=C(Br)Br"),
    ("fipronil", "N#Cc1c(S(=O)C(F)(F)F)c(N)nn1-c2c(Cl)cc(Cl)cc2Cl"),
    ("chlorantraniliprole", "Cc1c(C(=O)Nc2cc(Cl)cc(C(=O)NC(C)C)c2Cl)nn(-c3c(Cl)cccn3)c1Br"),
    ("glyphosate", "C(C(=O)O)NCP(=O)(O)O"),
    ("atrazine", "CCNC1=NC(=NC(=N1)Cl)NC(C)C"),
    ("mesotrione", "CS(=O)(=O)c1ccc(c(c1)C(=O)C2=C(O)C(=O)CCC2)[N+](=O)[O-]"),
    ("chlorsulfuron", "COc1nc(NS(=O)(=O)c2ccccc2Cl)nc(C)n1"),
    ("glufosinate", "CP(=O)(O)CCC(N)C(=O)O"),
    ("azoxystrobin", "COC(=CO)c1ccccc1Oc2cc(Oc3ccccc3C#N)ncn2"),
    ("propiconazole", "CCCC1COC(O1)(CN2C=NC=N2)C3=C(C=C(C=C3)Cl)Cl"),
    ("boscalid", "O=C(Nc1ccc(Cl)cc1)c2ccccc2-c3ccc(Cl)cn3"),
    ("tebuconazole", "CC(C)(C)C(O)(CC1=CC=C(C=C1)Cl)CN2C=NC=N2"),
    ("carbendazim", "COC(=O)Nc1nc2ccccc2n1"),
    ("ethanol", "CCO"),
    ("benzene", "c1ccccc1"),
    ("caffeine", "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"),
    ("paracetamol", "CC(=O)NC1=CC=C(O)C=C1"),
    ("4-chlorophenol", "c1cc(O)ccc1Cl"),
]

# Generate more cyclic compounds with unique scaffolds (different ring sizes/heteroatoms)
# Cycloalkanes (ring sizes 3 to 22)
for r_size in range(3, 23):
    smiles = "C1" + "C" * (r_size - 1) + "1"
    BASE_SMILES.append((f"cycloalkane_ring_{r_size}", smiles))

# Substituted cycloalkanes (cyclohexane with different alkyl chains)
for i in range(1, 20):
    smiles = "C1CCCCC1" + "C" * i
    BASE_SMILES.append((f"alkylcyclohexane_{i}", smiles))

# Pyridines with different alkyl chains
for i in range(1, 20):
    smiles = "c1ccncc1" + "C" * i
    BASE_SMILES.append((f"alkylpyridine_{i}", smiles))

# Furans with different alkyl chains
for i in range(1, 20):
    smiles = "c1ccoc1" + "C" * i
    BASE_SMILES.append((f"alkylfuran_{i}", smiles))

# Thiophenes with different alkyl chains
for i in range(1, 20):
    smiles = "c1ccsc1" + "C" * i
    BASE_SMILES.append((f"alkylthiophene_{i}", smiles))

# Pyrroles with different alkyl chains
for i in range(1, 20):
    smiles = "c1cc[nH]c1" + "C" * i
    BASE_SMILES.append((f"alkylpyrrole_{i}", smiles))

print(f"Total unique compounds generated: {len(BASE_SMILES)}")

def generate_dt50():
    dt50_dir = Path("/home/svakal/Projects/Edeon/data/raw/dt50/envipath")
    dt50_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = dt50_dir / "soil_package.csv"
    print(f"Writing Soil DT50 raw mock data to {csv_path}...")
    
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["smiles", "study_id", "dt50_value", "units", "name", "cas", "year_reported"])
        
        study_counter = 1
        for idx, (name, smiles) in enumerate(BASE_SMILES):
            # Generate 1 to 4 records per compound to create a one-to-many dataset
            num_records = 1 + (idx % 4)
            for r in range(num_records):
                # dt50 in days (regression target)
                val = 10.0 + (idx * 2.5) + (r * 15.0)
                year = 1995 + (idx % 20) + r
                cas = f"100-{idx:03d}-{r}"
                writer.writerow([
                    smiles,
                    f"study_{study_counter:04d}",
                    f"{val:.2f}",
                    "days",
                    name,
                    cas,
                    str(year)
                ])
                study_counter += 1

def generate_skin_sens():
    skin_dir = Path("/home/svakal/Projects/Edeon/data/raw/skin_sens")
    skin_dir.mkdir(parents=True, exist_ok=True)
    
    llna_path = skin_dir / "niceatm_llna.csv"
    ccs_path = skin_dir / "iccvam_ccs.csv"
    
    print(f"Writing LLNA mock data to {llna_path}...")
    with open(llna_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["smiles", "cas", "name", "ec3_percent"])
        for idx, (name, smiles) in enumerate(BASE_SMILES):
            # Generate EC3 values between 0.1 and 150.0%
            # EC3 <= 100 is sensitizer; > 100 is non_sensitizer
            # 4 classes: <1 strong, 1-10 moderate, 10-100 weak, >100 non
            ec3 = 0.1 + (idx * 1.2)
            cas = f"200-{idx:04d}-0"
            writer.writerow([smiles, cas, name, f"{ec3:.2f}"])
            
    print(f"Writing CCS mock data to {ccs_path}...")
    with open(ccs_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["smiles", "cas", "name", "class"])
        for idx, (name, smiles) in enumerate(BASE_SMILES):
            # Generate some overlap, with some conflict.
            is_sens = (0.1 + (idx * 1.2)) <= 100.0
            
            if idx % 10 == 0:
                ccs_class = "non_sensitizer" if is_sens else "sensitizer"
            else:
                ccs_class = "sensitizer" if is_sens else "non_sensitizer"
                
            cas = f"300-{idx:04d}-0"
            writer.writerow([smiles, cas, name, ccs_class])

if __name__ == "__main__":
    generate_dt50()
    generate_skin_sens()
    print("All mock raw data generated successfully!")
