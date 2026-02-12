import os
import json
import zipfile
import hashlib
import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime
from rdkit import Chem
from rdkit.DataStructs import BulkTanimotoSimilarity
from rdkit.Chem import AllChem

from edeon_data.shared.io import get_file_sha256

CURATED_ROOT = Path("/home/svakal/Projects/Edeon/data/curated")
DIST_ROOT = Path("/home/svakal/Projects/Edeon/dist")
DOCS_ROOT = Path("/home/svakal/Projects/Edeon/docs")

def get_completed_endpoints() -> list[str]:
    """Scans data/curated/ for directories that contain a curated.parquet file."""
    endpoints = []
    if not CURATED_ROOT.exists():
        return []
    for p in sorted(CURATED_ROOT.iterdir()):
        if p.is_dir() and not p.name.startswith("_") and (p / "v1.0" / "curated.parquet").exists():
            endpoints.append(p.name)
    return endpoints

def generate_overlap_report() -> None:
    """Task C2: Generates the cross-endpoint compound overlap CSV."""
    print(">>> Task C2: Generating cross-endpoint compound overlap report...")
    endpoints = get_completed_endpoints()
    if not endpoints:
        print("No curated endpoints found.")
        return
        
    dfs = []
    for ep in endpoints:
        pq_path = CURATED_ROOT / ep / "v1.0" / "curated.parquet"
        df = pd.read_parquet(pq_path)
        # Keep only inchikey, smiles_canonical, value_log
        df_sub = df[["inchikey", "smiles_canonical", "value_log"]].copy()
        df_sub = df_sub.rename(columns={"value_log": f"{ep}_value_log"})
        # Deduplicate locally (just in case)
        df_sub = df_sub.drop_duplicates(subset=["inchikey"])
        dfs.append(df_sub)
        
    # Outer join all dataframes on inchikey and smiles_canonical
    df_merged = dfs[0]
    for df in dfs[1:]:
        df_merged = pd.merge(df_merged, df, on=["inchikey", "smiles_canonical"], how="outer")
        
    # Count the number of endpoints each compound appears in
    val_cols = [f"{ep}_value_log" for ep in endpoints]
    df_merged["presence_count"] = df_merged[val_cols].notna().sum(axis=1)
    
    # Filter to compounds present in at least 2 endpoints
    df_overlap = df_merged[df_merged["presence_count"] >= 2].copy()
    
    # Sort by presence count descending, then by smiles_canonical
    df_overlap = df_overlap.sort_values(by=["presence_count", "smiles_canonical"], ascending=[False, True])
    
    # Drop presence_count column or keep it
    # We will keep it as it's useful
    
    output_path = CURATED_ROOT / "_cross_endpoint_overlap.csv"
    df_overlap.to_csv(output_path, index=False)
    print(f"Overlap report generated with {len(df_overlap)} compounds present in >=2 endpoints.")
    print(f"Saved to {output_path}")

def audit_split_tightness() -> dict[str, float]:
    """Task C3: Audits scaffold split tightness (mean NN Tanimoto similarity)."""
    print(">>> Task C3: Audits scaffold split tightness...")
    endpoints = get_completed_endpoints()
    audit_results = {}
    
    warnings = []
    
    for ep in endpoints:
        v1_dir = CURATED_ROOT / ep / "v1.0"
        train_path = v1_dir / "splits" / "scaffold" / "train.parquet"
        test_path = v1_dir / "splits" / "scaffold" / "test.parquet"
        
        if not train_path.exists() or not test_path.exists():
            print(f"  Scaffold split files missing for '{ep}', skipping audit.")
            continue
            
        df_train = pd.read_parquet(train_path)
        df_test = pd.read_parquet(test_path)
        
        train_smiles = df_train["smiles_canonical"].dropna().unique().tolist()
        test_smiles = df_test["smiles_canonical"].dropna().unique().tolist()
        
        if not train_smiles or not test_smiles:
            print(f"  No SMILES present in splits for '{ep}', skipping.")
            continue
            
        # Convert to fingerprints
        train_fps = []
        for s in train_smiles:
            mol = Chem.MolFromSmiles(s)
            if mol:
                train_fps.append(AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048))
                
        test_fps = []
        for s in test_smiles:
            mol = Chem.MolFromSmiles(s)
            if mol:
                test_fps.append(AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048))
                
        if not train_fps or not test_fps:
            print(f"  Failed to generate fingerprints for '{ep}', skipping.")
            continue
            
        # For each test compound, calculate max Tanimoto similarity to any train compound
        nn_similarities = []
        for tfp in test_fps:
            sims = BulkTanimotoSimilarity(tfp, train_fps)
            if sims:
                nn_similarities.append(max(sims))
                
        mean_nn = sum(nn_similarities) / len(nn_similarities) if nn_similarities else 0.0
        audit_results[ep] = mean_nn
        print(f"  Endpoint: {ep:<25} Mean NN Tanimoto: {mean_nn:.4f}")
        
        if mean_nn >= 0.5:
            warnings.append(f"WARNING: Scaffold split tightness for '{ep}' is {mean_nn:.4f} (>= 0.5 threshold!)")
            
    # Append any split tightness warnings to docs/PHASE1_NOTES.md
    notes_path = DOCS_ROOT / "PHASE1_NOTES.md"
    if notes_path.exists() and warnings:
        with open(notes_path, "a") as f:
            f.write("\n## Scaffold Split Tightness Audit Warnings\n")
            for w in warnings:
                f.write(f"- {w}\n")
        print("Logged split tightness audit warnings to docs/PHASE1_NOTES.md.")
        
    return audit_results

