"""
Edeon Engine — Building Block Reagent Stock Catalog Manager
"""

import os
from typing import Dict, Set, List, Any
from rdkit import Chem


# Curated in-memory commercial building block catalog for common reagents
DEFAULT_AGROCHEM_STOCK: Set[str] = {
    "CC(=O)O", "CC(=O)Cl", "ClC1=CC=CC=C1", "O=C(Cl)C1=CC=CC=C1", "NC1=CC=CC=C1",
    "OB(O)C1=CC=CC=C1", "BrC1=CC=CC=C1", "IC1=CC=CC=C1", "CCN", "CCN(CC)CC",
    "CCO", "CO", "ClC1=NC=CC=C1", "NC1=CC=NC=C1", "O=C1CCCC1", "O=C1CCCCC1",
    "OC1=CC=CC=C1", "CS(=O)(=O)Cl", "CC1=CC=CC=C1C(=O)O", "NCCN"
}


class StockManager:
    """Manages loaded stock catalogs by stock_id."""

    def __init__(self):
        self._stocks: Dict[str, Set[str]] = {
            "agrochem_default": DEFAULT_AGROCHEM_STOCK
        }

    def is_in_stock(self, smiles: str, stock_id: str = "agrochem_default") -> bool:
        """Check if a SMILES or canonical variant is present in the stock."""
        stock = self._stocks.get(stock_id, DEFAULT_AGROCHEM_STOCK)
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            can_smi = Chem.MolToSmiles(mol, canonical=True)
            return can_smi in stock or smiles in stock
        return smiles in stock

    def get_stock_size(self, stock_id: str = "agrochem_default") -> int:
        return len(self._stocks.get(stock_id, DEFAULT_AGROCHEM_STOCK))

    def import_stock_file(self, file_path: str, stock_id: str) -> int:
        """Import custom building block SMILES/SDF catalog file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Stock file not found: {file_path}")

        smiles_set = set()
        if file_path.endswith(".sdf"):
            suppl = Chem.SDMolSupplier(file_path)
            for m in suppl:
                if m:
                    smiles_set.add(Chem.MolToSmiles(m, canonical=True))
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        mol = Chem.MolFromSmiles(parts[0])
                        if mol:
                            smiles_set.add(Chem.MolToSmiles(mol, canonical=True))

        self._stocks[stock_id] = smiles_set
        return len(smiles_set)


_STOCK_MANAGER = StockManager()


def get_stock_manager() -> StockManager:
    return _STOCK_MANAGER
