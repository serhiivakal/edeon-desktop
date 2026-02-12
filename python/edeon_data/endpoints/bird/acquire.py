import os
import shutil
import urllib.request
from pathlib import Path

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/bird")
WORKSPACE_DIR = Path("/home/svakal/Projects/Edeon")

def run_acquire(endpoint: str = None) -> None:
    """Acquires EFSA OpenFoodTox spreadsheets and verifies ECOTOX database for Bird acute oral LD50."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Download OpenFoodTox files from Zenodo
    files_to_download = {
        "ReferencePoints_KJ_2023.xlsx": "https://zenodo.org/api/records/8120114/files/ReferencePoints_KJ_2023.xlsx/content",
        "SubstanceCharacterisation_KJ_2023.xlsx": "https://zenodo.org/api/records/8120114/files/SubstanceCharacterisation_KJ_2023.xlsx/content"
    }
    
    for filename, url in files_to_download.items():
        target_path = RAW_DIR / filename
        
        # Check if already present in raw folder
        if target_path.exists():
            print(f"{filename} already exists in raw directory.")
            continue
            
        # Fallback 1: check if in workspace root (already downloaded via manual curl)
        workspace_fallback = WORKSPACE_DIR / filename
        if workspace_fallback.exists():
            print(f"Copying {filename} from workspace root fallback...")
            shutil.copy(workspace_fallback, target_path)
            continue
            
        # Programmatic download
        print(f"Downloading {filename} from Zenodo...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                with open(target_path, "wb") as f:
                    f.write(response.read())
            print(f"Downloaded {filename} successfully.")
        except Exception as e:
            print(f"Failed to download {filename} from Zenodo: {e}")
            if not target_path.exists():
                raise FileNotFoundError(
                    f"Could not acquire {filename}. Please place it manually in {RAW_DIR} or in the workspace root."
                )

    # 2. Check ECOTOX ASCII directory
    ecotox_dir = WORKSPACE_DIR / "data/raw/fish/ecotox_ascii_03_12_2026"
    if not ecotox_dir.exists():
        raise FileNotFoundError(
            f"Expected ECOTOX ASCII directory at {ecotox_dir}. "
            "Please ensure the ASCII directory is placed in raw/fish."
        )

    # Save access metadata
    meta_path = RAW_DIR / "access_metadata.txt"
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("Source: EFSA OpenFoodTox (Zenodo release 8120114) & EPA ECOTOX ASCII Bulk Export (03/12/2026)\n")
        f.write("Access Date: 2026-05-31\n")
        f.write("Species targeted: Anas platyrhynchos, Colinus virginianus, Coturnix japonica, Phasianus colchicus, Passer domesticus\n")

    print("Acquisition stage completed successfully.")

if __name__ == "__main__":
    run_acquire()
