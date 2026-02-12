import os
from pathlib import Path

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/rat_ld50")

def run_acquire(endpoint: str = None) -> None:
    """Verifies and registers the manually downloaded NICEATM ICE / CATMoS raw files."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    sdf_path = RAW_DIR / "Supplemental_Material_1" / "TrainingSet.sdf"
    if not sdf_path.exists():
        raise FileNotFoundError(
            f"Expected raw CATMoS TrainingSet.sdf at {sdf_path}. "
            "Please make sure it is unzipped under the Supplemental_Material_1 folder."
        )
        
    print(f"Raw CATMoS file verified at: {sdf_path}")
    
    # Record access metadata
    meta_path = RAW_DIR / "access_metadata.txt"
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("Source: NICEATM ICE / CATMoS via EHP8495 Supplemental Material\n")
        f.write("DOI: 10.1289/EHP8495\n")
        f.write("Access Date: 2026-05-30\n")
        f.write("License: Public Domain (US Gov) / Open Access\n")
        f.write("Raw file: TrainingSet.sdf\n")
        
    print("Acquisition stage completed successfully.")
