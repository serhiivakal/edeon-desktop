import sqlite3
import os
import sys

# Add python directory to sys.path so we can import edeon_engine modules if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# We can import standardization and property calculators to compute descriptor values for reference actives
from edeon_engine.standardize import standardize_batch
from edeon_engine.properties import compute_properties_batch

def build_db():
    db_path = os.path.join(os.path.dirname(__file__), "reference_actives.sqlite")
    print(f"Building reference database at: {db_path}")

    # Remove existing db to rebuild clean
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS actives (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        cas TEXT,
        smiles TEXT NOT NULL,
        use_class TEXT NOT NULL,
        moa_group TEXT NOT NULL,
        approval_status TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_values (
        active_id TEXT NOT NULL REFERENCES actives(id) ON DELETE CASCADE,
        axis TEXT NOT NULL,
        value REAL,
        unit TEXT,
        source_type TEXT NOT NULL, -- 'measured' | 'predicted'
        source_ref TEXT,
        PRIMARY KEY (active_id, axis)
    );
    """)

    # Standard reference active ingredients definitions
    reference_actives = [
        {
            "id": "glyphosate",
            "name": "Glyphosate",
            "cas": "1071-83-6",
            "smiles": "C(C(=O)O)NCP(=O)(O)O",
            "use_class": "Herbicide",
            "moa_group": "EPSPS inhibitors",
            "approval_status": "Approved",
            "measured": {
                "logp": -3.2,
                "soil_dt50": 12.0,
                "soil_koc": 24000.0,
                "bee_oral_ld50": 100.0,
                "bee_contact_ld50": 100.0,
                "fish_lc50": 86.0,
                "daphnia_ec50": 55.0,
            }
        },
        {
            "id": "imidacloprid",
            "name": "Imidacloprid",
            "cas": "138261-41-3",
            "smiles": "C1CN(C(=N[N+](=O)[O-])N1)CC2=CN=C(C=C2)Cl",
            "use_class": "Insecticide",
            "moa_group": "Neonicotinoids",
            "approval_status": "Restricted",
            "measured": {
                "logp": 0.57,
                "soil_dt50": 174.0,
                "soil_koc": 247.0,
                "bee_oral_ld50": 0.0037, # highly toxic!
                "bee_contact_ld50": 0.081,
                "fish_lc50": 211.0,
                "daphnia_ec50": 85.0,
            }
        },
        {
            "id": "atrazine",
            "name": "Atrazine",
            "cas": "1912-24-9",
            "smiles": "CCNC1=NC(=NC(=N1)Cl)NC(C)C",
            "use_class": "Herbicide",
            "moa_group": "Photosystem II inhibitors",
            "approval_status": "Not Approved",
            "measured": {
                "logp": 2.5,
                "soil_dt50": 75.0,
                "soil_koc": 100.0,
                "bee_oral_ld50": 97.0,
                "bee_contact_ld50": 100.0,
                "fish_lc50": 4.5,
                "daphnia_ec50": 6.9,
            }
        },
        {
            "id": "chlorpyrifos",
            "name": "Chlorpyrifos",
            "cas": "2921-88-2",
            "smiles": "CCOP(=S)(OCC)OC1=NC(=C(C(=C1Cl)Cl)Cl)Cl",
            "use_class": "Insecticide",
            "moa_group": "Organophosphates",
            "approval_status": "Not Approved",
            "measured": {
                "logp": 4.7,
                "soil_dt50": 30.0,
                "soil_koc": 8500.0,
                "bee_oral_ld50": 0.36,
                "bee_contact_ld50": 0.1,
                "fish_lc50": 0.003, # very highly toxic to aquatic life!
                "daphnia_ec50": 0.0001,
            }
        },
        {
            "id": "azoxystrobin",
            "name": "Azoxystrobin",
            "cas": "131860-33-8",
            "smiles": "COC(=C\\C(=O)OC)/c1ccccc1Oc2cc(oc2Oc3ccc(cc3)C#N)n",
            "use_class": "Fungicide",
            "moa_group": "Strobilurins",
            "approval_status": "Approved",
            "measured": {
                "logp": 2.5,
                "soil_dt50": 78.0,
                "soil_koc": 430.0,
                "bee_oral_ld50": 25.0,
                "bee_contact_ld50": 200.0,
                "fish_lc50": 0.47,
                "daphnia_ec50": 0.28,
            }
        },
        {
            "id": "tebuconazole",
            "name": "Tebuconazole",
            "cas": "107534-96-3",
            "smiles": "CC(C)(C)C(O)(CN1CN=CN=1)CCC1=CC=C(Cl)C=C1",
            "use_class": "Fungicide",
            "moa_group": "Triazoles",
            "approval_status": "Approved",
            "measured": {
                "logp": 3.7,
                "soil_dt50": 365.0, # highly persistent!
                "soil_koc": 1251.0,
                "bee_oral_ld50": 83.0,
                "bee_contact_ld50": 200.0,
                "fish_lc50": 4.4,
                "daphnia_ec50": 2.79,
            }
        }
    ]

    for item in reference_actives:
        # Standardize smiles and extract chemical properties using local Edeon engine to fill molecular descriptors
        std_res = standardize_batch([item["smiles"]])[0]
        canonical_smiles = std_res["canonical"] if std_res["valid"] else item["smiles"]
        
        cursor.execute("""
        INSERT INTO actives (id, name, cas, smiles, use_class, moa_group, approval_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            item["id"],
            item["name"],
            item["cas"],
            canonical_smiles,
            item["use_class"],
            item["moa_group"],
            item["approval_status"]
        ))

        # Compute dynamic molecular properties (MW, TPSA, HBD, HBA) using compute_properties_batch
        props_res = compute_properties_batch([canonical_smiles])[0]
        
        # Save structural attributes
        for k in ["mol_weight", "tpsa", "hbd", "hba", "rotatable_bonds"]:
            if k in props_res and props_res[k] is not None:
                cursor.execute("""
                INSERT INTO active_values (active_id, axis, value, unit, source_type, source_ref)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (item["id"], k, float(props_res[k]), "", "predicted", "edeon_engine_v1.0"))

        # Save measured values
        for axis, val in item["measured"].items():
            unit = "mg/L" if "lc50" in axis or "ec50" in axis else "days" if "dt50" in axis else "ug/bee" if "ld50" in axis else ""
            cursor.execute("""
            INSERT INTO active_values (active_id, axis, value, unit, source_type, source_ref)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (item["id"], axis, float(val), unit, "measured", "PPDB / EPA Agrochemical Databases"))

    conn.commit()
    conn.close()
    print("Database built successfully!")

if __name__ == "__main__":
    build_db()
