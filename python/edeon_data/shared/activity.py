import math
from typing import Optional, Literal
import numpy as np
import pandas as pd

def normalize_unit_string(unit: str) -> str:
    if not isinstance(unit, str):
        return ""
    u = unit.lower().strip().replace(" ", "").replace("_", "")
    u = u.replace("µ", "u").replace("micro", "u")
    if u in ["m", "molar", "mol/l"]:
        return "molar"
    if u in ["mg/l", "mg/liter"]:
        return "mg/L"
    if u in ["ug/l", "ug/liter"]:
        return "ug/L"
    if u in ["ppm"]:
        return "ppm"
    if u in ["mg/kg", "mg/kgbw", "mg/kg_bw"]:
        return "mg/kg"
    if u in ["ug/kg", "ug/kgbw", "ug/kg_bw"]:
        return "ug/kg"
    if u in ["g/kg", "g/kgbw", "g/kg_bw"]:
        return "g/kg"
    if u in ["ug/bee", "ugbee"]:
        return "ug/bee"
    if u in ["ng/bee", "ngbee"]:
        return "ng/bee"
    if u in ["mg/bee", "mgbee"]:
        return "mg/bee"
    return u


def to_canonical_units(value: float, source_units: str, target_units: str, mw: Optional[float] = None) -> float:
    """Convert between common ecotox units. Supports:
       mg/L ↔ µg/L ↔ ppm ↔ molar (requires MW)
       mg/kg ↔ µg/kg ↔ g/kg
       ug/bee ↔ ng/bee ↔ mg/bee
    """
    src = normalize_unit_string(source_units)
    tgt = normalize_unit_string(target_units)
    
    if src == tgt:
        return value
        
    # Liquid concentration conversions
    # mg/L <-> ug/L <-> ppm <-> molar
    liquid_units = {"mg/L", "ug/L", "ppm", "molar"}
    if src in liquid_units and tgt in liquid_units:
        # Convert src to mg/L first
        if src == "mg/L":
            val_mg_l = value
        elif src == "ppm":
            val_mg_l = value
        elif src == "ug/L":
            val_mg_l = value / 1000.0
        elif src == "molar":
            if mw is None or mw <= 0:
                raise ValueError("Molecular weight (mw) is required for converting to/from molar units.")
            val_mg_l = value * 1000.0 * mw
            
        # Convert mg/L to tgt
        if tgt == "mg/L" or tgt == "ppm":
            return val_mg_l
        elif tgt == "ug/L":
            return val_mg_l * 1000.0
        elif tgt == "molar":
            if mw is None or mw <= 0:
                raise ValueError("Molecular weight (mw) is required for converting to/from molar units.")
            return val_mg_l / (1000.0 * mw)

    # Mass dose conversions
    # mg/kg <-> ug/kg <-> g/kg
    mass_units = {"mg/kg", "ug/kg", "g/kg"}
    if src in mass_units and tgt in mass_units:
        # Convert src to mg/kg
        if src == "mg/kg":
            val_mg_kg = value
        elif src == "ug/kg":
            val_mg_kg = value / 1000.0
        elif src == "g/kg":
            val_mg_kg = value * 1000.0
            
        # Convert mg/kg to tgt
        if tgt == "mg/kg":
            return val_mg_kg
        elif tgt == "ug/kg":
            return val_mg_kg * 1000.0
        elif tgt == "g/kg":
            return val_mg_kg / 1000.0

    # Bee dose conversions
    # ug/bee <-> ng/bee <-> mg/bee
    bee_units = {"ug/bee", "ng/bee", "mg/bee"}
    if src in bee_units and tgt in bee_units:
        # Convert src to ug/bee
        if src == "ug/bee":
            val_ug_bee = value
        elif src == "ng/bee":
            val_ug_bee = value / 1000.0
        elif src == "mg/bee":
            val_ug_bee = value * 1000.0
            
        # Convert ug/bee to tgt
        if tgt == "ug/bee":
            return val_ug_bee
        elif tgt == "ng/bee":
            return val_ug_bee * 1000.0
        elif tgt == "mg/bee":
            return val_ug_bee / 1000.0
            
    raise ValueError(f"Unsupported unit conversion from {source_units} to {target_units}")


