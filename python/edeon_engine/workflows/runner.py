import logging
from typing import Any, Callable, Dict, List
from joblib import Parallel, delayed

from .contracts import WorkflowSpec, Step, WorkflowResult, Verdict
from .registry import REGISTRY
from .provenance import build_provenance_manifest

logger = logging.getLogger("edeon_workflows")

def resolve_value(val: Any, step_outputs: dict, input_data: dict, params: dict, context: dict = None) -> Any:
    """
    Resolves $ parameter references:
      - $input.field -> input_data.get(field)
      - $params.field -> params.get(field)
      - $context.field -> context.get(field) if context else None
      - $step.field -> maps outputs from the specified step
    """
    if isinstance(val, str) and val.startswith("$"):
        expr = val[1:]
        if expr == "survivors.smiles":
            std_parents = step_outputs.get("standardize", [])
            surv_idx = context.get("surviving_indices") if context else None
            if surv_idx is not None and isinstance(std_parents, list):
                return [std_parents[i]["canonical"] for i in sorted(surv_idx) if i < len(std_parents) and isinstance(std_parents[i], dict) and std_parents[i].get("valid")]
            if isinstance(std_parents, list):
                return [item["canonical"] for item in std_parents if isinstance(item, dict) and item.get("valid")]
            return []
        elif expr.startswith("input."):
            field = expr[len("input."):]
            return input_data.get(field)
        elif expr.startswith("params."):
            field = expr[len("params."):]
            return params.get(field)
        elif expr.startswith("context."):
            field = expr[len("context."):]
            return context.get(field) if context else None
        else:
            parts = expr.split(".")
            step_name = parts[0]
            step_res = step_outputs.get(step_name)
            if step_res is None:
                return None
            if len(parts) > 1:
                field = parts[1]
                if isinstance(step_res, list):

                    idx = context.get("index") if context else None
                    if idx is not None and 0 <= idx < len(step_res):
                        item = step_res[idx]
                        if item is None:
                            return None
                        if isinstance(item, dict):
                            if field in item:
                                return item[field]
                            elif "result" in item and isinstance(item["result"], list):
                                return [tp[field] for tp in item["result"] if isinstance(tp, dict) and field in tp]
                        elif isinstance(item, str) and field == "smiles":
                            return item
                        return None
                    else:
                        res_list = []
                        for item in step_res:
                            if item is None:
                                continue
                            if isinstance(item, dict):
                                if field in item:
                                    res_list.append(item[field])
                                elif "result" in item and isinstance(item["result"], list):
                                    for tp in item["result"]:
                                        if isinstance(tp, dict) and field in tp:
                                            res_list.append(tp[field])
                            elif isinstance(item, str) and field == "smiles":
                                res_list.append(item)
                        # Deduplicate smiles for unique list fanning
                        return list(set(res_list)) if field == "smiles" else res_list
                elif isinstance(step_res, dict):
                    return step_res.get(field)
            else:
                if isinstance(step_res, list):
                    idx = context.get("index") if context else None
                    if idx is not None and 0 <= idx < len(step_res):
                        return step_res[idx]
            return step_res


    elif isinstance(val, dict):
        return {k: resolve_value(v, step_outputs, input_data, params, context) for k, v in val.items()}
    elif isinstance(val, list):
        return [resolve_value(v, step_outputs, input_data, params, context) for v in val]
    return val

def _execute_rpc_method(method: str, params: dict) -> Any:
    """Calls the engine's main handle_request loop to run the underlying method."""
    from edeon_engine.__main__ import handle_request
    response = handle_request({"id": 1, "method": method, "params": params})
    if "error" in response and response["error"] is not None:
        raise RuntimeError(f"Engine method '{method}' failed: {response['error']}")
    return response.get("result")

