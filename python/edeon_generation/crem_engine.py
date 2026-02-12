import os
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.DataStructs import TanimotoSimilarity

# Default public fragments database path
DEFAULT_FRAGMENTS_DB = Path(__file__).resolve().parents[2] / "data" / "generation" / "crem_fragments_v0.3.db"

BOOTSTRAP_SMILES = [
    "c1ccccc1",       # benzene
    "Cc1ccccc1",      # toluene
    "CCc1ccccc1",     # ethylbenzene
    "Clc1ccccc1",     # chlorobenzene
    "Fc1ccccc1",      # fluorobenzene
    "Brc1ccccc1",     # bromobenzene
    "Oc1ccccc1",      # phenol
    "Nc1ccccc1",      # aniline
    "COc1ccccc1",     # anisole
    "CC(=O)c1ccccc1",  # acetophenone
    "c1ccc(CC2OCCO2)cc1", # benzyl dioxolane
    "CN(C)C(=O)c1ccccc1",  # N,N-dimethylbenzamide
]

@dataclass
class GenerationResult:
    parent_smiles: str
    mutant_smiles: str
    transformation: str           # SMARTS describing the change
    fragment_id: str              # Reference/key in the database
    similarity_to_parent: float   # Tanimoto similarity (ECFP4)

class CReMGenerationEngine:
    """Edeon wrapper around the CReM mutation engine."""
    
    def __init__(self, fragments_db_path: Optional[Path] = None, max_mutations: int = 50):
        if fragments_db_path is None:
            fragments_db_path = DEFAULT_FRAGMENTS_DB
            
        self._fragments_db = Path(fragments_db_path)
        self._max_mutations = max_mutations
        
        # Ensure database is bootstrapped if missing
        self._ensure_database_exists()
        
    def _ensure_database_exists(self):
        """Checks if the fragments DB exists. If not, bootstraps a tiny local DB."""
        if self._fragments_db.exists():
            return
            
        # Ensure parent folder exists
        self._fragments_db.parent.mkdir(parents=True, exist_ok=True)
        
        # Write temporary SMILES file
        with tempfile.NamedTemporaryFile("w", suffix=".smi", delete=False) as f:
            f.write("\n".join(BOOTSTRAP_SMILES))
            smi_path = f.name
            
        try:
            # Find the cremdb_create script relative to the environment's python/conda bin
            # In production/WSL it is expected to be on the PATH since crem was pip-installed
            # We'll execute via python -m crem.scripts.cremdb_create to be environment-agnostic
            import sys
            cmd = [
                sys.executable,
                "-m",
                "crem.scripts.cremdb_create",
                "-i", smi_path,
                "-o", str(self._fragments_db),
                "-s", "standard",
                "-r", "1", "2"
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
        except Exception as e:
            # If the import/module execution fails, try running as system command
            try:
                subprocess.run(
                    ["cremdb_create", "-i", smi_path, "-o", str(self._fragments_db), "-s", "standard", "-r", "1", "2"],
                    check=True,
                    capture_output=True
                )
            except Exception as e_inner:
                raise RuntimeError(
                    f"Failed to bootstrap CReM database at {self._fragments_db}. "
                    f"Errors: {e} and {e_inner}"
                )
        finally:
            if os.path.exists(smi_path):
                try:
                    os.remove(smi_path)
                except Exception:
                    pass

    def generate_mutants(
        self,
        parent_smiles: str,
        radius: int = 2,
        min_size: int = 1,
        max_size: int = 5,
        max_mutants: int = 50,
        return_smiles_only: bool = False,
    ) -> List[GenerationResult]:
        """Apply CReM mutations to parent. Returns list of mutant compounds."""
        from crem.crem import mutate_mol
        
        parent_mol = Chem.MolFromSmiles(parent_smiles)
        if parent_mol is None:
            raise ValueError(f"Invalid parent SMILES: {parent_smiles}")
            
        # Ensure parent has Morgan fingerprint for similarity comparison
        parent_fp = AllChem.GetMorganFingerprintAsBitVect(parent_mol, 2, 2048)
        
        # Execute CReM mutation
        # return_rxn=True gives us list of [mutant_smiles, rxn_smarts]
        mutations = list(mutate_mol(
            parent_mol,
            db_name=str(self._fragments_db),
            radius=radius,
            min_size=min_size,
            max_size=max_size,
            max_replacements=max_mutants or self._max_mutations,
            return_rxn=True
        ))
        
        results = []
        for mut_smiles, rxn_smarts in mutations:
            mut_mol = Chem.MolFromSmiles(mut_smiles)
            if mut_mol is None:
                continue
                
            mut_fp = AllChem.GetMorganFingerprintAsBitVect(mut_mol, 2, 2048)
            sim = TanimotoSimilarity(parent_fp, mut_fp)
            
            results.append(GenerationResult(
                parent_smiles=parent_smiles,
                mutant_smiles=mut_smiles,
                transformation=rxn_smarts,
                fragment_id=rxn_smarts,  # Use reaction SMARTS as reference key
                similarity_to_parent=round(sim, 4)
            ))
            
        # Sort by similarity to parent descending
        results.sort(key=lambda x: x.similarity_to_parent, reverse=True)
        return results
