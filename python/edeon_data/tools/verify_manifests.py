import sys
import json
from pathlib import Path

from edeon_data.shared.io import get_file_sha256

CURATED_ROOT = Path(__file__).resolve().parents[3] / "data" / "curated"

def verify_manifests() -> int:
    """Verifies that all files listed in MANIFEST.json exist and match their expected size and SHA-256 hash."""
    manifest_path = CURATED_ROOT / "MANIFEST.json"
    if not manifest_path.exists():
        print(f"Error: manifest file not found at {manifest_path}")
        return 1
        
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        print(f"Error parsing manifest JSON: {e}")
        return 1
        
    files = manifest.get("files", {})
    if not files:
        print("Error: No files found in manifest definition.")
        return 1
        
    print(f"Verifying {len(files)} files listed in release manifest...")
    errors_count = 0
    
    for rel_path, meta in files.items():
        file_path = CURATED_ROOT / rel_path
        if not file_path.exists():
            print(f"  [MISSING] {rel_path} - File does not exist on disk!")
            errors_count += 1
            continue
            
        # Verify size
        expected_size = meta.get("size_bytes")
        actual_size = file_path.stat().st_size
        if expected_size != actual_size:
            print(f"  [SIZE CORRUPT] {rel_path} - Expected {expected_size} bytes, got {actual_size} bytes!")
            errors_count += 1
            continue
            
        # Verify hash
        expected_sha = meta.get("sha256")
        actual_sha = get_file_sha256(file_path)
        if expected_sha != actual_sha:
            print(f"  [HASH CORRUPT] {rel_path} - Expected SHA {expected_sha}, got {actual_sha}!")
            errors_count += 1
            continue
            
        # print(f"  [OK] {rel_path}")
        
    if errors_count > 0:
        print(f"\nVerification failed with {errors_count} errors.")
        return 1
        
    print(f"\nManifest verification successful! All {len(files)} files exist, sizes and hashes match.")
    return 0

if __name__ == "__main__":
    sys.exit(verify_manifests())
