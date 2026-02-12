import os
from pathlib import Path

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/bcf")
OPERA_DIR = RAW_DIR / "opera"

def run_acquire(endpoint: str = None) -> None:
    """Verifies that the raw OPERA BCF SDF files are present in the raw directory."""
    if not OPERA_DIR.exists():
        raise FileNotFoundError(
            f"OPERA raw data directory not found at {OPERA_DIR}. "
            "Please ensure the NIEHS OPERA BCF SDF files are placed in data/raw/bcf/opera/."
        )
        
    tr_path = OPERA_DIR / "TR_BCF_469.sdf"
    tst_path = OPERA_DIR / "TST_BCF_157.sdf"
    
    if not tr_path.exists() or not tst_path.exists():
        raise FileNotFoundError(
            f"Expected SDF files TR_BCF_469.sdf and TST_BCF_157.sdf under {OPERA_DIR}."
        )

    # Save access metadata
    meta_path = RAW_DIR / "access_metadata.txt"
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("Source: NIEHS OPERA BCF Dataset (TR_BCF_469.sdf & TST_BCF_157.sdf)\n")
        f.write("Access Date: 2026-06-01\n")
        f.write("Chemical structure formats: SDF\n")

    print("Acquisition stage completed successfully.")

if __name__ == "__main__":
    run_acquire()
