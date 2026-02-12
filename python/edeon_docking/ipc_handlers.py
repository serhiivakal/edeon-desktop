import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List

from .schema import (
    ReceptorPreparationParams,
    LigandPreparationParams,
    DockingJobSpec
)
from .services.receptor_service import ReceptorService
from .services.ligand_service import LigandService
from .services.pocket_service import PocketService
from .services.docking_service import DockingService
from .services.analysis_service import AnalysisService

logger = logging.getLogger("edeon_docking")

# Initialize services
receptor_service = ReceptorService()
ligand_service = LigandService()
pocket_service = PocketService()
docking_service = DockingService()
analysis_service = AnalysisService()

def handle_receptor_load_from_source(params: Dict[str, Any]) -> Dict[str, Any]:
    """Load receptor from source (preset, pdb_code, alphafold, upload)."""
    source_type = params.get("source_type", "")
    identifier = params.get("identifier", "")
    
    # We run it in a sync wrapper or using asyncio.run
    loop = asyncio.get_event_loop()
    raw_path, source_url = loop.run_until_complete(
        receptor_service.load_from_source(source_type, identifier)
    )
    
    # Run default preparation immediately on load
    default_params = ReceptorPreparationParams()
    prepared = loop.run_until_complete(
        receptor_service.prepare(raw_path, default_params, source_url)
    )
    
    return prepared.model_dump(mode='json')

def handle_receptor_get_het_list(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Retrieve HET list from cached prepared receptor."""
    receptor_hash = params.get("receptor_hash", "")
    prepared = receptor_service.get_cached(receptor_hash)
    if not prepared:
        raise ValueError(f"Prepared receptor not found in cache for hash: {receptor_hash}")
    return [h.model_dump(mode='json') for h in prepared.het_entries]

def handle_receptor_reprepare(params: Dict[str, Any]) -> Dict[str, Any]:
    """Re-prepare receptor with modified parameters."""
    receptor_hash = params.get("receptor_hash", "")
    params_dict = params.get("params", {})
    
    prepared_cached = receptor_service.get_cached(receptor_hash)
    if not prepared_cached:
        raise ValueError(f"Base prepared receptor not found in cache for hash: {receptor_hash}")
        
    prep_params = ReceptorPreparationParams.model_validate(params_dict)
    
    loop = asyncio.get_event_loop()
    prepared = loop.run_until_complete(
        receptor_service.prepare(
            Path(prepared_cached.raw_pdb_path), 
            prep_params, 
            prepared_cached.pdb_source
        )
    )
    
    return prepared.model_dump(mode='json')

def handle_ligand_prepare(params: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare ligand structure (SMILES/SDF) to PDBQT."""
    smiles = params.get("smiles", "")
    params_dict = params.get("params", {})
    
    prep_params = LigandPreparationParams.model_validate(params_dict)
    
    loop = asyncio.get_event_loop()
    prepared = loop.run_until_complete(
        ligand_service.prepare(smiles, prep_params)
    )
    
    return prepared.model_dump(mode='json')

def handle_pocket_detect(params: Dict[str, Any]) -> Dict[str, Any]:
    """Detect pockets on receptor."""
    receptor_hash = params.get("receptor_hash", "")
    
    loop = asyncio.get_event_loop()
    detected = loop.run_until_complete(
        pocket_service.detect(receptor_hash)
    )
    
    return detected.model_dump(mode='json')

def handle_docking_run(params: Dict[str, Any]) -> Dict[str, Any]:
    """Run molecular docking job."""
    spec_dict = params.get("spec", {})
    spec = DockingJobSpec.model_validate(spec_dict)
    
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        docking_service.run(spec)
    )
    
    return result.model_dump(mode='json')

def handle_analysis_interactions(params: Dict[str, Any]) -> Dict[str, Any]:
    """Detect receptor-ligand interactions for a pose."""
    receptor_pdb_path = params.get("receptor_pdb_path", "")
    pose_sdf_block = params.get("pose_sdf_block", "")
    pose_index = params.get("pose_index", 1)
    
    result = analysis_service.analyze_interactions(
        Path(receptor_pdb_path),
        pose_sdf_block,
        pose_index
    )
    
    return result.model_dump(mode='json')

def handle_analysis_distance(params: Dict[str, Any]) -> float:
    """Measure distance between two atoms."""
    pose_sdf_block = params.get("pose_sdf_block", "")
    receptor_pdb_path = params.get("receptor_pdb_path", "")
    atom1_selector = params.get("atom1_selector", "")
    atom2_selector = params.get("atom2_selector", "")
    
    return analysis_service.measure_distance(
        pose_sdf_block,
        Path(receptor_pdb_path),
        atom1_selector,
        atom2_selector
    )

def handle_generate_2d_interaction_map(params: Dict[str, Any]) -> str:
    """Generate a 2D interaction map SVG for a pose against receptor."""
    receptor_pdb_path = params.get("receptor_pdb_path", "")
    pose_sdf_block = params.get("pose_sdf_block", "")
    pose_index = params.get("pose_index", 1)
    
    return analysis_service.generate_2d_interaction_map(
        Path(receptor_pdb_path),
        pose_sdf_block,
        pose_index
    )

def handle_cluster_poses(params: Dict[str, Any]) -> List[List[int]]:
    """Cluster docking poses by heavy atom RMSD without superposition."""
    poses_list = params.get("poses", [])
    rmsd_cutoff = params.get("rmsd_cutoff", 2.0)
    
    from .schema import DockedPose
    poses = [DockedPose.model_validate(p) for p in poses_list]
    
    return analysis_service.cluster_poses_by_rmsd(poses, rmsd_cutoff)


