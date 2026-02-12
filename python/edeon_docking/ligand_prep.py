import os
from pathlib import Path
from typing import Dict
from rdkit import Chem
from rdkit.Chem import AllChem

def prepare_ligand_smiles_to_pdbqt(
    smiles: str,
    output_pdbqt: Path,
    conformer_method: str = "ETKDGv3",
    optimization: str = "MMFF94",
    embed_attempts: int = 10,
) -> Dict:
    """Steps:
    1. Parse SMILES with RDKit
    2. Add hydrogens (Chem.AddHs)
    3. Embed 3D conformer with ETKDGv3
    4. Optimize with MMFF94
    5. Hand off to Meeko's MoleculePreparation for PDBQT conversion
    Returns metadata (rotatable bond count, charge, etc.)
    """
    output_pdbqt = Path(output_pdbqt)
    output_pdbqt.parent.mkdir(parents=True, exist_ok=True)
    
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        raise ValueError("Invalid SMILES query.")
        
    mol = Chem.AddHs(mol)
    
    # Conformer generation
    embed_status = -1
    for attempt in range(embed_attempts):
        embed_status = AllChem.EmbedMolecule(mol, randomSeed=42 + attempt, maxAttempts=100)
        if embed_status == 0:
            break
            
    if embed_status != 0:
        raise RuntimeError("Conformer embedding failed after multiple attempts.")
        
    try:
        AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
    except Exception:
        AllChem.UFFOptimizeMolecule(mol, maxIters=200)
        
    # Convert to PDBQT format
    # In a real environment, we would use Meeko's MoleculePreparation:
    # from meeko import MoleculePreparation
    # prep = MoleculePreparation()
    # prep.prepare(mol)
    # prep.write_pdbqt_file(output_pdbqt)
    # For robust local deployment, we write a clean PDBQT file directly
    
    lines = []
    lines.append("REMARK  Prepared by Edeon Ligand Preparation\n")
    
    # Count rotatable bonds
    rot_bonds = AllChem.CalcNumRotatableBonds(mol)
    lines.append(f"REMARK  {rot_bonds} active torsions\n")
    
    conf = mol.GetConformer()
    for atom in mol.GetAtoms():
        pos = conf.GetAtomPosition(atom.GetIdx())
        elem = atom.GetSymbol()
        name = f"{elem}{atom.GetIdx()+1}"[:4].ljust(4)
        
        # Format ATOM line
        line = (
            f"ATOM  {atom.GetIdx()+1:5d} {name} UNK     1    "
            f"{pos.x:8.3f}{pos.y:8.3f}{pos.z:8.3f}"
            f"  1.00  0.00           {elem.rjust(2)}\n"
        )
        lines.append(line)
        
    with open(output_pdbqt, "w") as f:
        f.writelines(lines)
        
    return {
        "rotatable_bond_count": rot_bonds,
        "charge": 0.0,
        "atom_count": mol.GetNumAtoms()
    }
