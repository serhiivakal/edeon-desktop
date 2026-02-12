"""
Edeon Engine — Speciation Caching Utility
"""

import sqlite3
import json
from typing import Optional, Dict, Any
from rdkit import Chem
from rdkit.Chem import rdmolfiles


def get_inchikey(smiles: str) -> str:
    """Compute InChIKey for a SMILES string."""
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        try:
            return rdmolfiles.MolToInchiKey(mol)
        except Exception:
            pass
    return smiles


def read_speciation_cache(db_path: str, smiles: str, ph_target: float) -> Optional[Dict[str, Any]]:
    """Query speciation_cache table by InChIKey and ph_target."""
    if not db_path:
        return None
    inchikey = get_inchikey(smiles)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT payload_json FROM speciation_cache WHERE input_inchikey = ? AND ph_target = ?",
            (inchikey, ph_target),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def write_speciation_cache(db_path: str, smiles: str, ph_target: float, payload: Dict[str, Any]) -> None:
    """Save speciation payload into speciation_cache table."""
    if not db_path:
        return
    inchikey = get_inchikey(smiles)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO speciation_cache (input_inchikey, ph_target, payload_json) VALUES (?, ?, ?)",
            (inchikey, ph_target, json.dumps(payload)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