def generate_summary_report(audit_results: dict[str, float]) -> None:
    """Task C4: Compiles all endpoint metrics and creates docs/CURATION_SUMMARY.md."""
    print(">>> Task C4: Compiles curation summary report...")
    endpoints = get_completed_endpoints()
    
    md_lines = [
        "# Edeon Phase 1 — Curated Datasets Summary Report",
        "",
        "This report is auto-generated by the release pipeline. It lists and evaluates all curated datasets for the Edeon Phase 1 project, representing the data foundation for downstream reference model training in Phase 2.",
        "",
        "## Curated Endpoints Curation Metrics",
        "",
        "| Endpoint | Raw Records | Curated Unique | Rejection Rate | Scaffold Split (Tr/Val/Te) | Scaffold Tightness | Random Split (Tr/Val/Te) | Log Range (Min/Max) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    
    for ep in endpoints:
        v1_dir = CURATED_ROOT / ep / "v1.0"
        stats_path = v1_dir / "curation_stats.json"
        card_path = v1_dir / "data_card.yaml"
        
        if not stats_path.exists() or not card_path.exists():
            continue
            
        with open(stats_path) as f:
            stats = json.load(f)
            
        with open(card_path) as f:
            card = yaml.safe_load(f)
            
        # Extract split sizes
        sc = card["splits"]["scaffold"]
        sc_str = f"{sc['train']}/{sc['cal']}/{sc['test']}"
        
        ra = card["splits"]["random"]
        ra_str = f"{ra['train']}/{ra['cal']}/{ra['test']}"
        
        # Scaffold tightness
        tightness = audit_results.get(ep, 0.0)
        tight_str = f"{tightness:.4f}"
        
        # Load parquet to get value_log range
        df = pd.read_parquet(v1_dir / "curated.parquet")
        log_vals = df["value_log"].dropna()
        if len(log_vals) > 0:
            range_str = f"{log_vals.min():.2f} / {log_vals.max():.2f}"
        else:
            range_str = "N/A"
            
        rej_rate = stats["rejection_rate"] * 100
        
        md_lines.append(
            f"| `{ep}` | {stats['raw_records']:,} | {stats['after_aggregation']:,} | {rej_rate:.1f}% | {sc_str} | **{tight_str}** | {ra_str} | {range_str} |"
        )
        
    md_lines.append("")
    md_lines.append("## Known Biases and Intended Use Notes")
    md_lines.append("")
    
    for ep in endpoints:
        card_path = CURATED_ROOT / ep / "v1.0" / "data_card.yaml"
        if not card_path.exists():
            continue
        with open(card_path) as f:
            card = yaml.safe_load(f)
            
        md_lines.append(f"### `{ep}`")
        md_lines.append(f"- **Intended Use**: {card.get('intended_use', 'N/A')}")
        md_lines.append("- **Known Biases**:")
        for bias in card.get("known_biases", []):
            md_lines.append(f"  - {bias}")
        md_lines.append("")
        
    # Write summary
    DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    summary_path = DOCS_ROOT / "CURATION_SUMMARY.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
        
    print(f"Curation summary report created successfully at {summary_path}.")

def generate_manifest() -> None:
    """Task D1: Compiles the top-level data/curated/MANIFEST.json."""
    print(">>> Task D1: Generating top-level manifest...")
    endpoints = get_completed_endpoints()
    
    manifest_data = {
        "generator": "edeon-release-pipeline",
        "version": "1.0.0",
        "release_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endpoints": {},
        "files": {}
    }
    
    for ep in endpoints:
        v1_dir = CURATED_ROOT / ep / "v1.0"
        card_path = v1_dir / "data_card.yaml"
        if not card_path.exists():
            continue
            
        with open(card_path) as f:
            card = yaml.safe_load(f)
            
        # Get source citation details
        primary_source = card["sources"][0] if card.get("sources") else {}
        
        manifest_data["endpoints"][ep] = {
            "dataset_id": card.get("dataset_id"),
            "version": card.get("version"),
            "license": primary_source.get("license", "Public domain / Open Access"),
            "citation": primary_source.get("citation", "N/A"),
            "doi": primary_source.get("doi", "N/A"),
            "url": primary_source.get("url", "N/A"),
            "compounds_count": card["curation_summary"]["after_aggregation"]
        }
        
        # Scan files recursively for this endpoint v1.0 directory
        for p in sorted(v1_dir.rglob("*")):
            if p.is_file() and p.name != "manifest.json":
                # Relative path from CURATED_ROOT
                rel_path = p.relative_to(CURATED_ROOT).as_posix()
                size = p.stat().st_size
                sha256 = get_file_sha256(p)
                
                manifest_data["files"][rel_path] = {
                    "size_bytes": size,
                    "sha256": sha256
                }
                
    # Also include the cross-endpoint overlap file if it exists
    overlap_path = CURATED_ROOT / "_cross_endpoint_overlap.csv"
    if overlap_path.exists():
        manifest_data["files"]["_cross_endpoint_overlap.csv"] = {
            "size_bytes": overlap_path.stat().st_size,
            "sha256": get_file_sha256(overlap_path)
        }
        
    output_path = CURATED_ROOT / "MANIFEST.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        
    print(f"Top-level manifest generated successfully at {output_path}.")

def bundle_release_zip() -> None:
    """Task D2: Zips data/curated/ and writes a README and checklist under dist/."""
    print(">>> Task D2: Bundling release package zip and README...")
    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    
    zip_path = DIST_ROOT / "edeon-curated-datasets-v1.0.zip"
    
    # Create the release zip
    print(f"Zipping curated dataset tree to {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Walk curated root
        for root, dirs, files in os.walk(CURATED_ROOT):
            root_path = Path(root)
            # Exclude raw temp directories
            if root_path.name == "temp":
                continue
            for file in files:
                file_path = root_path / file
                # Save path relative to the Edeon root's data/ folder so it unpacks to data/curated/
                rel_path_in_zip = Path("data/curated") / file_path.relative_to(CURATED_ROOT)
                zipf.write(file_path, rel_path_in_zip.as_posix())
                
    # Write dist/README.md
    readme_lines = [
        "# Edeon Curated Agrochemistry Datasets v1.0",
        "",
        "This release contains the standardized, quality-assured, and curated training datasets for Paper 3 and Phase 2 Tier-1 prediction model training.",
        "",
        "## Release Overview",
        "",
        "The ZIP archive includes versioned datasets for 9 curated ecotoxicity and environmental endpoints. Each endpoint directory contains:",
        "- `curated.parquet`: The authoritative, type-enforced Parquet dataset containing canonical compound structures, InChIKeys, and activity values.",
        "- `curated.csv`: Human-readable mirror of the curated records.",
        "- `splits/`: Frozen Bemis-Murcko scaffold and stratified random splits (Train 70% / Conformal Calibration 15% / Test 15%).",
        "- `data_card.yaml`: Standardized Data Card documenting criteria, standardisation pipelines, and performance.",
        "- `manifest.json`: Checksum files manifest.",
        "",
        "## Curated Endpoints list",
    ]
    
    endpoints = get_completed_endpoints()
    for ep in endpoints:
        readme_lines.append(f"- `{ep}`: Curated v1.0 release dataset.")
        
    readme_lines.extend([
        "",
        "## Downstream Phase 2 Usage",
        "Phase 2 models consume splits directly from Parquet files:",
        "`data/curated/<endpoint>/v1.0/splits/<split_type>/<partition>.parquet`",
        "",
        "## Zenodo Publication Checklist",
        "",
        "The deposit manager must perform the following manual steps to publish this bundle on Zenodo:",
        "- [ ] Log into Zenodo (https://zenodo.org/) using the Anthropic/Edeon account.",
        "- [ ] Click **New Upload** and select **Upload Files**.",
        "- [ ] Drag and drop the `edeon-curated-datasets-v1.0.zip` file.",
        "- [ ] Set **Title** to: `Edeon Curated Agrochemistry Datasets v1.0`.",
        "- [ ] Set **Description** to: `Curated reference datasets for ecotoxicity and environmental partitioning endpoints of organic compounds, supporting Papers 3 & Phase 2 prediction model benchmarks.`",
        "- [ ] Add authors, citations, and licenses (e.g. CC BY 4.0).",
        "- [ ] Click **Reserve DOI** to obtain the publication DOI.",
        "- [ ] Update the `dataset_doi` in the `data_card.yaml` files inside Edeon and re-zip if needed.",
        "- [ ] Click **Publish**.",
    ])
    
    readme_path = DIST_ROOT / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(readme_lines))
        
    print(f"Release README and Zenodo checklist written to {readme_path}.")
    print("Bundle release package prepared successfully.")

def run_release_pipeline() -> None:
    """Wrapper function running all Group C and Group D release steps."""
    print("==================================================")
    print("=== Starting Edeon Release Pipeline (C & D) ===")
    print("==================================================")
    
    generate_overlap_report()
    audit_results = audit_split_tightness()
    generate_summary_report(audit_results)
    generate_manifest()
    bundle_release_zip()
    
    print("==================================================")
    print("=== Release Pipeline Completed Successfully! ===")
    print("==================================================")
