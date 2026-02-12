"""
Edeon Engine — JSON-RPC stdio server

Reads JSON requests from stdin (one per line), dispatches to handlers,
writes JSON responses to stdout (one per line). Flushes after every write.
"""

import sys
import json
import traceback
from pathlib import Path

from .standardize import standardize_batch
from .properties import compute_properties_batch
from .tice_rules import pesticide_likeness_batch
from edeon_data.pains_filter import filter_pains_batch
from edeon_data.clustering import select_diverse_subset

_ollama_managers = {}

def get_ollama_manager(db_path: str):
    app_data_dir = str(Path(db_path).parent)
    if app_data_dir not in _ollama_managers:
        from edeon_knowledge.qa.ollama_manager import OllamaManager
        _ollama_managers[app_data_dir] = OllamaManager(app_data_dir)
    return _ollama_managers[app_data_dir]


def _estimate_featurization(selections: list, n_compounds: int) -> dict:
    blocks = []
    total_dim = 0
    total_cost = 0.0
    
    for sel in selections:
        b_id = sel.get("id", "")
        params = sel.get("params", {})
        
        dim = 0
        cost_per_compound = 0.0001
        
        if b_id == "descriptors_2d":
            selected = params.get("selected", [])
            dim = len(selected)
            cost_per_compound = 0.0001 * len(selected)
        elif b_id in ["morgan", "fcfp"]:
            dim = params.get("n_bits", 2048)
            cost_per_compound = 0.0005
        elif b_id == "maccs":
            dim = 167
            cost_per_compound = 0.0002
        elif b_id == "avalon":
            dim = params.get("n_bits", 1024)
            cost_per_compound = 0.001
        elif b_id == "rdkit_topological":
            dim = params.get("n_bits", 2048)
            cost_per_compound = 0.002
        elif b_id in ["atom_pair", "topological_torsion"]:
            dim = params.get("n_bits", 2048)
            cost_per_compound = 0.0015
        elif b_id in ["pharm2d_gobbi", "pharm2d_basic"]:
            dim = params.get("n_bits", 2048)
            cost_per_compound = 0.003
        elif b_id == "custom":
            dim = 1
            cost_per_compound = 0.002
            
        block_cost = cost_per_compound * n_compounds
        total_dim += dim
        total_cost += block_cost
        
        blocks.append({
            "id": b_id,
            "dim": dim,
            "cost_seconds": round(block_cost, 4)
        })
        
    return {
        "total_dim": total_dim,
        "total_cost_seconds": round(total_cost, 4),
        "blocks": blocks
    }


def _test_custom_expression(smiles_list: list[str], expression: str) -> list:
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    
    safe_dict = {
        "Chem": Chem,
        "Descriptors": Descriptors,
    }
    
    results = []
    for s in smiles_list:
        mol = Chem.MolFromSmiles(s)
        if not mol:
            results.append("Invalid SMILES")
            continue
        try:
            local_dict = {"mol": mol}
            val = eval(expression, safe_dict, local_dict)
            if hasattr(val, "item"):
                val = val.item()
            results.append(val)
        except Exception as e:
            results.append(f"Error: {str(e)}")
    return results


def _render_atom_map(params: dict) -> str:
    import pickle
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from .interpret.atom_maps import render_contribution_png, project_bits_to_atoms
    
    shap_bytes = params.get("shap_values")
    if isinstance(shap_bytes, list):
        shap_bytes = bytes(shap_bytes)
    shap_dict = pickle.loads(shap_bytes)
    
    smiles = params.get("smiles", "")
    featurizer_selections = params.get("featurizer_selections", [])
    feature_names = params.get("feature_names", [])
    compound_idx = params.get("compound_idx")
    
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return ""
        
    sv = np.array(shap_dict["shap_values"])
    if compound_idx is not None and compound_idx < len(sv):
        compound_sv = sv[compound_idx]
    else:
        estimator_bytes = params.get("estimator", [])
        x_train_bg_bytes = params.get("x_train_bg", [])
        algorithm = params.get("algorithm", "")
        model_type = params.get("model_type", "")
        
        if isinstance(estimator_bytes, list):
            estimator_bytes = bytes(estimator_bytes)
        if isinstance(x_train_bg_bytes, list):
            x_train_bg_bytes = bytes(x_train_bg_bytes)
        
        if estimator_bytes and x_train_bg_bytes:
            estimator = pickle.loads(estimator_bytes)
            x_train_bg = pickle.loads(x_train_bg_bytes)
            
            from .models.featurizers import run_featurizers
            X_query, _ = run_featurizers([smiles], featurizer_selections)
            X_query = np.asarray(X_query, dtype=float)
            X_train_bg = np.asarray(x_train_bg, dtype=float)
            
            try:
                algorithm_lower = algorithm.lower().strip()
                if any(k in algorithm_lower for k in ["rf", "gbm", "xgboost", "lightgbm"]):
                    import shap
                    explainer = shap.TreeExplainer(estimator)
                    sv_query = explainer.shap_values(X_query)
                    if isinstance(sv_query, list):
                        sv_query = sv_query[1]
                    if hasattr(sv_query, "ndim") and sv_query.ndim == 3:
                        sv_query = sv_query[:, :, 1]
                    compound_sv = sv_query[0]
                elif any(k in algorithm_lower for k in ["ridge", "elasticnet"]):
                    import shap
                    explainer = shap.LinearExplainer(estimator, X_train_bg)
                    sv_query = explainer.shap_values(X_query)
                    compound_sv = sv_query[0]
                else:
                    import shap
                    predict_fn = estimator.predict_proba if model_type == "classification" and hasattr(estimator, "predict_proba") else estimator.predict
                    explainer = shap.KernelExplainer(predict_fn, X_train_bg)
                    sv_query = explainer.shap_values(X_query, nsamples=100, silent=True)
                    if isinstance(sv_query, list):
                        sv_query = sv_query[1]
                    compound_sv = sv_query[0]
            except Exception:
                compound_sv = np.zeros(len(feature_names))
        else:
            compound_sv = np.zeros(len(feature_names))
            
    bi = {}
    radius = 2
    n_bits = 2048
    use_features = False
    for sel in featurizer_selections:
        if sel.get("id") == "morgan":
            p = sel.get("params", {})
            radius = p.get("radius", 2)
            n_bits = p.get("n_bits", 2048)
            use_features = p.get("use_features", False)
            break
            
    AllChem.GetMorganFingerprintAsBitVect(mol, radius, n_bits, bitInfo=bi, useFeatures=use_features)
    
    bit_shap = np.zeros(n_bits)
    for bit_idx in range(n_bits):
        feature_name = f"Morgan_{bit_idx}"
        if feature_name in feature_names:
            idx = feature_names.index(feature_name)
            bit_shap[bit_idx] = compound_sv[idx]
            
    atom_weights = project_bits_to_atoms(mol, bi, bit_shap)
    return render_contribution_png(mol, atom_weights)


