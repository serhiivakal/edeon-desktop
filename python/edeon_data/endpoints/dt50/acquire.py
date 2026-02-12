import os
from pathlib import Path

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/dt50")

def run_acquire(endpoint: str = None) -> None:
    """Verifies that the raw Soil DT50 EAWAG-SOIL dataset is present in the raw directory."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    csv_path = RAW_DIR / "envipath" / "soil_package.csv"
    
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Soil DT50 raw data file not found at {csv_path}.\n"
            "Please ensure the enviPath Soil package export CSV is placed manually at:\n"
            "  data/raw/dt50/envipath/soil_package.csv"
        )
        
    print(f"Verified raw Soil DT50 data file at: {csv_path}")
    
    # Save access metadata
    meta_path = RAW_DIR / "access_metadata.txt"
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("Source: EAWAG-SOIL database via enviPath (https://envipath.org/)\n")
        f.write("Dataset: Soil package export\n")
        f.write("Access Date: 2026-06-02\n")
        f.write("Chemical structure format: SMILES\n")
        
    print("Acquisition stage completed successfully for Soil DT50.")

if __name__ == "__main__":
    run_acquire()
