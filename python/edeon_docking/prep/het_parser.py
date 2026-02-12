import os
import yaml
import logging
from pathlib import Path
from typing import List, Set, Dict, Any
from Bio.PDB import PDBParser
from ..schema import HetEntry

logger = logging.getLogger("edeon_docking")

STANDARD_AMINO_ACIDS = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL"
}

STANDARD_NUCLEIC_ACIDS = {"A", "C", "G", "U", "DA", "DC", "DG", "DT"}

MODIFIED_RESIDUES = {
    "MSE", "CSE", "PTR", "TPO", "SEP", "HYP", "ALY", "M3L", "CSO", "CSD", "OCS"
}

COMMON_BUFFERS = {
    "SO4", "PO4", "GOL", "EDO", "PEG", "ACT", "DTT", "DMS", "IPA", "PG4", "PEG"
}

COFACTOR_ION_WHITELIST = {
    "MG", "CA", "ZN", "FE", "FE2", "FE3", "MN", "CU", "CO", "NI"
}

ALL_ION_RESNAMES = {
    "NA", "K", "MG", "CA", "ZN", "FE", "FE2", "FE3", "MN", "CU", "CO", "NI", "CL", "BR", "I"
}

def load_cofactor_whitelist() -> Set[str]:
    """Load cofactor names from YAML whitelist."""
    # Find YAML file relative to this file
    # We are in python/edeon_docking/prep/het_parser.py
    # data/docking/cofactor_allowlist.yaml is at ../../../data/docking/cofactor_allowlist.yaml
    yaml_path = Path(__file__).resolve().parents[3] / "data" / "docking" / "cofactor_allowlist.yaml"
    
    default_cofactors = {
        "HEM", "HEC", "FAD", "FMN", "NAD", "NAP", "NDP", "ATP", "ADP", "SAM", "CLA", "BCL", "PLP"
    }
    
    if yaml_path.exists():
        try:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)
                if data and "cofactors" in data:
                    return set(data["cofactors"])
        except Exception as e:
            logger.warning(f"Failed to load cofactor whitelist YAML from {yaml_path}: {e}")
            
    return default_cofactors

def parse_het_atoms(pdb_path: Path) -> List[HetEntry]:
    """Parse all non-standard HET residues in the PDB structure and classify them."""
    pdb_path = Path(pdb_path)
    if not pdb_path.exists():
        logger.error(f"PDB file does not exist: {pdb_path}")
        return []
        
    parser = PDBParser(QUIET=True)
    try:
        structure = parser.get_structure("receptor", str(pdb_path))
    except Exception as e:
        logger.error(f"Biopython failed to parse PDB structure {pdb_path}: {e}")
        return []
        
    cofactor_whitelist = load_cofactor_whitelist()
    het_entries: List[HetEntry] = []
    seen_residues = set()
    
    for model in structure:
        for chain in model:
            chain_id = chain.id or "A"
            for residue in chain:
                resname = residue.get_resname().strip()
                res_id = residue.id
                
                # Biopython represents HETATM residue IDs as a tuple where the first element is e.g. "H_HEM"
                is_hetero = res_id[0].startswith("H_") or res_id[0].startswith("W_")
                
                if not is_hetero:
                    continue
                    
                # Skip standard residues that might be flagged as hetero
                if resname in STANDARD_AMINO_ACIDS or resname in STANDARD_NUCLEIC_ACIDS:
                    continue
                    
                # Unique identifier for the residue to avoid duplicate parsing across models
                residue_key = (chain_id, resname, res_id[1])
                if residue_key in seen_residues:
                    continue
                seen_residues.add(residue_key)
                
                atom_count = len(list(residue.get_atoms()))
                
                # Classify residue
                classification = "unknown"
                default_action = "strip"
                
                resname_upper = resname.upper()
                
                if resname_upper in {"HOH", "H2O", "WAT", "DOD"}:
                    classification = "water"
                    default_action = "strip"
                elif resname_upper in cofactor_whitelist:
                    classification = "cofactor"
                    default_action = "keep"
                elif resname_upper in MODIFIED_RESIDUES:
                    classification = "modified_residue"
                    default_action = "keep"
                elif resname_upper in COMMON_BUFFERS or resname_upper.startswith("PEG"):
                    classification = "buffer"
                    default_action = "strip"
                elif atom_count == 1 and (resname_upper in ALL_ION_RESNAMES or len(resname_upper) <= 2):
                    classification = "ion"
                    if resname_upper in COFACTOR_ION_WHITELIST:
                        default_action = "keep"
                    else:
                        default_action = "strip"
                elif atom_count > 8:
                    classification = "cocrystal_ligand"
                    default_action = "strip"
                else:
                    classification = "unknown"
                    default_action = "strip"
                    logger.warning(f"Unknown HETATM residue parsed: {resname} with {atom_count} atoms.")
                    
                het_entries.append(HetEntry(
                    residue_name=resname,
                    chain_id=chain_id,
                    residue_number=res_id[1],
                    atom_count=atom_count,
                    type_classification=classification,
                    default_action=default_action,
                    user_action=default_action
                ))
                
    return het_entries
