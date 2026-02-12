import unittest
from typing import Optional
from edeon_models.endpoints import Endpoint
from edeon_models.backend import ModelBackend
from edeon_models.types import Prediction, PredictionValue, ADStatus, ModelCard
from edeon_models.uq.conformal import ConformalUQ
from edeon_models.uq.wrapper import UQWrapper

class DummyNumericAndCategoricalPredictor(ModelBackend):
    """Mock predictor returning both numeric and categorical predictions for testing UQ boundaries."""
    
    def __init__(self, endpoint: Endpoint, is_numeric: bool):
        self._endpoint = endpoint
        self._is_numeric = is_numeric
        
    def endpoint(self) -> Endpoint:
        return self._endpoint
        
    def tier(self) -> int:
        return 2
        
    def version(self) -> str:
        return "1.1.0"
        
    def predict(self, smiles: list[str], conditions: Optional[dict] = None) -> list[Prediction]:
        out = []
        for s in smiles:
            if self._is_numeric:
                val = PredictionValue(kind="numeric", numeric=10.0)
            else:
                val = PredictionValue(kind="categorical", categorical="Low Risk")
                
            out.append(Prediction(
                smiles=s,
                endpoint=self.endpoint().value,
                value=val,
                ci_lower=None,
                ci_upper=None,
                ad_status=ADStatus.UNKNOWN,
                units="mg/L" if self._is_numeric else "category",
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
            name="Mock Multi-Type Predictor",
            version=self.version(),
            tier=self.tier(),
            endpoint=self.endpoint().value,
            description="Mock base model card",
            intended_use="Unittests"
        )

class TestUQWrapper(unittest.TestCase):
    
    def setUp(self):
        # Conformal UQ strategy pre-calibrated to have a quantile size of 1.5
        self.uq_strategy = ConformalUQ(alpha=0.05)
        self.uq_strategy.quantile = 1.5
        
    def test_delegation_interface(self):
        """Assert standard delegation of properties and model_id +uq version tags."""
        base = DummyNumericAndCategoricalPredictor(Endpoint.FISH_ACUTE_LC50, is_numeric=True)
        wrapper = UQWrapper(base, self.uq_strategy)
        
        self.assertEqual(wrapper.endpoint(), Endpoint.FISH_ACUTE_LC50)
        self.assertEqual(wrapper.tier(), 2)
        self.assertEqual(wrapper.version(), "1.1.0+uq")
        self.assertEqual(wrapper.model_id(), "fish_acute_lc50.t2.1.1.0+uq")
        self.assertEqual(wrapper.applicability_domain(["C"]), [ADStatus.UNKNOWN])

    def test_numeric_predictions_get_ci_intervals(self):
        """Assert that numeric point predictions are augmented with UQ intervals."""
        base = DummyNumericAndCategoricalPredictor(Endpoint.FISH_ACUTE_LC50, is_numeric=True)
        wrapper = UQWrapper(base, self.uq_strategy)
        
        preds = wrapper.predict(["C", "CC"])
        self.assertEqual(len(preds), 2)
        
        for pred in preds:
            self.assertEqual(pred.value.kind, "numeric")
            self.assertEqual(pred.value.numeric, 10.0)
            # 10.0 ± 1.5 (from pre-set conformal quantile)
            self.assertEqual(pred.ci_lower, 8.5)
            self.assertEqual(pred.ci_upper, 11.5)
            self.assertEqual(pred.ci_level, 0.05)

    def test_categorical_predictions_skip_ci_intervals(self):
        """Assert that categorical/binary predictions skip UQ calculations and remain unchanged."""
        base = DummyNumericAndCategoricalPredictor(Endpoint.SKIN_SENSITIZATION, is_numeric=False)
        wrapper = UQWrapper(base, self.uq_strategy)
        
        preds = wrapper.predict(["C", "CC"])
        self.assertEqual(len(preds), 2)
        
        for pred in preds:
            self.assertEqual(pred.value.kind, "categorical")
            self.assertEqual(pred.value.categorical, "Low Risk")
            self.assertIsNone(pred.ci_lower)
            self.assertIsNone(pred.ci_upper)

    def test_metadata_augmentation(self):
        """Verify model card details update with uncertainty_method and version additions."""
        base = DummyNumericAndCategoricalPredictor(Endpoint.FISH_ACUTE_LC50, is_numeric=True)
        wrapper = UQWrapper(base, self.uq_strategy)
        
        card = wrapper.metadata()
        self.assertIsInstance(card, ModelCard)
        self.assertEqual(card.version, "1.1.0+uq")
        self.assertEqual(card.uncertainty_method, "ConformalUQ")

if __name__ == "__main__":
    unittest.main()
