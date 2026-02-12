"""Dataset manifest construction."""
from pathlib import Path
from typing import Dict, Any
from edeon_data.shared.io import get_file_sha256

def construct_manifest(bundle_dir: Path) -> Dict[str, Any]:
    """Calculates sizes and hashes of all files in bundle_dir and returns metadata."""
    bundle_dir = Path(bundle_dir)
    files_metadata = {}
    
    for p in sorted(bundle_dir.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel_path = p.relative_to(bundle_dir).as_posix()
            size = p.stat().st_size
            sha256 = get_file_sha256(p)
            files_metadata[rel_path] = {
                "size_bytes": size,
                "sha256": sha256
            }
            
    return {
        "generator": "edeon-data-pipeline",
        "files": files_metadata
    }
