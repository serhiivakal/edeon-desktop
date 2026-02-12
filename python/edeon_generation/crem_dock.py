import os
import time
import asyncio
import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field

from edeon_docking.schema import PreparedReceptor
from edeon_models.ipc.commands import execute_command

from .crem_engine import CReMGenerationEngine
from .easydock_wrapper import EasyDockService

logger = logging.getLogger("edeon_generation")

@dataclass
class GenerationCompound:
    smiles: str
    docking_score: float
    generation: int
    parent_in_generation: str
    predicted_properties: Dict[str, Any]
    composite_score: float
    mpo_score: float
    rank_category: str  # "Lead" | "Candidate" | "Deprioritize"

@dataclass
class IterationResult:
    iteration: int
    compounds: List[GenerationCompound] = field(default_factory=list)

@dataclass
class CReMDockResult:
    parent_smiles: str
    receptor_id: str
    best_compounds: List[GenerationCompound]
    iterations: List[IterationResult]
    total_compounds_generated: int
    total_compounds_docked: int
    elapsed_seconds: float

class CReMDockPipeline:
    """Closed-loop generative design pipeline.
    
    Iteratively mutates a parent molecule using CReM, docks the candidates using
    EasyDock, predicts safety/toxicity, and selects the best MPO-ranked mutants
    to seed the next round.
    """
    
    def __init__(self, fragments_db_path: Optional[str] = None):
        from pathlib import Path
        db_path = Path(fragments_db_path) if fragments_db_path else None
        self.generation_engine = CReMGenerationEngine(db_path)
        self.docking_service = EasyDockService()

    def _get_batch_predictions(self, smiles_list: List[str]) -> Dict[str, Dict[str, Any]]:
        """Gathers predictions for all endpoints in batch for a list of SMILES."""
        from edeon_models import Endpoint
        results = {s: {} for s in smiles_list}
        
        for ep in Endpoint:
            try:
                preds = execute_command("predict", {"endpoint": ep.value, "smiles": smiles_list})
                for pred in preds:
                    s = pred["smiles"]
                    if s in results:
                        results[s][ep.value] = pred
            except Exception as e:
                logger.warning(f"Failed to batch predict {ep.value}: {e}")
                
        return results

    async def run(
        self,
        parent_smiles: str,
        receptor: PreparedReceptor,
        box_center: Tuple[float, float, float],
        box_size: Tuple[float, float, float],
        n_iterations: int = 3,
        population_size: int = 20,
        keep_top_n: int = 5,
        weights: Optional[Dict[str, float]] = None,
    ) -> CReMDockResult:
        """Runs the evolutionary closed-loop docking and safety-profile scoring."""
        start_time = time.time()
        
        from edeon_engine.properties import compute_properties_single
        from edeon_engine.tice_rules import check_tice_rules
        from edeon_engine.selectivity import compute_single_selectivity
        from edeon_engine.resistance import resistance_batch
        from edeon_engine.toxicity import toxicity_batch
        from edeon_engine.scoring import compute_mpo_score
        
        # We start with the parent SMILES
        current_seeds = [parent_smiles]
        seen_compounds: Dict[str, GenerationCompound] = {}
        iterations_records: List[IterationResult] = []
        
        total_docked_count = 0
        
        for iteration in range(1, n_iterations + 1):
            logger.info(f"Running CReM-dock iteration {iteration}/{n_iterations}...")
            
            # Emit progress update line so frontend can display status
            # Iteration progress calculated out of 100%
            percent_start = int(((iteration - 1) / n_iterations) * 100)
            print(f"[DOCKING_PROGRESS] {{\"percent\": {percent_start}}}", flush=True)
            
            # 1. Generate mutants from current seeds
            all_mutant_smiles = []
            mutant_parents = {}
            
            for seed in current_seeds:
                try:
                    # Retrieve mutants from core CReM mutator
                    mutants = self.generation_engine.generate_mutants(
                        seed,
                        radius=2,
                        min_size=1,
                        max_size=5,
                        max_mutants=population_size
                    )
                    for m in mutants:
                        mut_smiles = m.mutant_smiles
                        if mut_smiles not in seen_compounds and mut_smiles != parent_smiles:
                            all_mutant_smiles.append(mut_smiles)
                            mutant_parents[mut_smiles] = seed
                except Exception as e:
                    logger.warning(f"CReM generation failed for seed {seed}: {e}")
            
            # Deduplicate mutant SMILES
            unique_mutants = list(set(all_mutant_smiles))
            
            # Limit population size per iteration (sort by first occurrence / convenience)
            unique_mutants = unique_mutants[:population_size]
            
            if not unique_mutants:
                logger.info("No new unique mutants generated. Ending early.")
                break
                
            # 2. Batch Dock mutants
            logger.info(f"Batch docking {len(unique_mutants)} mutants...")
            dock_results = await self.docking_service.dock_batch(
                receptor,
                unique_mutants,
                box_center,
                box_size,
                n_workers=os.cpu_count() or 4
            )
            
            total_docked_count += len(unique_mutants)
            
            # Build docking scores mapping
            dock_scores = {}
            dock_poses = {}
            for r in dock_results:
                dock_scores[r.smiles] = r.docking_score
                dock_poses[r.smiles] = r.poses
                
            # 3. Batch predict all Tier-1 property predictions
            logger.info("Running Tier-1 properties batch predictions...")
            pred_profiles = self._get_batch_predictions(unique_mutants)
            
            # 4. Compute composite and MPO safety scores
            # Prepare batch parameters for MPO scoring
            properties_list = []
            tice_list = []
            selectivity_list = []
            compounds_in = []
            
            for s in unique_mutants:
                prop = compute_properties_single(s)
                properties_list.append(prop)
                tice_list.append(check_tice_rules(prop))
                selectivity_list.append(compute_single_selectivity(s))
                compounds_in.append({"smiles": s})
                
            # Batch calculate resistance and toxicity
            resistance_list = resistance_batch(compounds_in)
            toxicity_list = toxicity_batch(compounds_in)
            
            # Calculate final MPO and composite scores
            iter_compounds = []
            for i, s in enumerate(unique_mutants):
                mpo_res = compute_mpo_score(
                    properties_list[i],
                    tice_list[i],
                    selectivity_list[i],
                    resistance_list[i],
                    toxicity_list[i],
                    weights
                )
                
                # Fetch docking score
                d_score = dock_scores.get(s, 0.0)
                
                # Combine docking (lower is better, e.g. -8.5) and MPO (higher is better, 0-10)
                # Composite score = MPO_score - 1.2 * docking_score
                # For failed/zero docking scores, penalize the compound
                composite = mpo_res["score"] - (1.2 * d_score if d_score < 0 else 0.0)
                
                gen_comp = GenerationCompound(
                    smiles=s,
                    docking_score=round(d_score, 2),
                    generation=iteration,
                    parent_in_generation=mutant_parents[s],
                    predicted_properties=pred_profiles.get(s, {}),
                    composite_score=round(composite, 2),
                    mpo_score=mpo_res["score"],
                    rank_category=mpo_res["rank_category"]
                )
                
                seen_compounds[s] = gen_comp
                iter_compounds.append(gen_comp)
                
            # Sort current iteration compounds by composite score
            iter_compounds.sort(key=lambda x: x.composite_score, reverse=True)
            iterations_records.append(IterationResult(iteration=iteration, compounds=iter_compounds))
            
            # Select top K compounds as seeds for next iteration
            current_seeds = [c.smiles for c in iter_compounds[:keep_top_n]]

        # Gather overall best compounds
        all_compounds = list(seen_compounds.values())
        all_compounds.sort(key=lambda x: x.composite_score, reverse=True)
        
        # Emits final docking progress
        print(f"[DOCKING_PROGRESS] {{\"percent\": 100}}", flush=True)
        
        elapsed = time.time() - start_time
        return CReMDockResult(
            parent_smiles=parent_smiles,
            receptor_id=receptor.receptor_hash,
            best_compounds=all_compounds,
            iterations=iterations_records,
            total_compounds_generated=len(seen_compounds),
            total_compounds_docked=total_docked_count,
            elapsed_seconds=round(elapsed, 2)
        )