def run_workflow(
    workflow_id: str,
    input_data: dict,
    params: dict = None,
    progress_callback: Callable = None
) -> WorkflowResult:
    """
    Executes a named declarative workflow step-by-step.
    """
    spec = REGISTRY.get(workflow_id)
    if not spec:
        raise ValueError(f"Workflow '{workflow_id}' not found in registry.")

    # Merge default params with overrides
    merged_params = {**spec.default_params, **(params or {})}
    
    step_outputs = {}
    total_steps = len(spec.steps)
    
    # Track parent smiles list for input validation and standardize mapping
    parent_smiles = input_data.get("smiles", [])
    if isinstance(parent_smiles, str):
        parent_smiles = [parent_smiles]

    surviving_indices = None
    attrition_log = []

    for idx, step in enumerate(spec.steps):
        logger.info(f"Running step {idx+1}/{total_steps}: {step.name} ({step.method})")
        
        if progress_callback:
            overall_fraction = idx / total_steps
            progress_callback(step.name, 0, 100, overall_fraction, f"Running {step.name}...")

        try:
            if step.applies_to == "parent":
                ctx = {"surviving_indices": surviving_indices}
                resolved = resolve_value(step.params, step_outputs, input_data, merged_params, ctx)
                step_outputs[step.name] = _execute_rpc_method(step.method, resolved)

                
            elif step.applies_to == "each_compound":
                # Get standardized parent smiles or fall back to inputs
                std_parents = step_outputs.get("standardize")
                smiles_list = []
                if isinstance(std_parents, list):
                    smiles_list = [item["canonical"] for item in std_parents if isinstance(item, dict) and item.get("valid")]
                else:
                    smiles_list = parent_smiles
                
                N = len(smiles_list)
                if surviving_indices is None:
                    surviving_indices = set(range(N))
                
                in_count = len(surviving_indices)
                
                def run_single_comp(s, comp_idx):
                    if comp_idx not in surviving_indices:
                        return None
                    ctx = {"smiles": s, "index": comp_idx}
                    resolved = resolve_value(step.params, step_outputs, input_data, merged_params, ctx)
                    return _execute_rpc_method(step.method, resolved)
                
                # Parallel execution
                n_jobs = merged_params.get("num_workers", 1)
                results = Parallel(n_jobs=n_jobs, prefer="threads")(
                    delayed(run_single_comp)(s, i) for i, s in enumerate(smiles_list)
                )
                step_outputs[step.name] = results
                
                # Evaluate gating if this step is a gate
                if step.gate:
                    for i in list(surviving_indices):
                        res = results[i]
                        if isinstance(res, list) and len(res) == 1:
                            res = res[0]
                        dropped = False
                        reason_detail = ""

                        
                        if res is None:
                            dropped = True
                            reason_detail = "Execution failed"
                        elif step.method == "pesticide_likeness":
                            level = res.get("level")
                            if level == "Low":
                                dropped = True
                                violations = res.get("violations", [])
                                reason_detail = f"Low likeness (violations: {', '.join(violations)})"
                        elif step.method == "filter_pains":
                            pains = res.get("pains", False)
                            reactive = res.get("reactive", False)
                            if pains or reactive:
                                dropped = True
                                reasons_list = []
                                if pains:
                                    reasons_list.append("PAINS")
                                if reactive:
                                    reasons_list.append("reactive alert")
                                reason_detail = f"Flagged: {', '.join(reasons_list)}"
                                
                        if dropped:
                            surviving_indices.remove(i)
                    
                    out_count = len(surviving_indices)
                    dropped_count = in_count - out_count
                    attrition_log.append({
                        "stage": step.name,
                        "in": in_count,
                        "out": out_count,
                        "dropped": dropped_count,
                        "reason": f"Failed {step.name} criteria"
                    })
                
            elif step.applies_to == "each_tp":
                # Find all unique TPs generated from the previous steps
                tp_smiles_list = resolve_value("$transformation_products.smiles", step_outputs, input_data, merged_params)
                # For W4 we might also have $suggest_analogs.smiles
                if not tp_smiles_list:
                    tp_smiles_list = resolve_value("$suggest_analogs.smiles", step_outputs, input_data, merged_params)
                if not tp_smiles_list:
                    tp_smiles_list = []
                
                def run_single_tp(s, tp_idx):
                    ctx = {"smiles": s, "index": tp_idx}
                    resolved = resolve_value(step.params, step_outputs, input_data, merged_params, ctx)
                    return _execute_rpc_method(step.method, resolved)
                
                n_jobs = merged_params.get("num_workers", 1)
                results = Parallel(n_jobs=n_jobs, prefer="threads")(
                    delayed(run_single_tp)(s, i) for i, s in enumerate(tp_smiles_list)
                )
                step_outputs[step.name] = results
                
        except Exception as e:
            logger.error(f"Step '{step.name}' failed: {e}")
            if step.on_fail == "abort":
                raise e
            elif step.on_fail == "warn":
                step_outputs[step.name] = None
            else: # skip
                continue

    # Invoke aggregator
    result = spec.aggregator(step_outputs, merged_params)
    
    # Attach provenance
    result.provenance = build_provenance_manifest(workflow_id, merged_params, parent_smiles)
    
    # Attach attrition if present
    if attrition_log:
        if not result.sections:
            result.sections = {}
        result.sections["attrition"] = attrition_log
        
    if progress_callback:
        progress_callback("complete", 100, 100, 1.0, "Workflow complete!")
        
    return result

