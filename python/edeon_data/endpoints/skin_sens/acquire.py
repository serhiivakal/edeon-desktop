import os
from pathlib import Path

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/skin_sens")

def run_acquire(endpoint: str = None) -> None:
    """Verifies that the raw Skin Sensitization LLNA and CCS datasets are present in the raw directory."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    llna_path = RAW_DIR / "niceatm_llna.csv"
    ccs_path = RAW_DIR / "iccvam_ccs.csv"
    
    if not llna_path.exists() or not ccs_path.exists():
        raise FileNotFoundError(
            f"Skin Sensitization raw data files not found.\n"
            f"Please place 'niceatm_llna.csv' and 'iccvam_ccs.csv' manually in:\n"
            f"  {RAW_DIR}"
        )
        
    print(f"Verified raw NICEATM LLNA dataset at: {llna_path}")
    print(f"Verified raw ICCVAM CCS dataset at: {ccs_path}")
    
    # Save access metadata
    meta_path = RAW_DIR / "access_metadata.txt"
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("Source 1: NICEATM LLNA dataset (niceatm_llna.csv)\n")
        f.write("Source 2: ICCVAM CCS dataset (iccvam_ccs.csv)\n")
        f.write("Access Date: 2026-06-02\n")
        f.write("Chemical structure format: SMILES\n")
        
    print("Acquisition stage completed successfully for Skin Sensitization.")

if __name__ == "__main__":
    run_acquire()