def log_transform(value: float, mw: Optional[float] = None, target: str = "log10") -> float:
    """Apply log10 transformation.
    Supported targets:
      - "log10": log10(value)
      - "-log10": -log10(value)
      - "log10_molar": convert from mg/L to molar, then log10 (requires mw)
      - "-log10_molar": convert from mg/L to molar, then -log10 (requires mw)
    """
    if value <= 0:
        raise ValueError("Cannot log-transform non-positive values.")
        
    if target == "log10":
        return math.log10(value)
    elif target == "-log10":
        return -math.log10(value)
    elif target == "log10_molar":
        if mw is None or mw <= 0:
            raise ValueError("Molecular weight (mw) is required for log10_molar transformation.")
        molar_value = to_canonical_units(value, "mg/L", "molar", mw=mw)
        return math.log10(molar_value)
    elif target == "-log10_molar":
        if mw is None or mw <= 0:
            raise ValueError("Molecular weight (mw) is required for -log10_molar transformation.")
        molar_value = to_canonical_units(value, "mg/L", "molar", mw=mw)
        return -math.log10(molar_value)
    else:
        raise ValueError(f"Unsupported log transform target: {target}")


def aggregate_records(group: pd.DataFrame, mode: Literal["regression", "classification"]) -> dict:
    """
    Aggregate a group of records for the same compound (grouped by inchikey).
    Returns dict with value, value_log, aggregation_n, aggregation_method, aggregation_cv, quality_flags.
    """
    n = len(group)
    
    # Accumulate all quality flags from the input group
    flags = set()
    for f_list in group["quality_flags"]:
        if isinstance(f_list, list):
            flags.update(f_list)
        elif isinstance(f_list, str):
            flags.update([f.strip() for f in f_list.split(",") if f.strip()])

    if n == 1:
        row = group.iloc[0]
        return {
            "value": float(row["value"]),
            "value_log": float(row["value_log"]) if pd.notna(row.get("value_log")) else None,
            "value_class": row.get("value_class") if pd.notna(row.get("value_class")) else None,
            "aggregation_n": 1,
            "aggregation_method": "single",
            "aggregation_cv": None,
            "quality_flags": sorted(list(flags))
        }

    if mode == "regression":
        raw_values = group["value"].dropna().to_numpy()
        log_values = group["value_log"].dropna().to_numpy()
        
        if len(raw_values) == 0:
            raise ValueError("No valid numeric values to aggregate.")
            
        # Arithmetic mean of value_log
        avg_log = float(np.mean(log_values)) if len(log_values) > 0 else None
        
        # Geometric mean of raw values
        geom_mean = float(np.exp(np.mean(np.log(raw_values)))) if np.all(raw_values > 0) else float(np.mean(raw_values))
        
        # Calculate CV
        cv = None
        if len(raw_values) > 1:
            mean_val = np.mean(raw_values)
            if mean_val > 0:
                cv = float(np.std(raw_values, ddof=1) / mean_val)
                
        if cv is not None:
            if cv > 0.5:
                flags.add("high_cv")
            if n > 10 and cv > 1.0:
                flags.add("extreme_variance")
                
        return {
            "value": geom_mean,
            "value_log": avg_log,
            "value_class": None,
            "aggregation_n": n,
            "aggregation_method": "geomean",
            "aggregation_cv": cv,
            "quality_flags": sorted(list(flags))
        }
        
    elif mode == "classification":
        raw_classes = group["value_class"].dropna().tolist()
        if len(raw_classes) == 0:
            raise ValueError("No valid categorical classes to aggregate.")
            
        counts = pd.Series(raw_classes).value_counts()
        max_count = counts.max()
        majority_classes = counts[counts == max_count].index.tolist()
        
        if len(majority_classes) == 1:
            chosen_class = majority_classes[0]
            method = "majority_vote"
        else:
            flags.add("class_conflict")
            
            def concern_score(c):
                c_lower = str(c).lower().strip()
                high_concern_list = ["toxic", "sensitizer", "cat1", "cat 1", "cat 2", "yes", "active", "positive", "1"]
                low_concern_list = ["nontoxic", "nonsensitizer", "cat 5", "cat5", "no", "inactive", "negative", "0"]
                
                if c_lower in high_concern_list:
                    return 0
                if c_lower in low_concern_list:
                    return 2
                return 1
                
            chosen_class = min(majority_classes, key=concern_score)
            method = "majority_vote"
            
        return {
            "value": float(counts.index.get_loc(chosen_class)),
            "value_log": None,
            "value_class": chosen_class,
            "aggregation_n": n,
            "aggregation_method": method,
            "aggregation_cv": None,
            "quality_flags": sorted(list(flags))
        }
    else:
        raise ValueError(f"Unknown aggregation mode: {mode}")
