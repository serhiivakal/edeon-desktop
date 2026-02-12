"""
Edeon Engine — Custom Descriptor
Evaluates restricted free-text Python molecular property expressions.
"""

import numpy as np
import math
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors, Lipinski, Crippen
from .base import FeaturizerSpec, register

SAFE_NAMES = {"Chem", "Descriptors", "rdMolDescriptors", "Lipinski", "Crippen", "math", "mol"}
SAFE_MODULES = {
    "Chem": Chem,
    "Descriptors": Descriptors,
    "rdMolDescriptors": rdMolDescriptors,
    "Lipinski": Lipinski,
    "Crippen": Crippen,
    "math": math,
}

# Dynamically populate SAFE_NAMES with public attributes of safe modules and standard rdkit classes
for module in SAFE_MODULES.values():
    for attr in dir(module):
        if not attr.startswith("_"):
            SAFE_NAMES.add(attr)

for cls in [Chem.Mol, Chem.Atom, Chem.Bond]:
    for attr in dir(cls):
        if not attr.startswith("_"):
            SAFE_NAMES.add(attr)

# Add basic python builtins that are safe for math/list expressions
SAFE_BUILTINS = {"len", "float", "int", "list", "range", "tuple", "dict", "sum", "abs", "min", "max", "round", "enumerate", "zip"}
SAFE_NAMES.update(SAFE_BUILTINS)

SAFE_BUILTINS_DICT = {
    "len": len,
    "float": float,
    "int": int,
    "list": list,
    "range": range,
    "tuple": tuple,
    "dict": dict,
    "sum": sum,
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "enumerate": enumerate,
    "zip": zip,
}

def _safe_eval(expr: str, mol):
    # Reject double underscores to block accesses like __class__
    if "__" in expr:
        raise ValueError("Disallowed double underscores in expression")
        
    code = compile(expr, "<custom_descriptor>", "eval")
    # Verify the code does not access disallowed names
    for name in code.co_names:
        if name not in SAFE_NAMES:
            raise ValueError(f"Disallowed name in custom expression: {name}")
            
    # Restricted evaluation context
    context = {
        "Chem": Chem,
        "Descriptors": Descriptors,
        "rdMolDescriptors": rdMolDescriptors,
        "Lipinski": Lipinski,
        "Crippen": Crippen,
        "math": math,
        "mol": mol,
        **SAFE_BUILTINS_DICT
    }
    
    # Check that it doesn't try to access builtins or double underscores
    result = eval(code, {"__builtins__": {}}, context)
    return result

def compute_custom_expr(smiles_list: list[str], params: dict) -> np.ndarray:
    expr = params.get("expression", "Descriptors.MolWt(mol)")
    if not expr:
        expr = "Descriptors.MolWt(mol)"
        
    # Standardize/compile check
    try:
        # Check double underscores on expr string directly
        if "__" in expr:
            raise ValueError("Disallowed double underscores in expression")
        compiled = compile(expr, "<custom_descriptor>", "eval")
        for name in compiled.co_names:
            if name not in SAFE_NAMES and name != "mol":
                raise ValueError(f"Disallowed name in custom expression: {name}")
    except Exception as e:
        # If compilation fails, return a 1-column array of zeros to prevent pipeline crash
        return np.zeros((len(smiles_list), 1))
        
    # Lock dimensionality by evaluating first valid molecule
    dim = 1
    for smiles in smiles_list:
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                val = _safe_eval(expr, mol)
                if isinstance(val, (list, tuple)):
                    dim = len(val)
                else:
                    dim = 1
                break
        except Exception:
            continue
            
    matrix = np.zeros((len(smiles_list), dim))
    
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                val = _safe_eval(expr, mol)
                if isinstance(val, (list, tuple)):
                    for j in range(min(dim, len(val))):
                        matrix[i, j] = float(val[j])
                else:
                    matrix[i, 0] = float(val)
        except Exception:
            pass
            
    return matrix

# Helper function to test an expression on first 5 molecules
def test_custom_expression(smiles_list: list[str], expr: str) -> list:
    """
    Evaluates the expression on the first 5 parsed molecules.
    Returns a list of dicts: {"smiles": smiles, "value": val_or_error_string, "success": bool}
    """
    results = []
    count = 0
    for smiles in smiles_list:
        if count >= 5:
            break
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                continue
            val = _safe_eval(expr, mol)
            if isinstance(val, (list, tuple)):
                parsed_val = [float(x) for x in val]
            else:
                parsed_val = float(val)
            results.append({"smiles": smiles, "value": parsed_val, "success": True})
            count += 1
        except Exception as e:
            results.append({"smiles": smiles, "value": str(e), "success": False})
            count += 1
    return results

test_custom_expression.__test__ = False

register(FeaturizerSpec(
    id="custom",
    category="custom",
    label="Custom Descriptor",
    description="Power-user free-text mode allowing evaluation of custom Python molecular property expressions.",
    dimensionality=lambda params: 1, # Dynamically sized during run, default 1-column representation
    cost_estimate=lambda params, n: n * 0.002,
    compute=compute_custom_expr,
    param_schema={
        "expression": {"type": "string", "default": "Descriptors.MolWt(mol)"}
    },
    default_params={"expression": "Descriptors.MolWt(mol)"}
))
