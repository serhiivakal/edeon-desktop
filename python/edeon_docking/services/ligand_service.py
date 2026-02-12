import os
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from rdkit import Chem
from rdkit.Chem import AllChem
from meeko import MoleculePreparation, PDBQTWriterLegacy

from ..schema import (
    PreparedLigand,
    LigandPreparationParams
)
from edeon_engine.standardize import standardize_single

logger = logging.getLogger("edeon_docking")

class LigandService:
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            self.base_dir = Path(__file__).resolve().parents[3]
            self.cache_dir = self.base_dir / "data" / "docking" / "cache"
        else:
            self.cache_dir = Path(cache_dir)
            self.base_dir = self.cache_dir.parents[2]
            
        self.prepared_dir = self.cache_dir / "ligands"
        self.prepared_dir.mkdir(parents=True, exist_ok=True)

    def compute_hash(self, canonical_smiles: str, params: LigandPreparationParams) -> str:
        """Calculate SHA-256 hash representing canonical SMILES + prep params."""
        hasher = hashlib.sha256()
        hasher.update(canonical_smiles.encode("utf-8"))
        
        # Canonicalize params to JSON with sorted keys
        params_json = params.model_dump_json()
        hasher.update(params_json.encode("utf-8"))
        
        return hasher.hexdigest()

    def get_cached(self, ligand_hash: str) -> Optional[PreparedLigand]:
        """Check cache for prepared ligand metadata."""
        meta_path = self.prepared_dir / ligand_hash / "metadata.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r") as f:
                    data = json.load(f)
                    return PreparedLigand.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to read cached ligand metadata at {meta_path}: {e}")
        return None

    def _adjust_protonation(self, mol: Chem.Mol, params: LigandPreparationParams) -> Chem.Mol:
        """Adjust protonation state for physiological pH."""
        # 1. Deprotonate acids (e.g. carboxylic acids C(=O)[OH] -> C(=O)[O-])
        if params.deprotonate_acids:
            acid_pat = Chem.MolFromSmarts('[CX3](=[OX1])[OX2H1]')
            if acid_pat:
                matches = mol.GetSubstructMatches(acid_pat)
                for match in matches:
                    atom = mol.GetAtomWithIdx(match[2])
                    if atom.GetFormalCharge() == 0:
                        atom.SetFormalCharge(-1)
                        atom.SetNumExplicitHs(0)
                        
        # 2. Protonate bases (e.g. aliphatic amines R-N-R -> R-NH+-R)
        if params.protonate_bases:
            # Matches basic aliphatic nitrogen atoms (not amide, not aromatic, etc.)
            base_pat = Chem.MolFromSmarts('[NX3;H2,H1,H0;!$(NC=O);!$(N-[#6]=*)]')
            if base_pat:
                matches = mol.GetSubstructMatches(base_pat)
                for match in matches:
                    atom = mol.GetAtomWithIdx(match[0])
                    if atom.GetFormalCharge() == 0:
                        atom.SetFormalCharge(1)
                        
        try:
            mol.UpdatePropertyCache()
        except Exception as e:
            logger.warning(f"Failed to update property cache after protonation adjustment: {e}")
            
        return mol

    async def prepare(self, smiles: str, params: LigandPreparationParams) -> PreparedLigand:
        """Execute full ligand preparation pipeline."""
        # 1. Standardize SMILES
        std_res = standardize_single(smiles)
        if not std_res["valid"]:
            raise ValueError(f"Invalid SMILES input: {std_res['error']}")
            
        canonical_smiles = std_res["canonical"]
        ligand_hash = self.compute_hash(canonical_smiles, params)
        
        # Check cache
        cached = self.get_cached(ligand_hash)
        if cached and Path(cached.pdbqt_path).exists():
            logger.info(f"Returning cached prepared ligand for hash: {ligand_hash}")
            return cached
            
        target_folder = self.prepared_dir / ligand_hash
        target_folder.mkdir(parents=True, exist_ok=True)
        
        # 2. Parse standardized SMILES into RDKit Mol
        mol = Chem.MolFromSmiles(canonical_smiles)
        if not mol:
            raise ValueError("Failed to parse standardized SMILES into RDKit Mol")
            
        # 3. Adjust protonation state
        mol = self._adjust_protonation(mol, params)
        
        # 4. Add hydrogens
        if params.add_hydrogens:
            mol = Chem.AddHs(mol)
            
        # 5. Generate 3D conformer using ETKDGv3
        embed_status = -1
        embed_params = AllChem.ETKDGv3()
        # Set static random seed 42 per Section 10
        embed_params.randomSeed = 42
        
        for attempt in range(params.embed_attempts):
            embed_params.randomSeed = 42 + attempt
            embed_status = AllChem.EmbedMolecule(mol, embed_params)
            if embed_status == 0:
                break
                
        if embed_status != 0:
            # Fallback to random coordinates if standard embed fails
            embed_params.useRandomCoords = True
            for attempt in range(params.embed_attempts):
                embed_params.randomSeed = 42 + attempt
                embed_status = AllChem.EmbedMolecule(mol, embed_params)
                if embed_status == 0:
                    break
                    
        if embed_status != 0:
            raise RuntimeError("Conformer embedding failed after multiple attempts")
            
        # 6. Minimize with MMFF94 or UFF force field
        if params.optimization in ("MMFF94", "MMFF94s"):
            # Set maxIters to 200
            try:
                AllChem.MMFFOptimizeMolecule(mol, maxIters=200, forceField=params.optimization)
            except Exception:
                try:
                    AllChem.UFFOptimizeMolecule(mol, maxIters=200)
                except Exception:
                    logger.warning("Force field minimization failed. Proceeding with unoptimized conformer.")
        elif params.optimization == "UFF":
            try:
                AllChem.UFFOptimizeMolecule(mol, maxIters=200)
            except Exception:
                logger.warning("UFF force field minimization failed.")
                
        # 7. Convert to PDBQT using Meeko
        preparator = MoleculePreparation()
        mol_setups = preparator.prepare(mol)
        if not mol_setups:
            raise RuntimeError("Meeko failed to prepare ligand molecule")
            
        pdbqt_string, success, error_msg = PDBQTWriterLegacy.write_string(mol_setups[0])
        if not success:
            raise RuntimeError(f"Meeko PDBQT translation failed: {error_msg}")
            
        prepared_pdbqt_path = target_folder / "prepared.pdbqt"
        with open(prepared_pdbqt_path, "w") as f:
            f.write(pdbqt_string)
            
        # Save SDF block representation for frontend viewer convenience
        sdf_block = Chem.MolToMolBlock(mol)
        sdf_path = target_folder / "prepared.sdf"
        with open(sdf_path, "w") as f:
            f.write(sdf_block)
            
        # Calculate metadata
        rot_bonds = AllChem.CalcNumRotatableBonds(mol)
        formal_charge = Chem.GetFormalCharge(mol)
        atom_count = mol.GetNumAtoms()
        
        metadata = {
            "rotatable_bonds": rot_bonds,
            "formal_charge": formal_charge,
            "atom_count": atom_count,
        }
        
        prepared_ligand = PreparedLigand(
            ligand_hash=ligand_hash,
            source_smiles=smiles,
            canonical_smiles=canonical_smiles,
            pdbqt_path=str(prepared_pdbqt_path.resolve()),
            preparation_params=params,
            metadata=metadata,
            prepared_at=datetime.utcnow().isoformat()
        )
        
        # Save metadata to cache folder
        meta_path = target_folder / "metadata.json"
        with open(meta_path, "w") as f:
            f.write(prepared_ligand.model_dump_json(indent=2))
            
        return prepared_ligand
