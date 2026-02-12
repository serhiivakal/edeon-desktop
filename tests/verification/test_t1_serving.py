import pytest
import math
from edeon_models import build_default_registry, Endpoint
from edeon_models.types import ADStatus

# Deployed Tier-1 endpoints (have checkpoints under data/checkpoints) plus GUS composite
T1_ENDPOINTS = [
    Endpoint.BEE_ACUTE_ORAL_LD50,
    Endpoint.BEE_ACUTE_CONTACT_LD50,
    Endpoint.FISH_ACUTE_LC50,
    Endpoint.DAPHNIA_ACUTE_EC50,
    Endpoint.ALGAE_GROWTH_EC50,
    Endpoint.EARTHWORM_ACUTE_LC50,
    Endpoint.BIRD_ACUTE_ORAL_LD50,
    Endpoint.SOIL_KOC,
    Endpoint.SOIL_DT50,
    Endpoint.GUS_INDEX,
]

# Deployed Tier-1 endpoints that are regression tasks in both T1 and T2
T1_REG_ENDPOINTS = [
    Endpoint.DAPHNIA_ACUTE_EC50,
    Endpoint.EARTHWORM_ACUTE_LC50,
    Endpoint.SOIL_KOC,
    Endpoint.SOIL_DT50,
]

REFERENCE_PANEL = [
    ("C1=C(Cl)C=NC(=C1)CN2C(=N[N+](=O)[O-])NCC2", "Imidacloprid"),
    ("O=C(O)CNCP(=O)(O)O", "Glyphosate"),
    ("CCNc1nc(Cl)nc(NCC)n1", "Atrazine"),
    ("CS(=O)(=O)c1ccc(C(=O)C2C(=O)CCCC2=O)c([N+](=O)[O-])c1", "Mesotrione"),
    ("CCN(C)C(=N/C#N)/Cc1ccc(Cl)nc1", "Acetamiprid"),
    ("CC(C)(C)C(O)(CN1C=NC=N1)CCC2=CC=C(C=C2)Cl", "Tebuconazole"),
    ("C1(=C(C(=C(C(=C1Cl)Cl)C#N)Cl)Cl)C#N", "Chlorothalonil"),
    ("CNC(=O)Oc1cccc2ccccc12", "Carbaryl"),
    ("CCOP(=S)(OCC)Oc1nc(Cl)c(Cl)cc1Cl", "Chlorpyrifos"),
    ("C[n+]1ccc(-c2cc[n+](C)cc2)cc1", "Paraquat"),
]


@pytest.fixture(scope="module")
def registry():
    return build_default_registry()


@pytest.mark.parametrize("endpoint", T1_ENDPOINTS)
def test_t1_serves_predictions(endpoint, registry):
    backend = registry.get(endpoint, preferred_tier=1)
    assert backend.tier() == 1, (
        f"Endpoint {endpoint.value} is being served by tier {backend.tier()} "
        f"backend, not Tier-1."
    )
    
    # Predict on full panel
    smiles_list = [s for s, _ in REFERENCE_PANEL]
    predictions = backend.predict(smiles_list)
    assert len(predictions) == len(REFERENCE_PANEL)
    
    for pred, (_, name) in zip(predictions, REFERENCE_PANEL):
        assert pred.tier == 1, f"{name} prediction for {endpoint.value} is tier {pred.tier}, expected 1"
        assert pred.model_id == backend.model_id()
        assert pred.ad_status in [ADStatus.IN, ADStatus.BORDERLINE, ADStatus.OUT]
        
        # Verify provenance exists
        prov = pred.provenance
        assert prov is not None, f"{name} prediction for {endpoint.value} lacks provenance"
        assert "model_id" in prov
        assert "model_version" in prov


@pytest.mark.parametrize("endpoint", T1_REG_ENDPOINTS)
def test_t1_differs_from_legacy(endpoint, registry):
    """Confirm T1 isn't accidentally producing LogP-derived values."""
    t1 = registry.get(endpoint, preferred_tier=1)
    t2 = registry.get(endpoint, preferred_tier=2)
    
    smiles_list = [s for s, _ in REFERENCE_PANEL]
    t1_preds = t1.predict(smiles_list)
    t2_preds = t2.predict(smiles_list)
    
    differences = []
    for p1, p2 in zip(t1_preds, t2_preds):
        if p1.value.numeric is not None and p2.value.numeric is not None:
            # Both are in log10 space for regression
            # T1 backends return native values, so we log10 them
            p1_log_val = math.log10(p1.value.numeric) if p1.value.numeric > 0 else -999.0
            p2_log_val = p2.value.numeric # Tier 2 is in log10 space
            
            diff = abs(p1_log_val - p2_log_val)
            differences.append(diff)
            
    n_significant = sum(1 for d in differences if d > 0.2)
    assert n_significant >= 5, (
        f"T1 and T2 predictions for {endpoint.value} differ significantly (> 0.2 log10) "
        f"on only {n_significant}/{len(differences)} compounds. T1 may be collapsing to LogP."
    )
