"""Measured Value Index for Edeon Phase 2.

Loads curated experimental measurements from Phase 1 Parquet datasets
and indexes them by InChIKey and Endpoint for quick startup-time overlays.
"""

import os
import logging
import pandas as pd
from typing import List, Dict, Tuple, Any, Optional
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import rdinchi
from edeon_models.endpoints import Endpoint

logger = logging.getLogger("edeon_models.overlay.lookup")

def smiles_to_inchikey(smiles: str) -> Optional[str]:
    """Helper to convert a SMILES string to its canonical InChIKey."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return rdinchi.MolToInchiKey(mol)
    except Exception as e:
        logger.debug(f"Failed to generate InChIKey for SMILES {smiles}: {e}")
        return None

class ExperimentalValueIndex:
    """In-memory lookup index from InChIKey to list of curated experimental measurements."""
    
    def __init__(self):
        self._index: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    @classmethod
    def build(cls, curated_root: str = "data/curated") -> "ExperimentalValueIndex":
        """Walks the curated root folder and indexes all curated.parquet records."""
        index_obj = cls()
        root_path = Path(curated_root)
        
        if not root_path.exists():
            logger.warning(f"Curated root directory {curated_root} does not exist. Index will be empty.")
            return index_obj
            
        parquet_files = list(root_path.glob("**/v1.0/curated.parquet"))
        logger.info(f"Scanning curated datasets. Found {len(parquet_files)} curated.parquet files.")
        
        count = 0
        for p_file in parquet_files:
            try:
                df = pd.read_parquet(p_file)
                # Check necessary columns
                required = ["inchikey", "value", "value_units", "source", "endpoint"]
                missing = [c for c in required if c not in df.columns]
                if missing:
                    logger.warning(f"Parquet {p_file} is missing required columns: {missing}. Skipping.")
                    continue
                    
                for _, row in df.iterrows():
                    ikey = str(row["inchikey"])
                    ep_val = str(row["endpoint"])
                    
                    # Convert to canonical Endpoint to check validity
                    try:
                        resolved_ep = Endpoint(ep_val)
                    except ValueError:
                        continue
                        
                    key = (ikey, resolved_ep.value)
                    
                    # Extract record citation / DOI
                    citation = str(row["source_ref"]) if "source_ref" in row and pd.notna(row["source_ref"]) else ""
                    
                    record = {
                        "value": float(row["value"]),
                        "units": str(row["value_units"]),
                        "source": str(row["source"]),
                        "citation": citation
                    }
                    
                    if key not in index_obj._index:
                        index_obj._index[key] = []
                    index_obj._index[key].append(record)
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to read parquet file {p_file}: {e}")
                
        logger.info(f"Successfully loaded {count} curated measurements into the Measured Value Index.")
        return index_obj

    def lookup(self, inchikey: str, endpoint: Endpoint) -> List[Dict[str, Any]]:
        """Looks up experimental measurements for a specific InChIKey and Endpoint."""
        if not inchikey:
            return []
        resolved_ep = Endpoint(endpoint)
        return self._index.get((inchikey, resolved_ep.value), [])

    def lookup_smiles(self, smiles: str, endpoint: Endpoint) -> List[Dict[str, Any]]:
        """Convenience lookup: Standardizes SMILES to InChIKey, then queries the index."""
        ikey = smiles_to_inchikey(smiles)
        if ikey is None:
            return []
        return self.lookup(ikey, endpoint)