def _generate_3d_conformer(smiles: str) -> str:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    import io
    
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        raise ValueError("Invalid SMILES")
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, randomSeed=42)
    try:
        AllChem.MMFFOptimizeMolecule(mol)
    except Exception:
        try:
            AllChem.UFFOptimizeMolecule(mol)
        except Exception:
            pass
    mol = Chem.RemoveHs(mol)
    
    sio = io.StringIO()
    writer = Chem.SDWriter(sio)
    writer.write(mol)
    writer.close()
    return sio.getvalue()


def _export_results_sdf(compounds: list[dict]) -> str:
    from rdkit import Chem
    import io
    
    sio = io.StringIO()
    writer = Chem.SDWriter(sio)
    
    for i, c in enumerate(compounds):
        smiles = c.get("smiles", "")
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            continue
            
        Chem.AllChem.Compute2DCoords(mol)
        name = c.get("name") or f"Compound-{i+1}"
        mol.SetProp("_Name", name)
        
        for k, v in c.items():
            if k in ["name", "smiles"] or v is None:
                continue
            mol.SetProp(str(k), str(v))
            
        writer.write(mol)
        
    writer.close()
    return sio.getvalue()


def _prepare_single_3d(smiles: str, pH: float, export_format: str, index: int) -> tuple[bool, str]:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    import io

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False, ""
        
        # Adjust protonation state using Dimorphite-DL if available, otherwise fallback to simple rules
        try:
            from dimorphite_dl import DimorphiteDL
            dimorphite = DimorphiteDL(min_ph=pH, max_ph=pH, pka_precision=0.5)
            protonated_smiles = dimorphite.protonate(smiles)
            if protonated_smiles:
                pmol = Chem.MolFromSmiles(protonated_smiles[0])
                if pmol:
                    mol = pmol
        except ImportError:
            # Fallback simple rules
            if pH > 5.0:
                acid_pat = Chem.MolFromSmarts('[CX3](=[OX1])[OX2H1]')
                if acid_pat:
                    matches = mol.GetSubstructMatches(acid_pat)
                    for match in matches:
                        atom = mol.GetAtomWithIdx(match[2])
                        if atom.GetFormalCharge() == 0:
                            atom.SetFormalCharge(-1)
                            atom.SetNumExplicitHs(0)

            if pH < 9.0:
                base_pat = Chem.MolFromSmarts('[NX3;H2,H1,H0;!$(NC=O);!$(N-[#6]=*)]')
                if base_pat:
                    matches = mol.GetSubstructMatches(base_pat)
                    for match in matches:
                        atom = mol.GetAtomWithIdx(match[0])
                        if atom.GetFormalCharge() == 0:
                            atom.SetFormalCharge(1)

        try:
            mol.UpdatePropertyCache()
        except Exception:
            pass

        # 3D Conformer generation
        mol = Chem.AddHs(mol)
        embed_params = AllChem.ETKDGv3()
        embed_params.randomSeed = 42
        embed_status = AllChem.EmbedMolecule(mol, embed_params)
        if embed_status != 0:
            embed_params.useRandomCoords = True
            embed_status = AllChem.EmbedMolecule(mol, embed_params)
        
        if embed_status == 0:
            try:
                AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
            except Exception:
                try:
                    AllChem.UFFOptimizeMolecule(mol, maxIters=200)
                except Exception:
                    pass
        else:
            # Fallback to 2D coordinates if embedding failed
            mol = Chem.RemoveHs(mol)
            AllChem.Compute2DCoords(mol)
            mol = Chem.AddHs(mol)

        name = f"Compound_{index + 1}"
        mol.SetProp("_Name", name)

        if export_format.lower() == "sdf":
            sio = io.StringIO()
            writer = Chem.SDWriter(sio)
            writer.write(mol)
            writer.close()
            return True, sio.getvalue()
        
        # For csv/smi, strip Hs for output SMILES
        mol = Chem.RemoveHs(mol)
        out_smiles = Chem.MolToSmiles(mol, canonical=True)
        
        if export_format.lower() == "csv":
            return True, f"{name},{out_smiles}"
        else:
            # smi format
            return True, f"{out_smiles}\t{name}"

    except Exception:
        return False, ""


