import json
import hashlib
import yaml
from pathlib import Path
import pandas as pd
from typing import List, Dict, Any
from edeon_data.schema import DataCard

CANONICAL_COLUMNS = [
    "inchikey",
    "smiles_canonical",
    "smiles_original",
    "cas",
    "name",
    "chembl_id",
    "endpoint",
    "value",
    "value_units",
    "value_log",
    "value_class",
    "species",
    "species_taxonomy",
    "test_type",
    "exposure_route",
    "exposure_duration_h",
    "effect",
    "source",
    "source_ref",
    "source_record_id",
    "year_reported",
    "aggregation_n",
    "aggregation_method",
    "aggregation_cv",
    "quality_flags"
]

def enforce_parquet_types(df: pd.DataFrame) -> pd.DataFrame:
    """Enforces official schema types on the DataFrame before storage."""
    df_copy = df.copy()
    
    # Ensure all canonical columns exist (use None if missing)
    for col in CANONICAL_COLUMNS:
        if col not in df_copy.columns:
            df_copy[col] = None
            
    # Keep only canonical columns in canonical order, plus any endpoint-specific extensions (placed at the end)
    extra_cols = [c for c in df_copy.columns if c not in CANONICAL_COLUMNS]
    ordered_cols = CANONICAL_COLUMNS + extra_cols
    df_copy = df_copy[ordered_cols]
    
    # String columns
    str_cols = [
        "inchikey", "smiles_canonical", "smiles_original", "cas", "name", 
        "chembl_id", "endpoint", "value_units", "value_class", "species", 
        "species_taxonomy", "test_type", "exposure_route", "effect", 
        "source", "source_ref", "source_record_id", "aggregation_method"
    ]
    for col in str_cols:
        if col in df_copy.columns:
            # Safe conversion to nullable string
            df_copy[col] = df_copy[col].apply(lambda x: str(x) if pd.notna(x) and x is not None else None)
            
    # Float64 columns
    float_cols = ["value", "value_log", "aggregation_cv", "exposure_duration_h"]
    for col in float_cols:
        if col in df_copy.columns:
            df_copy[col] = pd.to_numeric(df_copy[col], errors="coerce").astype("float64")
            
    # Int32 columns (nullable)
    int_cols = ["aggregation_n", "year_reported"]
    for col in int_cols:
        if col in df_copy.columns:
            df_copy[col] = pd.to_numeric(df_copy[col], errors="coerce").astype("Int32")
            
    # List<string> for quality_flags
    if "quality_flags" in df_copy.columns:
        def clean_flags(x):
            if isinstance(x, list):
                return [str(i) for i in x]
            elif isinstance(x, str):
                return [i.strip() for i in x.split(",") if i.strip()]
            else:
                return []
        df_copy["quality_flags"] = df_copy["quality_flags"].apply(clean_flags)
        
    return df_copy


def get_file_sha256(path: Path) -> str:
    """Calculates SHA-256 hash of a file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_parquet_with_hash(df: pd.DataFrame, path: Path) -> str:
    """Writes a DataFrame to Parquet, enforces official types, and returns the file's SHA-256 hash."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    df_clean = enforce_parquet_types(df)
    df_clean.to_parquet(path, index=False)
    
    return get_file_sha256(path)


def write_csv_mirror(df: pd.DataFrame, path: Path) -> None:
    """Writes a CSV mirror of the DataFrame with stable column ordering."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    df_clean = enforce_parquet_types(df)
    # Convert lists in quality_flags to comma-separated strings for CSV readability
    df_csv = df_clean.copy()
    if "quality_flags" in df_csv.columns:
        df_csv["quality_flags"] = df_csv["quality_flags"].apply(
            lambda x: ",".join(x) if isinstance(x, list) else ""
        )
        
    df_csv.to_csv(path, index=False)


def write_data_card(card: DataCard, path: Path) -> None:
    """Writes a YAML data card with stable key ordering."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Dump using safe_dump with stable ordering from the model dict representation
    card_dict = card.model_dump(exclude_none=False)
    
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(card_dict, f, default_flow_style=False, sort_keys=False)


def write_curation_log(entries: List[Dict[str, Any]], path: Path) -> None:
    """Writes structured JSON log of all curation events."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def write_manifest(bundle_dir: Path) -> None:
    """
    Walks the bundle_dir directory, calculates sizes and hashes of all files,
    and writes manifest.json in bundle_dir.
    """
    bundle_dir = Path(bundle_dir)
    manifest_path = bundle_dir / "manifest.json"
    
    files_metadata = {}
    
    # We list files in bundle_dir
    for p in sorted(bundle_dir.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel_path = p.relative_to(bundle_dir).as_posix()
            size = p.stat().st_size
            sha256 = get_file_sha256(p)
            files_metadata[rel_path] = {
                "size_bytes": size,
                "sha256": sha256
            }
            
    manifest_data = {
        "generator": "edeon-data-pipeline",
        "files": files_metadata
    }
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
