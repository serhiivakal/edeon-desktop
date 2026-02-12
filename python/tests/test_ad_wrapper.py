import unittest
from typing import Optional
from edeon_models.endpoints import Endpoint
from edeon_models.backend import ModelBackend
from edeon_models.types import Prediction, PredictionValue, ADStatus, ModelCard
from edeon_models.ad.tanimoto_knn import TanimotoKNN_AD
from edeon_models.ad.wrapper import ADWrapper

class DummyPredictorBackend(ModelBackend):
    """A dummy predictor backend returning predictions with UNKNOWN AD status."""
    
    def endpoint(self) -> Endpoint:
        return Endpoint.BEE_ACUTE_ORAL_LD50
        
    def tier(self) -> int:
        return 2
        
    def version(self) -> str:
        return "1.0.0"
        
    def predict(self, smiles: list[str], conditions: Optional[dict] = None) -> list[Prediction]:
        out = []
        for s in smiles:
            out.append(Prediction(
                smiles=s,
                endpoint=self.endpoint().value,
                value=PredictionValue(kind="numeric", numeric=5.5),
                ad_status=ADStatus.UNKNOWN,
                ad_score=None,
                units="µg/bee",
                model_id=self.model_id(),
                model_version=self.version(),
                tier=self.tier()
            ))
        return out
        
    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        return [ADStatus.UNKNOWN] * len(smiles)
        
    def metadata(self) -> ModelCard:
        return ModelCard(
            model_id=self.model_id(),
            name="Dummy Baseline Bee Predictor",
            version=self.version(),
            tier=self.tier(),
            endpoint=self.endpoint().value,
            description="Baseline mock",
            intended_use="Testing"
        )

class TestADWrapper(unittest.TestCase):
    
    def setUp(self):
        self.training_smiles = [
            "C", "CC", "CCC", "CCCC", "CCCCC", "CCCCCC", "CCCCCCC", "CCCCCCCC",
            "CO", "CCO", "CCCO", "CCCCO", "CCCCCO", "CCCCCCCO", "CCCCCCCCCO"
        ]
        self.ad_strategy = TanimotoKNN_AD(self.training_smiles, k=3)
        self.base_backend = DummyPredictorBackend()
        
    def test_wrapper_interface_delegation(self):
        """Assert that ADWrapper delegates base properties properly and appends version suffix."""
        wrapper = ADWrapper(self.base_backend, self.ad_strategy)
        
        self.assertEqual(wrapper.endpoint(), Endpoint.BEE_ACUTE_ORAL_LD50)
        self.assertEqual(wrapper.tier(), 2)
        self.assertEqual(wrapper.version(), "1.0.0+ad")
        self.assertEqual(wrapper.model_id(), "bee_acute_oral_ld50.t2.1.0.0+ad")

    def test_wrapped_predictions(self):
        """Assert that wrapping successfully overlays ADStatus and Tanimoto scores onto base predictions."""
        wrapper = ADWrapper(self.base_backend, self.ad_strategy)
        
        # 3 molecules: 1 in-domain, 1 out-of-domain, 1 invalid
        query_smiles = [
            "CCCCCCCO",         # IN (direct analogue)
            "[Na+].[Cl-]",      # OUT (inorganic salt)
            "INVALID_SMILES"    # UNKNOWN
        ]
        
        preds = wrapper.predict(query_smiles)
        self.assertEqual(len(preds), 3)
        
        # Molecule 1 (In-domain)
        self.assertEqual(preds[0].smiles, "CCCCCCCO")
        self.assertEqual(preds[0].ad_status, ADStatus.IN)
        self.assertIsNotNone(preds[0].ad_score)
        self.assertTrue(preds[0].ad_score <= self.ad_strategy.in_threshold)
        
        # Molecule 2 (Out-of-domain)
        self.assertEqual(preds[1].smiles, "[Na+].[Cl-]")
        self.assertEqual(preds[1].ad_status, ADStatus.OUT)
        self.assertEqual(preds[1].ad_score, 1.0) # exact 0 similarity
        
        # Molecule 3 (Invalid)
        self.assertEqual(preds[2].smiles, "INVALID_SMILES")
        self.assertEqual(preds[2].ad_status, ADStatus.UNKNOWN)
        self.assertIsNone(preds[2].ad_score)

    def test_applicability_domain_method(self):
        """Assert that applicability_domain lists match wrapper scoring statuses."""
        wrapper = ADWrapper(self.base_backend, self.ad_strategy)
        
        query_smiles = ["CCCCCCCO", "[Na+].[Cl-]", "INVALID_SMILES"]
        statuses = wrapper.applicability_domain(query_smiles)
        self.assertEqual(statuses, [ADStatus.IN, ADStatus.OUT, ADStatus.UNKNOWN])

    def test_wrapped_model_card_metadata(self):
        """Assert that ADWrapper updates the ModelCard with appropriate applicability domain parameters."""
        wrapper = ADWrapper(self.base_backend, self.ad_strategy)
        card = wrapper.metadata()
        
        self.assertIsInstance(card, ModelCard)
        self.assertIsNotNone(card.applicability_domain)
        self.assertEqual(card.applicability_domain.method, "tanimoto_knn")
        self.assertEqual(card.applicability_domain.threshold, self.ad_strategy.in_threshold)

if __name__ == "__main__":
    unittest.main()
