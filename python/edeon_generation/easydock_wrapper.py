import asyncio
import time
import logging
from typing import List, Tuple, Literal, Optional, Dict, Any
from dataclasses import dataclass

from edeon_docking.schema import PreparedReceptor, DockingJobSpec, DockedPose
from edeon_docking.services.docking_service import DockingService
from edeon_docking.services.ligand_service import LigandService
from edeon_docking.schema import LigandPreparationParams

logger = logging.getLogger("edeon_generation")

@dataclass
class EasyDockResult:
    smiles: str
    docking_score: float  # Top pose score
    poses: List[Dict[str, Any]]  # List of serialized DockedPose model dicts
    elapsed_seconds: float
    error: Optional[str] = None

class EasyDockService:
    """Edeon wrapper around EasyDock for high-throughput docking.
    
    Orchestrates ligand preparation and batch docking by utilizing Edeon's
    core DockingService concurrently.
    """
    
    def __init__(self):
        self.docking_service = DockingService()
        self.ligand_service = LigandService()

    async def dock_batch(
        self,
        receptor: PreparedReceptor,
        ligand_smiles: List[str],
        box_center: Tuple[float, float, float],
        box_size: Tuple[float, float, float],
        engine: Literal["vina", "gnina"] = "vina",
        n_workers: Optional[int] = None,
    ) -> List[EasyDockResult]:
        """Batch docking. Parallelizes concurrently using asyncio."""
        start_time = time.time()
        
        # 1. Prepare all ligands
        # We prepare them in parallel
        async def prep_one(smiles: str) -> Tuple[str, Optional[Any], Optional[str]]:
            try:
                prep_params = LigandPreparationParams(
                    conformer_method="ETKDGv3",
                    optimization="MMFF94",
                    embed_attempts=10,
                    add_hydrogens=True,
                    pH=7.4
                )
                lig = await self.ligand_service.prepare(smiles, prep_params)
                return smiles, lig, None
            except Exception as e:
                logger.warning(f"Failed to prepare ligand {smiles}: {e}")
                return smiles, None, str(e)

        prep_tasks = [prep_one(s) for s in ligand_smiles]
        prep_results = await asyncio.gather(*prep_tasks)
        
        # 2. Run docking for successfully prepared ligands
        async def dock_one(smiles: str, prepared_ligand: Any, prep_error: Optional[str]) -> EasyDockResult:
            if prep_error:
                return EasyDockResult(
                    smiles=smiles,
                    docking_score=0.0,
                    poses=[],
                    elapsed_seconds=0.0,
                    error=f"Ligand prep failed: {prep_error}"
                )
                
            try:
                # Build job spec
                spec = DockingJobSpec(
                    job_id="",  # Auto-computed by service
                    receptor_hash=receptor.receptor_hash,
                    ligand_hash=prepared_ligand.ligand_hash,
                    box_center=box_center,
                    box_size=box_size,
                    exhaustiveness=4,  # Lower exhaustiveness for faster de novo screening
                    num_modes=9,
                    seed=42,
                    engine=engine,
                    created_at=""  # Auto-computed
                )
                
                job_start = time.time()
                result = await self.docking_service.run(spec)
                job_elapsed = time.time() - job_start
                
                # Top score is the score of the first pose
                top_score = result.poses[0].score_kcal_per_mol if result.poses else 0.0
                
                return EasyDockResult(
                    smiles=smiles,
                    docking_score=top_score,
                    poses=[p.model_dump(mode='json') for p in result.poses],
                    elapsed_seconds=round(job_elapsed, 2),
                    error=None
                )
            except Exception as e:
                logger.warning(f"Failed to dock ligand {smiles}: {e}")
                return EasyDockResult(
                    smiles=smiles,
                    docking_score=0.0,
                    poses=[],
                    elapsed_seconds=0.0,
                    error=str(e)
                )

        # Semaphore to limit concurrency based on n_workers or CPU count
        sem_limit = n_workers or os.cpu_count() or 4
        sem = asyncio.Semaphore(sem_limit)
        
        async def sem_dock_one(smiles: str, prepared_ligand: Any, prep_error: Optional[str]) -> EasyDockResult:
            async with sem:
                return await dock_one(smiles, prepared_ligand, prep_error)

        dock_tasks = [sem_dock_one(s, lig, err) for s, lig, err in prep_results]
        results = await asyncio.gather(*dock_tasks)
        
        # Emits final docking progress
        print(f"[DOCKING_PROGRESS] {{\"percent\": 100}}", flush=True)
        
        return results
import os
