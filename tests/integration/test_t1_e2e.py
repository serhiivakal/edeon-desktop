import pytest
import math
from edeon_models import build_default_registry, Endpoint
from edeon_models.types import ADStatus

def test_t1_e2e_integration():
    # 1. Build the registry at startup
    reg = build_default_registry()
    
    # 2. Assert that soil_koc is registered as Tier-1
    backend = reg.get(Endpoint.SOIL_KOC)
    assert backend.tier() == 1, "Expected Soil Koc to resolve to trained Tier-1 reference model!"
    
    # 3. Predict on a SMILES in the curated set and enrich via OverlayService
    from edeon_models.ipc.commands import OVERLAY_SERVICE
    curated_smiles = "COP(=O)(OC)C(O)C(Cl)(Cl)Cl"
    predictions = backend.predict([curated_smiles])
    predictions = OVERLAY_SERVICE.enrich(predictions)
    
    assert len(predictions) == 1
    pred = predictions[0]
    
    # 4. Assert prediction properties
    # Confirm it has a numeric value
    assert pred.value.kind == "numeric"
    assert pred.value.numeric is not None
    assert not math.isnan(pred.value.numeric)
    
    # Confirm it has a split conformal prediction interval (95% CI)
    assert pred.ci_lower is not None
    assert pred.ci_upper is not None
    assert pred.ci_lower <= pred.value.numeric <= pred.ci_upper
    
    # Confirm it has Tanimoto AD status (not UNKNOWN)
    assert pred.ad_status in [ADStatus.IN, ADStatus.BORDERLINE, ADStatus.OUT]
    assert pred.ad_score is not None
    
    # Confirm it has tier=1
    assert pred.tier == 1
    
    # Confirm provenance contains experimental values (imidacloprid is in ApisTox / bee oral curated data)
    assert pred.provenance is not None
    assert pred.provenance.get("experimental_values") is not None
    assert len(pred.provenance.get("experimental_values")) > 0
    
    # Verify experimental overlay contents
    exp = pred.provenance.get("experimental_values")[0]
    assert "value" in exp
    assert "units" in exp
    assert "source" in exp
    
    print(f"End-to-end integration successful!")
    print(f"Predicted value: {pred.value.numeric:.4f} {pred.units} [{pred.ci_lower:.4f} - {pred.ci_upper:.4f}]")
    print(f"AD status: {pred.ad_status.value} (score: {pred.ad_score:.4f})")
    print(f"Experimental values found: {len(pred.provenance.get('experimental_values'))}")

def test_t1_dt50_and_gus_integration():
    reg = build_default_registry()
    
    # 1. Assert Soil DT50 reference model resolves to Tier-1
    dt50_backend = reg.get(Endpoint.SOIL_DT50)
    assert dt50_backend.tier() == 1, "Expected Soil DT50 to resolve to trained Tier-1 reference model!"
    
    # 2. Predict on Imidacloprid (known compound)
    imidacloprid = "C1=C(Cl)C=NC(=C1)CN2C(=N[N+](=O)[O-])NCC2"
    dt50_preds = dt50_backend.predict([imidacloprid])
    assert len(dt50_preds) == 1
    pred_dt50 = dt50_preds[0]
    
    # Verify heteroscedastic predictions and CI bounds
    assert pred_dt50.value.kind == "numeric"
    assert pred_dt50.value.numeric is not None
    assert pred_dt50.ci_lower is not None
    assert pred_dt50.ci_upper is not None
    assert pred_dt50.ci_lower <= pred_dt50.value.numeric <= pred_dt50.ci_upper
    
    # Verify heteroscedastic log-space variables in provenance
    prov = pred_dt50.provenance
    assert "variance_aleatoric" in prov
    assert "variance_epistemic" in prov
    assert "variance_total" in prov
    assert "scale" in prov
    
    # 3. Assert GUS Leaching Index resolves to Tier-1 composite model
    gus_backend = reg.get(Endpoint.GUS_INDEX)
    assert gus_backend.tier() == 1, "Expected GUS Index to resolve to Tier-1 composite model!"
    assert gus_backend.model_id() == "gus_index.t1.v1.0"
    
    gus_preds = gus_backend.predict([imidacloprid])
    assert len(gus_preds) == 1
    pred_gus = gus_preds[0]
    
    # Verify GUS index predictions and Monte Carlo CI bounds
    assert pred_gus.value.kind == "numeric"
    assert pred_gus.value.numeric is not None
    assert pred_gus.ci_lower is not None
    assert pred_gus.ci_upper is not None
    assert pred_gus.ci_lower <= pred_gus.value.numeric <= pred_gus.ci_upper
    
    # Verify GUS leaching probability breakdown in provenance
    gus_prov = pred_gus.provenance
    assert "leaching_probabilities" in gus_prov
    probs = gus_prov["leaching_probabilities"]
    assert "non_leacher" in probs
    assert "transition" in probs
    assert "leacher" in probs
    assert abs(probs["non_leacher"] + probs["transition"] + probs["leacher"] - 1.0) < 1e-4
    
    # Verify combined AD status
    assert pred_gus.ad_status in [ADStatus.IN, ADStatus.BORDERLINE, ADStatus.OUT]
    
    print("Soil DT50 and GUS composite integration successful!")
    print(f"DT50 Prediction: {pred_dt50.value.numeric:.4f} days (95% CI: [{pred_dt50.ci_lower:.4f} - {pred_dt50.ci_upper:.4f}])")
    print(f"GUS Prediction: {pred_gus.value.numeric:.4f} (95% CI: [{pred_gus.ci_lower:.4f} - {pred_gus.ci_upper:.4f}])")
    print(f"Leaching classes: Non-leacher={probs['non_leacher']:.4f}, Transition={probs['transition']:.4f}, Leacher={probs['leacher']:.4f}")
