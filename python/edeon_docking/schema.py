from pydantic import BaseModel, Field
from typing import Optional, List, Tuple, Literal, Dict, Any

class HetEntry(BaseModel):
    residue_name: str           # e.g. "HOH", "HEM", "NAG", "IMD"
    chain_id: str
    residue_number: int
    atom_count: int
    type_classification: Literal["water", "ion", "cofactor", "cocrystal_ligand",
                                  "modified_residue", "buffer", "unknown"]
    default_action: Literal["strip", "keep"]
    user_action: Literal["strip", "keep"]   # Initially = default_action

class ReceptorPreparationParams(BaseModel):
    keep_water: bool = False
    keep_ions: bool = False                # Override default keep for ions
    keep_cofactors: bool = True
    keep_cocrystal_ligands: bool = False   # Strip for clean docking
    custom_het_actions: Dict[str, str] = {}  # residue_name → "strip"/"keep"
    add_hydrogens: bool = True
    ph: float = 7.4                        # For PROPKA-based H-addition if available
    method: Literal["meeko", "meeko_propka"] = "meeko"

class PreparedReceptor(BaseModel):
    receptor_hash: str
    pdb_source: str                # URL or file path
    pdbqt_path: str
    raw_pdb_path: str
    preparation_params: ReceptorPreparationParams
    metadata: Dict[str, Any]       # chain_count, residue_count, charge_sum, etc.
    het_entries: List[HetEntry]
    cocrystal_ligands: List[Dict[str, Any]]  # Each: residue_name, chain, centroid_xyz, residue_count
    prepared_at: str

class LigandPreparationParams(BaseModel):
    conformer_method: Literal["ETKDGv3", "ETKDGv2", "ETDG"] = "ETKDGv3"
    optimization: Literal["MMFF94", "MMFF94s", "UFF", "none"] = "MMFF94"
    embed_attempts: int = 10
    add_hydrogens: bool = True
    pH: float = 7.4              # For protonation state
    deprotonate_acids: bool = True   # COOH → COO⁻
    protonate_bases: bool = True     # amines → ammoniums

class PreparedLigand(BaseModel):
    ligand_hash: str
    source_smiles: str
    canonical_smiles: str
    pdbqt_path: str
    preparation_params: LigandPreparationParams
    metadata: Dict[str, Any]    # rotatable_bonds, formal_charge, atom_count, etc.
    prepared_at: str

class FpocketResult(BaseModel):
    pocket_id: int
    rank: int                      # 1 = top pocket
    druggability_score: float
    volume_angstrom_cubed: float
    centroid: Tuple[float, float, float]
    pocket_residues: List[str]     # e.g. ["A:HIS-440", "A:GLU-327"]
    bounding_box: Dict[str, Any]             # min/max per axis

class PocketDetectionResult(BaseModel):
    receptor_hash: str
    fpocket_results: List[FpocketResult]
    cocrystal_pockets: List[Dict[str, Any]]  # From receptor's cocrystal ligands
    detected_at: str

class DockingJobSpec(BaseModel):
    job_id: str                          # SHA-256 of canonical job parameters
    receptor_hash: str
    ligand_hash: str
    box_center: Tuple[float, float, float]
    box_size: Tuple[float, float, float]
    exhaustiveness: int = 8
    num_modes: int = 9
    seed: int = 42
    engine: Literal["vina", "gnina"] = "vina"
    gnina_binary_path: Optional[str] = None
    created_at: str

class DockedPose(BaseModel):
    pose_index: int                      # 1-based ranking
    score_kcal_per_mol: float
    rmsd_to_top: Optional[float] = None
    rmsd_to_prev: Optional[float] = None
    pdbqt_block: str
    sdf_block: Optional[str] = None             # For viewer convenience
    gnina_cnn_score: Optional[float] = None

class DockingJobResult(BaseModel):
    job_id: str
    spec: DockingJobSpec
    poses: List[DockedPose]
    elapsed_seconds: float
    engine_version: str
    command_line: str
    warnings: List[str]
    completed_at: str

class InteractionFingerprint(BaseModel):
    pose_index: int
    hbond_donor: List[Dict[str, Any]]          # ligand_atom, residue, distance
    hbond_acceptor: List[Dict[str, Any]]
    hydrophobic: List[Dict[str, Any]]
    pi_stacking: List[Dict[str, Any]]
    pi_cation: List[Dict[str, Any]]
    salt_bridge: List[Dict[str, Any]]
    halogen_bond: List[Dict[str, Any]]
    metal_coordination: List[Dict[str, Any]]

class JobHistoryEntry(BaseModel):
    job_id: str
    receptor_id: str                # Preset ID or PDB code or hash
    receptor_display_name: str
    ligand_smiles: str
    ligand_display_name: Optional[str] = None
    box_center: Tuple[float, float, float]
    box_size: Tuple[float, float, float]
    top_score: float
    num_poses: int
    elapsed_seconds: float
    completed_at: str
    starred: bool = False           # User can star jobs to keep