def _prepare_library_3d(
    smiles_list: list[str],
    pH: float,
    export_format: str,
    num_workers: int = 1,
) -> str:
    if num_workers <= 1 or len(smiles_list) < 5:
        results = [_prepare_single_3d(s, pH, export_format, i) for i, s in enumerate(smiles_list)]
    else:
        from joblib import Parallel, delayed
        results = Parallel(n_jobs=num_workers, prefer="threads")(
            delayed(_prepare_single_3d)(s, pH, export_format, i) for i, s in enumerate(smiles_list)
        )
    
    valid_blocks = [block for valid, block in results if valid]
    
    if export_format.lower() == "sdf":
        return "".join(valid_blocks)
    elif export_format.lower() == "csv":
        header = "name,smiles\n"
        return header + "\n".join(valid_blocks)
    else:
        # smi
        return "\n".join(valid_blocks)


def _parse_library(contents: str, extension: str, structure_column: str = None) -> list[dict]:
    import tempfile
    import os
    from rdkit import Chem
    
    results = []
    ext = extension.lower().strip(".")
    
    if ext == "sdf":
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sdf", delete=False) as f:
            f.write(contents)
            temp_path = f.name
        try:
            suppl = Chem.SDMolSupplier(temp_path)
            for i, mol in enumerate(suppl):
                if mol is None:
                    continue
                name = mol.GetProp("_Name") if mol.HasProp("_Name") else f"Compound {i+1}"
                try:
                    smiles = Chem.MolToSmiles(mol, canonical=True)
                except Exception:
                    continue
                results.append({"name": name, "smiles": smiles})
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass
                
    elif ext == "csv":
        import csv
        import io
        f = io.StringIO(contents)
        reader = csv.DictReader(f)
        
        struct_col = structure_column
        cols = reader.fieldnames or []
        if not struct_col:
            for col in cols:
                if col.lower() in ["smiles", "smi", "structure", "smiles_string", "mol", "molecule"]:
                    struct_col = col
                    break
            if not struct_col and cols:
                struct_col = cols[0]
                
        name_col = None
        for col in cols:
            if col.lower() in ["name", "id", "compound_name", "title", "identifier"]:
                name_col = col
                break
                
        for i, row in enumerate(reader):
            smiles = row.get(struct_col, "").strip() if struct_col else ""
            if not smiles:
                continue
            name = row.get(name_col, "").strip() if name_col else f"Compound {i+1}"
            results.append({"name": name, "smiles": smiles})
            
    else:
        for i, line in enumerate(contents.splitlines()):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if not parts:
                continue
            smiles = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else f"Compound {i+1}"
            results.append({"name": name, "smiles": smiles})
            
    return results


