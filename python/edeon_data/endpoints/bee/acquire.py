import urllib.request
import os
from pathlib import Path

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/bee")

FILES_TO_DOWNLOAD = [
    "dataset_final.csv",
    "ecotox.csv",
    "time_train.csv",
    "time_test.csv"
]

def run_acquire(endpoint: str = None) -> None:
    """Downloads all raw files from the ApisTox Zenodo repository."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    for filename in FILES_TO_DOWNLOAD:
        url = f"https://zenodo.org/api/records/13350981/files/{filename}/content"
        dest_path = RAW_DIR / filename
        
        if not dest_path.exists():
            print(f"Downloading raw file '{filename}' for honey bee endpoint...")
            try:
                urllib.request.urlretrieve(url, dest_path)
                print(f"Downloaded '{filename}' successfully.")
            except Exception as e:
                print(f"Error downloading '{filename}': {e}")
                raise e
        else:
            print(f"Raw file '{filename}' already exists.")
            
    # Record access metadata
    meta_path = RAW_DIR / "access_metadata.txt"
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("Source: ApisTox via Zenodo\n")
        f.write("DOI: 10.5281/zenodo.11062076\n")
        f.write("Access Date: 2026-05-30\n")
        f.write("License: CC BY-NC 4.0\n")
        f.write(f"Raw record count: {len(FILES_TO_DOWNLOAD)} files\n")
