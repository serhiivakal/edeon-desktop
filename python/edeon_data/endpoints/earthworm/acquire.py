import os
from pathlib import Path

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/earthworm")

def run_acquire(endpoint: str = None) -> None:
    """Verifies that the raw Earthworm QsarDB dataset zip file is present in the raw directory."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    zip_path = RAW_DIR / "final_arch_exp.zip"
    pore_path = RAW_DIR / "pore_2024.xlsx"
    
    # We require the QsarDB archive as it represents the main dataset
    if not zip_path.exists():
        raise FileNotFoundError(
            f"Earthworm raw data archive not found at {zip_path}.\n"
            "Please download the QsarDB archive 'final_arch_exp.zip' manually from:\n"
            "  https://qsardb.org/repository/handle/10967/258\n"
            "and place it at 'data/raw/earthworm/final_arch_exp.zip'."
        )
        
    print(f"Verified raw QsarDB archive file at: {zip_path}")
    if pore_path.exists():
        print(f"Verified optional Pore et al. supplementary file at: {pore_path}")
        
    # Save access metadata
    meta_path = RAW_DIR / "access_metadata.txt"
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("Source: QsarDB Repository (QDB.258) for Kotli et al. 2024 (J. Hazard. Mater. 461:132577)\n")
        f.write("DOI: 10.15152/QDB.258\n")
        f.write("Access Date: 2026-06-02\n")
        f.write("Chemical structure format: Daylight SMILES inside Zip archive\n")
        if pore_path.exists():
            f.write("Additional Source: Pore et al. 2024 (J. Hazard. Mater. 479:135725) Supplementary Excel\n")
            f.write("Additional DOI: 10.1016/j.jhazmat.2024.135725\n")
            
    print("Acquisition stage completed successfully.")

if __name__ == "__main__":
    run_acquire()
