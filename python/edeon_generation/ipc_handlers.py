import asyncio
from typing import Dict, Any, List

from edeon_docking.ipc_handlers import receptor_service
from .crem_engine import CReMGenerationEngine
from .easydock_wrapper import EasyDockService
from .crem_dock import CReMDockPipeline

# Initialize services
generation_engine = CReMGenerationEngine()
easydock_service = EasyDockService()
crem_dock_pipeline = CReMDockPipeline()

def handle_crem_generate(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate mutants for a parent molecule using CReM core."""
    smiles = params.get("smiles", "")
    radius = int(params.get("radius", 2))
    min_size = int(params.get("min_size", 1))
    max_size = int(params.get("max_size", 5))
    max_mutants = int(params.get("max_mutants", 50))
    
    mutants = generation_engine.generate_mutants(
        parent_smiles=smiles,
        radius=radius,
        min_size=min_size,
        max_size=max_size,
        max_mutants=max_mutants
    )
    
    # Return serialized GenerationResult dataclasses
    from dataclasses import asdict
    return [asdict(m) for m in mutants]

def handle_easydock_dock(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run batch virtual screening using EasyDock."""
    receptor_hash = params.get("receptor_hash", "")
    ligand_smiles = params.get("smiles", [])
    box_center = params.get("box_center", (0.0, 0.0, 0.0))
    box_size = params.get("box_size", (20.0, 20.0, 20.0))
    engine = params.get("engine", "vina")
    
    # Retrieve prepared receptor from docking cache
    receptor = receptor_service.get_cached(receptor_hash)
    if not receptor:
        raise ValueError(f"Prepared receptor not found in cache for hash: {receptor_hash}")
        
    box_center_tuple = (float(box_center[0]), float(box_center[1]), float(box_center[2]))
    box_size_tuple = (float(box_size[0]), float(box_size[1]), float(box_size[2]))
    
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(
        easydock_service.dock_batch(
            receptor=receptor,
            ligand_smiles=ligand_smiles,
            box_center=box_center_tuple,
            box_size=box_size_tuple,
            engine=engine
        )
    )
    
    from dataclasses import asdict
    return [asdict(r) for r in results]

def handle_crem_dock_run(params: Dict[str, Any]) -> Dict[str, Any]:
    """Run closed-loop de novo design generation + docking + T1 safety scoring."""
    smiles = params.get("smiles", "")
    receptor_hash = params.get("receptor_hash", "")
    box_center = params.get("box_center", (0.0, 0.0, 0.0))
    box_size = params.get("box_size", (20.0, 20.0, 20.0))
    n_iterations = int(params.get("n_iterations", 3))
    population_size = int(params.get("population_size", 20))
    keep_top_n = int(params.get("keep_top_n", 5))
    weights = params.get("weights")
    
    # Retrieve prepared receptor
    receptor = receptor_service.get_cached(receptor_hash)
    if not receptor:
        raise ValueError(f"Prepared receptor not found in cache for hash: {receptor_hash}")
        
    box_center_tuple = (float(box_center[0]), float(box_center[1]), float(box_center[2]))
    box_size_tuple = (float(box_size[0]), float(box_size[1]), float(box_size[2]))
    
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        crem_dock_pipeline.run(
            parent_smiles=smiles,
            receptor=receptor,
            box_center=box_center_tuple,
            box_size=box_size_tuple,
            n_iterations=n_iterations,
            population_size=population_size,
            keep_top_n=keep_top_n,
            weights=weights
        )
    )
    
    from dataclasses import asdict
    return asdict(result)


def handle_reaction_list_templates(params: Dict[str, Any]) -> Dict[str, Any]:
    """List available RDKit reaction SMARTS templates."""
    from .reaction_enum import load_reaction_templates
    templates = load_reaction_templates()
    return {
        "ok": True,
        "templates": [
            {
                "id": t["id"],
                "name": t["name"],
                "smarts": t["smarts"],
                "description": t.get("description", ""),
                "n_reagent_slots": t.get("n_reagent_slots", 2)
            }
            for t in templates
        ]
    }


def handle_reaction_enumerate(params: Dict[str, Any]) -> Dict[str, Any]:
    """Run combinatorial reaction product enumeration."""
    from .reaction_enum import enumerate_reaction_products
    template_id = params.get("template_id", "amide_coupling")
    core_smiles = params.get("core_smiles")
    reagents = params.get("reagent_catalogs") or params.get("reagents")
    max_products = int(params.get("max_products", 500))
    apply_filters = params.get("apply_filters")
    retro_gate = params.get("retro_gate")

    return enumerate_reaction_products(
        template_id=template_id,
        core_smiles=core_smiles,
        reagents=reagents,
        max_products=max_products,
        apply_filters=apply_filters,
        retro_gate=retro_gate
    )