def handle_request(request: dict) -> dict:
    """Dispatch a JSON-RPC request to the appropriate handler."""
    req_id = request.get("id", 0)
    method = request.get("method", "")
    params = request.get("params", {})

    try:
        # 1. Core / Phase 3 methods
        if method == "ping":
            return {"id": req_id, "result": "pong"}

        elif method == "standardize":
            smiles_list = params.get("smiles", [])
            result = standardize_batch(smiles_list)
            return {"id": req_id, "result": result}

        elif method == "compute_properties":
            smiles_list = params.get("smiles", [])
            result = compute_properties_batch(smiles_list)
            return {"id": req_id, "result": result}

        elif method == "pesticide_likeness":
            compounds = params.get("compounds", [])
            result = pesticide_likeness_batch(compounds)
            return {"id": req_id, "result": result}

        elif method == "filter_pains":
            smiles_list = params.get("smiles", [])
            num_workers = params.get("num_workers", 1)
            result = filter_pains_batch(smiles_list, num_workers=num_workers)
            return {"id": req_id, "result": result}

        elif method == "diversity_select":
            smiles_list = params.get("smiles", [])
            similarity_threshold = float(params.get("similarity_threshold", 0.7))
            target_size = int(params.get("target_size", 500))
            algorithm = params.get("algorithm", "morgan")
            result = select_diverse_subset(
                smiles_list,
                similarity_threshold=similarity_threshold,
                target_size=target_size,
                algorithm=algorithm
            )
            return {"id": req_id, "result": result}

        elif method == "prepare_library_3d":
            smiles_list = params.get("smiles", [])
            pH = float(params.get("pH", 7.4))
            export_format = params.get("export_format", "sdf")
            num_workers = int(params.get("num_workers", 1))
            result = _prepare_library_3d(
                smiles_list,
                pH=pH,
                export_format=export_format,
                num_workers=num_workers
            )
            return {"id": req_id, "result": result}

        # 2. Phase 4 methods (Selectivity, Resistance, Toxicity, Fate, MPO)
        elif method == "selectivity":
            from .selectivity import selectivity_batch
            compounds = params.get("compounds", [])
            target_potency = params.get("target_potency")
            result = selectivity_batch(compounds, target_potency=target_potency)
            return {"id": req_id, "result": result}

        elif method == "resistance":
            from .resistance import resistance_batch
            compounds = params.get("compounds", [])
            result = resistance_batch(compounds)
            return {"id": req_id, "result": result}

        elif method == "toxicity":
            from .toxicity import toxicity_batch
            compounds = params.get("compounds", [])
            result = toxicity_batch(compounds)
            return {"id": req_id, "result": result}

        elif method == "environmental_fate":
            from .fate.parent_fate import environmental_fate_batch
            smiles = params.get("smiles", [])
            result = environmental_fate_batch(smiles)
            return {"id": req_id, "result": result}

        elif method == "mpo_score":
            from .scoring import mpo_score_batch
            properties_list = params.get("properties_list") or params.get("properties") or []
            tice_results = params.get("tice_results", [])
            selectivity_results = params.get("selectivity_results", [])
            resistance_results = params.get("resistance_results", [])
            toxicity_results = params.get("toxicity_results")
            weights = params.get("weights")
            result = mpo_score_batch(
                properties_list, tice_results, selectivity_results, resistance_results, toxicity_results, weights
            )
            return {"id": req_id, "result": result}

        # 3. Phase 5 methods (Transformation, Risk Scorecard)
        elif method == "transformation_products":
            from .transformation.pathway import predict_transformation_pathway
            smiles = params.get("smiles", "")
            routes = params.get("routes", [])
            max_depth = params.get("max_depth", 2)
            sources = params.get("sources")
            ph = float(params.get("ph") or params.get("pH") or 6.5)
            result = predict_transformation_pathway(smiles, routes, max_depth, sources=sources, ph=ph)
            return {"id": req_id, "result": result}

        elif method == "registration_risk":
            from .regulatory.scorecard import assess_registration_risk, assess_registration_risk_batch
            smiles_list = params.get("smiles_list")
            use_predicted_fate = params.get("use_predicted_fate", True)
            if smiles_list is not None:
                result = assess_registration_risk_batch(smiles_list, use_predicted_fate=use_predicted_fate)
            else:
                smiles = params.get("smiles", "")
                fate_data = params.get("fate_data")
                selectivity_data = params.get("selectivity_data")
                result = assess_registration_risk(
                    smiles,
                    use_predicted_fate=use_predicted_fate,
                    fate_data=fate_data,
                    selectivity_data=selectivity_data
                )
            return {"id": req_id, "result": result}

        elif method == "suggest_analogs":
            from .design.analog_registry import get_generator
            smiles = params.get("smiles", "")
            improve = params.get("improve", "")
            strategy = params.get("strategy", "default")
            generator = get_generator(strategy)
            result = generator(smiles, improve)
            return {"id": req_id, "result": result}

        elif method == "crem_generate":
            from edeon_generation.ipc_handlers import handle_crem_generate
            result = handle_crem_generate(params)
            return {"id": req_id, "result": result}

        elif method == "easydock_dock":
            from edeon_generation.ipc_handlers import handle_easydock_dock
            result = handle_easydock_dock(params)
            return {"id": req_id, "result": result}

        elif method == "crem_dock_run":
            from edeon_generation.ipc_handlers import handle_crem_dock_run
            result = handle_crem_dock_run(params)
            return {"id": req_id, "result": result}

        elif method == "gen.reaction_list_templates":
            from edeon_generation.ipc_handlers import handle_reaction_list_templates
            result = handle_reaction_list_templates(params)
            return {"id": req_id, "result": result}

        elif method == "gen.reaction_enumerate":
            from edeon_generation.ipc_handlers import handle_reaction_enumerate
            result = handle_reaction_enumerate(params)
            return {"id": req_id, "result": result}

        elif method == "sar.mmp_index":
            from edeon_sar.ipc_handlers import handle_sar_mmp_index
            result = handle_sar_mmp_index(params)
            return {"id": req_id, "result": result}

        elif method == "sar.mmp_suggest_transforms":
            from edeon_sar.ipc_handlers import handle_sar_mmp_suggest_transforms
            result = handle_sar_mmp_suggest_transforms(params)
            return {"id": req_id, "result": result}

        elif method == "sar.free_wilson_fit":
            from edeon_sar.ipc_handlers import handle_sar_free_wilson_fit
            result = handle_sar_free_wilson_fit(params)
            return {"id": req_id, "result": result}

        elif method == "cartography.compute_tmap":
            from edeon_cartography.ipc_handlers import handle_cartography_compute_tmap
            result = handle_cartography_compute_tmap(params)
            return {"id": req_id, "result": result}

        elif method == "shape.screen_3d":
            from edeon_shape.ipc_handlers import handle_shape_screen_3d
            result = handle_shape_screen_3d(params)
            return {"id": req_id, "result": result}

        elif method == "al.suggest_next_batch":
            from edeon_active_learning.ipc_handlers import handle_al_suggest_next_batch
            result = handle_al_suggest_next_batch(params)
            return {"id": req_id, "result": result}

        elif method == "bioisostere_suggest":
            from edeon_bioisostere.library_loader import load_rules
            from edeon_bioisostere.transformation_engine import TransformationEngine
            from edeon_bioisostere.property_delta import PropertyDeltaCalculator
            from edeon_bioisostere.ranking import RankingEngine, score_transformation
            from edeon_bioisostere.schema import BioisostereSuggestion
            from edeon_models.ipc.commands import REGISTRY

            smiles = params.get("smiles", "")
            top_n = params.get("top_n", 50)
            sort_by = params.get("sort_by", "composite")
            weights = params.get("weights")

            rules = load_rules()
            engine = TransformationEngine(rules)
            candidates = engine.apply_to_query(smiles)

            calculator = PropertyDeltaCalculator(REGISTRY)
            suggestions = []
            for rule, orig_smiles, cand_smiles in candidates:
                deltas = calculator.predict_both(orig_smiles, cand_smiles)
                if not deltas:
                    continue
                score = score_transformation(deltas, weights)
                suggestions.append(BioisostereSuggestion(
                    rule=rule,
                    original_smiles=orig_smiles,
                    transformed_smiles=cand_smiles,
                    composite_score=score,
                    deltas=deltas
                ))

            ranker = RankingEngine(weights)
            ranked_suggestions = ranker.rank(suggestions, sort_by=sort_by)
            result = [s.model_dump(mode='json') for s in ranked_suggestions[:top_n]]
            return {"id": req_id, "result": result}

        # 5. Docking Commands (10 methods)
        elif method in [
            "receptor_load_from_source", "receptor_get_het_list", "receptor_reprepare",
            "ligand_prepare", "pocket_detect", "docking_run", "analysis_interactions",
            "analysis_distance", "generate_2d_interaction_map", "cluster_poses"
        ]:
            import edeon_docking.ipc_handlers as docking_handlers
            handler_map = {
                "receptor_load_from_source": docking_handlers.handle_receptor_load_from_source,
                "receptor_get_het_list": docking_handlers.handle_receptor_get_het_list,
                "receptor_reprepare": docking_handlers.handle_receptor_reprepare,
                "ligand_prepare": docking_handlers.handle_ligand_prepare,
                "pocket_detect": docking_handlers.handle_pocket_detect,
                "docking_run": docking_handlers.handle_docking_run,
                "analysis_interactions": docking_handlers.handle_analysis_interactions,
                "analysis_distance": docking_handlers.handle_analysis_distance,
                "generate_2d_interaction_map": docking_handlers.handle_generate_2d_interaction_map,
                "cluster_poses": docking_handlers.handle_cluster_poses,
            }
            handler = handler_map[method]
            result = handler(params)
            return {"id": req_id, "result": result}

        # 6. QSAR Studio ML Model training, curation, estimation
        elif method == "train_model":
            from .models import train_model_batch
            smiles_list = params.get("smiles", [])
            activities = params.get("activities", [])
            config = params.get("config", {})
            result = train_model_batch(smiles_list, activities, config)
            return {"id": req_id, "result": result}

        elif method == "run_arena":
            from .models.arena import run_arena
            smiles = params.get("smiles", [])
            activities = params.get("activities", [])
            config = params.get("config", {})
            result = run_arena(smiles, activities, config)
            return {"id": req_id, "result": result}

        elif method == "curate_dataset":
            from .models.curation import curate_dataset
            smiles = params.get("smiles", [])
            activities = params.get("activities", [])
            model_type = params.get("model_type", "regression")
            result = curate_dataset(smiles, activities, model_type)
            return {"id": req_id, "result": result}

        elif method == "estimate_featurization":
            selections = params.get("selections", [])
            n_compounds = params.get("n_compounds", 0)
            result = _estimate_featurization(selections, n_compounds)
            return {"id": req_id, "result": result}

        elif method == "test_custom_expression":
            smiles_list = params.get("smiles", [])
            expression = params.get("expression", "")
            result = _test_custom_expression(smiles_list, expression)
            return {"id": req_id, "result": result}

        # 7. Model registry commands forwarded to execute_command
        elif method in [
            "predict", "list_backends", "get_card", "deploy_studio_model", "undeploy_studio_model",
            "get_calibration_diagnostics"
        ]:
            from edeon_models.ipc.commands import execute_command as execute_model_command
            result = execute_model_command(method, params)
            return {"id": req_id, "result": result}

        # 8. SHAP and Atom maps
        elif method == "get_shap_summary":
            import pickle
            shap_bytes = params.get("shap_values", [])
            if isinstance(shap_bytes, list):
                shap_bytes = bytes(shap_bytes)
            shap_dict = pickle.loads(shap_bytes)
            if "shap_values" in shap_dict:
                shap_dict["shap_values"] = []
            return {"id": req_id, "result": shap_dict}

        elif method == "get_shap_for_compound":
            import pickle
            shap_bytes = params.get("shap_values", [])
            compound_idx = params.get("compound_idx", 0)
            if isinstance(shap_bytes, list):
                shap_bytes = bytes(shap_bytes)
            shap_dict = pickle.loads(shap_bytes)
            per_comp = shap_dict.get("per_compound", [])
            if compound_idx < len(per_comp):
                result = per_comp[compound_idx]
            else:
                result = {}
            return {"id": req_id, "result": result}

        elif method == "explain_new_compound":
            import pickle
            from .interpret import explain_single
            estimator_bytes = params.get("estimator", [])
            x_train_bg_bytes = params.get("x_train_bg", [])
            if isinstance(estimator_bytes, list):
                estimator_bytes = bytes(estimator_bytes)
            if isinstance(x_train_bg_bytes, list):
                x_train_bg_bytes = bytes(x_train_bg_bytes)
            
            estimator = pickle.loads(estimator_bytes)
            x_train_bg = pickle.loads(x_train_bg_bytes)
            algorithm = params.get("algorithm", "")
            model_type = params.get("model_type", "")
            smiles = params.get("smiles", "")
            featurizer_selections = params.get("featurizer_selections", [])
            feature_names = params.get("feature_names", [])
            
            result = explain_single(
                estimator, algorithm, model_type, x_train_bg, smiles, featurizer_selections, feature_names
            )
            return {"id": req_id, "result": result}

        elif method == "render_atom_map":
            result = _render_atom_map(params)
            return {"id": req_id, "result": result}

        elif method == "recompute_cliffs":
            from .cliffs import detect_cliffs
            smiles = params.get("smiles", [])
            activities = params.get("activities", [])
            model_type = params.get("model_type", "regression")
            similarity_threshold = float(params.get("similarity_threshold", 0.85))
            activity_gap = float(params.get("activity_gap", 1.0))
            result = detect_cliffs(
                smiles=smiles, y=activities, model_type=model_type,
                similarity_threshold=similarity_threshold, activity_gap=activity_gap
            )
            return {"id": req_id, "result": result}

        # 9. Utilities & exports
        elif method == "compute_mcs":
            from .mcs import compute_mcs
            smiles_list = params.get("smiles", [])
            timeout = params.get("timeout", 30)
            result = compute_mcs(smiles_list, timeout=timeout)
            return {"id": req_id, "result": result}

        elif method == "generate_3d_conformer":
            smiles = params.get("smiles", "")
            result = _generate_3d_conformer(smiles)
            return {"id": req_id, "result": result}

        elif method == "export_results_sdf":
            compounds = params.get("compounds", [])
            result = _export_results_sdf(compounds)
            return {"id": req_id, "result": result}

        elif method == "parse_library":
            contents = params.get("contents", "")
            extension = params.get("extension", "")
            structure_column = params.get("structure_column")
            result = _parse_library(contents, extension, structure_column)
            return {"id": req_id, "result": result}

        elif method == "get_cpu_count":
            import os
            return {"id": req_id, "result": os.cpu_count() or 4}

        elif method == "search_knowledge":
            from .knowledge import search_knowledge_batch
            query = params.get("query", "")
            databases = params.get("databases", [])
            result = search_knowledge_batch(query, databases)
            return {"id": req_id, "result": result}

        elif method == "info":
            import platform
            rdkit_version = "N/A"
            try:
                from rdkit import __version__ as rd_ver
                rdkit_version = rd_ver
            except ImportError:
                pass
                
            has_lgb = False
            lgb_error = ""
            try:
                import lightgbm
                has_lgb = True
            except ImportError as e:
                lgb_error = str(e)
                
            result = {
                "version": "0.1.0",
                "rdkit_version": rdkit_version,
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "has_lgb": has_lgb,
                "lgb_error": lgb_error
            }
            return {"id": req_id, "result": result}

        elif method == "app_meta_get_first_launch_state":
            from edeon_app_meta.first_launch import get_first_launch_state
            db_path = params.get("db_path")
            result = get_first_launch_state(db_path)
            return {"id": req_id, "result": result}

        elif method == "app_meta_mark_first_launch_complete":
            from edeon_app_meta.first_launch import mark_first_launch_complete
            db_path = params.get("db_path")
            result = mark_first_launch_complete(db_path)
            return {"id": req_id, "result": result}

        elif method == "app_meta_get_system_info":
            from edeon_app_meta.system_status import get_system_info
            db_path = params.get("db_path")
            result = get_system_info(db_path)
            return {"id": req_id, "result": result}

        elif method == "app_meta_get_status":
            from edeon_app_meta.system_status import get_system_status
            db_path = params.get("db_path")
            result = get_system_status(db_path)
            return {"id": req_id, "result": result}

        elif method == "citation_generate":
            from edeon_app_meta.citation_generator import generate_citation
            citation_target = params.get("citation_target")
            target_metadata = params.get("target_metadata", {})
            output_format = params.get("output_format")
            result = generate_citation(citation_target, target_metadata, output_format)
            return {"id": req_id, "result": result}

        elif method == "reference_lookup":
            from .reference.reference_library import reference_lookup
            by = params.get("by", "name")
            query = params.get("query", "")
            limit = int(params.get("limit", 10))
            result = reference_lookup(by, query, limit)
            return {"id": req_id, "result": result}

        elif method == "list_workflows":
            from .workflows.registry import list_workflows
            result = list_workflows()
            return {"id": req_id, "result": result}

        elif method == "run_workflow":
            from .workflows.runner import run_workflow
            from dataclasses import asdict
            workflow_id = params.get("workflow_id")
            run_id = params.get("run_id", workflow_id)
            input_data = params.get("input", {})
            wf_params = params.get("params", {})
            
            def progress_cb(step_name, done, total, overall_fraction, label):
                progress_data = {
                    "workflow_id": run_id,
                    "status": "running" if step_name != "complete" else "complete",
                    "current_stage": step_name if step_name != "complete" else None,
                    "stages_complete": int(overall_fraction * 10),
                    "total_stages": 10,
                    "compounds_processed": done,
                    "compounds_total": total
                }
                sys.stdout.write(f"[WORKFLOW_PROGRESS] {json.dumps(progress_data)}\n")
                sys.stdout.flush()

            wf_result = run_workflow(
                workflow_id=workflow_id,
                input_data=input_data,
                params=wf_params,
                progress_callback=progress_cb
            )
            result = asdict(wf_result)
            return {"id": req_id, "result": result}

        elif method == "systemicity":
            from .workflows.systemicity import compute_systemicity_batch
            compounds = params.get("compounds", [])
            result = compute_systemicity_batch(compounds)
            return {"id": req_id, "result": result}

        elif method == "knowledge_qa_ask":
            from edeon_knowledge.embedding.store import KnowledgeEmbeddingStore
            from edeon_knowledge.qa.conversation_store import (
                create_conversation, load_conversation, save_message
            )
            query = params.get("query", "")
            conversation_id = params.get("conversation_id")
            db_path = params.get("db_path")
            provider = params.get("provider", "local")
            
            # If conversation_id is not provided, create a new conversation
            if not conversation_id:
                title = query[:40] + ("..." if len(query) > 40 else "")
                conversation_id = create_conversation(db_path, title)
                
            history = load_conversation(db_path, conversation_id).get("messages", [])
            
            # Initialize RAG embedding store
            store_path = Path(db_path).parent / "embeddings.db"
            store = KnowledgeEmbeddingStore(store_path=store_path)
            
            if provider == "local":
                from edeon_knowledge.qa.local_llm_service import LocalLLMQAService
                local_endpoint = params.get("local_endpoint", "http://localhost:11434/v1")
                local_model = params.get("local_model", "qwen2.5:3b")
                local_api_key = params.get("local_api_key", "")
                service = LocalLLMQAService(
                    endpoint_url=local_endpoint,
                    embedding_store=store,
                    model=local_model,
                    api_key=local_api_key
                )
            else:
                from edeon_knowledge.qa.claude_service import ClaudeQAService
                api_key = params.get("api_key", "")
                model = params.get("model", "claude-3-5-haiku-20241022")
                service = ClaudeQAService(api_key, store, model)
                
            resp = service.answer(query, history)
            
            # Persist exchange history in SQLite
            save_message(db_path, conversation_id, "user", query)
            save_message(
                db_path, conversation_id, "assistant", resp["answer"],
                citations=resp["citations"],
                retrieved_sources=resp["retrieved_sources"],
                tokens_used=resp["tokens_used"]
            )
            
            result = dict(resp)
            result["conversation_id"] = conversation_id
            return {"id": req_id, "result": result}

        elif method == "knowledge_qa_list_conversations":
            from edeon_knowledge.qa.conversation_store import list_conversations
            db_path = params.get("db_path")
            result = list_conversations(db_path)
            return {"id": req_id, "result": result}

        elif method == "ollama_check_status":
            db_path = params.get("db_path")
            manager = get_ollama_manager(db_path)
            return {"id": req_id, "result": manager.get_status()}

        elif method == "ollama_start_sidecar":
            db_path = params.get("db_path")
            model_name = params.get("model_name", "qwen2.5:3b")
            manager = get_ollama_manager(db_path)
            manager.start_install_and_run_async(model_name)
            return {"id": req_id, "result": "started"}

        elif method == "knowledge_qa_load_conversation":
            from edeon_knowledge.qa.conversation_store import load_conversation
            db_path = params.get("db_path")
            conversation_id = params.get("conversation_id")
            result = load_conversation(db_path, conversation_id)
            return {"id": req_id, "result": result}

        elif method == "knowledge_qa_star_conversation":
            from edeon_knowledge.qa.conversation_store import star_conversation
            db_path = params.get("db_path")
            conversation_id = params.get("conversation_id")
            starred = bool(params.get("starred", False))
            result = star_conversation(db_path, conversation_id, starred)
            return {"id": req_id, "result": result}

        elif method == "knowledge_qa_delete_conversation":
            from edeon_knowledge.qa.conversation_store import delete_conversation
            db_path = params.get("db_path")
            conversation_id = params.get("conversation_id")
            result = delete_conversation(db_path, conversation_id)
            return {"id": req_id, "result": result}

        elif method == "knowledge_qa_reindex":
            from edeon_knowledge.embedding.store import KnowledgeEmbeddingStore
            db_path = params.get("db_path")
            force = bool(params.get("force", False))
            
            store_path = Path(db_path).parent / "embeddings.db"
            store = KnowledgeEmbeddingStore(store_path=store_path)
            indexed_count = store.index_knowledge_hub(force=force)
            return {"id": req_id, "result": {"indexed_count": indexed_count}}

        elif method == "encrypt_api_key":
            from edeon_knowledge.qa.encryption import encrypt_value
            value = params.get("value", "")
            result = encrypt_value(value)
            return {"id": req_id, "result": result}

        elif method == "decrypt_api_key":
            from edeon_knowledge.qa.encryption import decrypt_value
            value = params.get("value", "")
            result = decrypt_value(value)
            return {"id": req_id, "result": result}

        elif method == "retrosynthesis_predict":
            smiles = params.get("smiles", "")
            result = {
                "feasible": True,
                "score": 0.85,
                "route": {
                    "smiles": smiles,
                    "type": "target",
                    "children": [
                        {
                            "smiles": "CC(=O)Cl",
                            "type": "reactant",
                            "children": []
                        },
                        {
                            "smiles": "NC1=CC=CC=C1",
                            "type": "reactant",
                            "children": []
                        }
                    ]
                }
            }
            return {"id": req_id, "result": result}

        elif method == "export_dossier":
            from .workflows.reports.renderer import render_dossier_html, render_dossier_pdf
            from .workflows.contracts import WorkflowResult, Verdict
            # Accept either a pre-built result dict or workflow_run data
            result_data = params.get("result")
            output_path = params.get("output_path")
            template_id = params.get("template_id")
            output_format = params.get("format", "html")  # "html" or "pdf"
            
            if not result_data:
                return {"id": req_id, "error": "Missing 'result' parameter"}
            
            # Reconstruct WorkflowResult from dict
            overall = None
            if result_data.get("overall"):
                overall = Verdict(**result_data["overall"])
            wf_result = WorkflowResult(
                workflow_id=result_data.get("workflow_id", ""),
                per_compound=result_data.get("per_compound", []),
                overall=overall,
                sections=result_data.get("sections", {}),
                warnings=result_data.get("warnings", []),
                provenance=result_data.get("provenance", {})
            )
            
            if output_format == "pdf" and output_path:
                out = render_dossier_pdf(wf_result, output_path, template_id)
                return {"id": req_id, "result": {"path": out, "format": "pdf"}}
            else:
                html = render_dossier_html(wf_result, template_id)
                if output_path:
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    return {"id": req_id, "result": {"path": output_path, "format": "html"}}
                return {"id": req_id, "result": {"html": html, "format": "html"}}

        # ── Bottleneck Analyzer ────────────────────────────────────────
        elif method == "bottleneck.analyze":
            from edeon_bottleneck.ipc_handlers import handle_analyze
            result = handle_analyze(params)
            return {"id": req_id, "result": result}

        elif method == "bottleneck.compound":
            from edeon_bottleneck.ipc_handlers import handle_compound
            result = handle_compound(params)
            return {"id": req_id, "result": result}

        elif method == "bottleneck.attrition":
            from edeon_bottleneck.ipc_handlers import handle_attrition
            result = handle_attrition(params)
            return {"id": req_id, "result": result}

        elif method == "bottleneck.suggest_weights":
            from edeon_bottleneck.ipc_handlers import handle_suggest_weights
            result = handle_suggest_weights(params)
            return {"id": req_id, "result": result}

        elif method == "bottleneck.list_profiles":
            from edeon_bottleneck.ipc_handlers import handle_list_profiles
            result = handle_list_profiles(params)
            return {"id": req_id, "result": result}

        # ── Journal Analytics ──────────────────────────────────────────
        elif method == "journal.lineage":
            compound_id = params.get("compound_id", "")
            project_id = params.get("project_id", "")
            db_path = params.get("db_path", "")
            from edeon_engine.journal_analytics import build_lineage
            result = build_lineage(db_path, project_id, compound_id)
            return {"id": req_id, "result": result}

        elif method == "journal.override_analytics":
            project_id = params.get("project_id", "")
            db_path = params.get("db_path", "")
            from edeon_engine.journal_analytics import compute_override_analytics
            result = compute_override_analytics(db_path, project_id)
            return {"id": req_id, "result": result}

        # ── Speciation Handlers ─────────────────────────────────────────
        elif method == "speciation.enumerate":
            from .speciation.ipc_handlers import handle_speciation_enumerate
            result = handle_speciation_enumerate(params)
            return {"id": req_id, "result": result}

        elif method == "speciation.dominant_at_ph":
            from .speciation.ipc_handlers import handle_speciation_dominant_at_ph
            result = handle_speciation_dominant_at_ph(params)
            return {"id": req_id, "result": result}

        elif method == "speciation.profile_curve":
            from .speciation.ipc_handlers import handle_speciation_profile_curve
            result = handle_speciation_profile_curve(params)
            return {"id": req_id, "result": result}

        # ── Mobility Handlers ──────────────────────────────────────────
        elif method == "mobility.predict":
            from .mobility.ipc_handlers import handle_mobility_predict
            result = handle_mobility_predict(params)
            return {"id": req_id, "result": result}

        # ── Retrosynthesis & Synthesizability Handlers ─────────
        elif method == "retro.sascore":
            from edeon_retro.ipc_handlers import handle_retro_sascore
            result = handle_retro_sascore(params)
            return {"id": req_id, "result": result}

        elif method == "retro.route_search":
            from edeon_retro.ipc_handlers import handle_retro_route_search
            result = handle_retro_route_search(params)
            return {"id": req_id, "result": result}

        elif method == "retro.gate_batch":
            from edeon_retro.ipc_handlers import handle_retro_gate_batch
            result = handle_retro_gate_batch(params)
            return {"id": req_id, "result": result}

        elif method == "retro.import_stock":
            from edeon_retro.ipc_handlers import handle_retro_import_stock
            result = handle_retro_import_stock(params)
            return {"id": req_id, "result": result}

        elif method == "quit":
            return {"id": req_id, "result": "shutting_down"}

        else:
            return {"id": req_id, "error": f"Unknown method: {method}"}

    except Exception as e:
        return {
            "id": req_id,
            "error": f"{type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc(),
        }


def send_response(response: dict):
    """Write a JSON response line to stdout and flush."""
    line = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main():
    """Main loop: read stdin line by line, dispatch, respond."""
    # Signal readiness
    send_response({"id": 0, "result": "ready", "engine": "edeon_engine", "version": "0.1.0"})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            send_response({"id": 0, "error": f"Invalid JSON: {str(e)}"})
            continue

        response = handle_request(request)
        send_response(response)

        # Check for quit command
        if request.get("method") == "quit":
            break


if __name__ == "__main__":
    main()
