import unittest
import numpy as np
from typing import Optional
from edeon_models.endpoints import Endpoint
from edeon_models.backend import ModelBackend
from edeon_models.types import Prediction, PredictionValue, ADStatus, ModelCard
from edeon_models import wrap_with_uq_and_ad

class MockPointPredictor(ModelBackend):
    """A dummy predictor backend returning simple point predictions."""
    
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
            name="Mock Point Predictor",
            version=self.version(),
            tier=self.tier(),
            endpoint=self.endpoint().value,
            description="Mock base point predictor for testing composite",
            intended_use="Testing"
        )

class TestCompositeWrappers(unittest.TestCase):
    
    def setUp(self):
        # A simple list of training SMILES (mostly alkanes)
        self.training_smiles = [
            "C", "CC", "CCC", "CCCC", "CCCCC", "CCCCCC", "CCCCCCC", "CCCCCCCC",
            "CO", "CCO", "CCCO", "CCCCO", "CCCCCO", "CCCCCCCO", "CCCCCCCCCO"
        ]
        # Calibration residuals around 0.5
        self.calibration_residuals = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        self.base_backend = MockPointPredictor()
        
    def test_one_line_composition(self):
        """Assert that wrap_with_uq_and_ad produces a backend with both UQ and AD capability."""
        composite = wrap_with_uq_and_ad(
            backend=self.base_backend,
            training_smiles=self.training_smiles,
            calibration_residuals=self.calibration_residuals
        )
        
        # Verify it implements the base interface
        self.assertIsInstance(composite, ModelBackend)
        self.assertEqual(composite.endpoint(), Endpoint.BEE_ACUTE_ORAL_LD50)
        self.assertEqual(composite.tier(), 2)
        
        # The version suffix should show both wrappers
        self.assertEqual(composite.version(), "1.0.0+ad+uq")
        self.assertEqual(composite.model_id(), "bee_acute_oral_ld50.t2.1.0.0+ad+uq")

    def test_composite_predict_applies_both_uq_and_ad(self):
        """Assert that predict() overlays both Tanimoto AD scoring and Conformal UQ bounds."""
        composite = wrap_with_uq_and_ad(
            backend=self.base_backend,
            training_smiles=self.training_smiles,
            calibration_residuals=self.calibration_residuals
        )
        
        query_smiles = [
            "CCCCCCCO",         # IN (direct analogue)
            "[Na+].[Cl-]",      # OUT (inorganic salt)
            "INVALID_SMILES"    # UNKNOWN
        ]
        
        preds = composite.predict(query_smiles)
        self.assertEqual(len(preds), 3)
        
        # Conformal quantile for 8 residuals and alpha=0.05:
        # n = 8, alpha = 0.05
        # q_level = np.ceil(9 * 0.95) / 8 = np.ceil(8.55) / 8 = 9 / 8 = 1.125 -> clipped to 1.0
        # So it takes the maximum residual (0.8)
        expected_quantile = 0.8
        
        # Molecule 1: In-domain
        self.assertEqual(preds[0].smiles, "CCCCCCCO")
        self.assertEqual(preds[0].ad_status, ADStatus.IN)
        self.assertIsNotNone(preds[0].ad_score)
        
        # Conformal check
        self.assertAlmostEqual(preds[0].ci_lower, 5.5 - expected_quantile)
        self.assertAlmostEqual(preds[0].ci_upper, 5.5 + expected_quantile)
        self.assertEqual(preds[0].ci_level, 0.05) # Alpha level preserved
        
        # Molecule 2: Out-of-domain
        self.assertEqual(preds[1].smiles, "[Na+].[Cl-]")
        self.assertEqual(preds[1].ad_status, ADStatus.OUT)
        self.assertEqual(preds[1].ad_score, 1.0)
        self.assertAlmostEqual(preds[1].ci_lower, 5.5 - expected_quantile)
        self.assertAlmostEqual(preds[1].ci_upper, 5.5 + expected_quantile)
        
        # Molecule 3: Invalid
        self.assertEqual(preds[2].smiles, "INVALID_SMILES")
        self.assertEqual(preds[2].ad_status, ADStatus.UNKNOWN)
        self.assertIsNone(preds[2].ad_score)
        self.assertAlmostEqual(preds[2].ci_lower, 5.5 - expected_quantile)
        self.assertAlmostEqual(preds[2].ci_upper, 5.5 + expected_quantile)

    def test_composite_applicability_domain(self):
        """Assert applicability_domain matches expected Tanimoto AD scores."""
        composite = wrap_with_uq_and_ad(
            backend=self.base_backend,
            training_smiles=self.training_smiles,
            calibration_residuals=self.calibration_residuals
        )
        
        query_smiles = ["CCCCCCCO", "[Na+].[Cl-]", "INVALID_SMILES"]
        statuses = composite.applicability_domain(query_smiles)
        self.assertEqual(statuses, [ADStatus.IN, ADStatus.OUT, ADStatus.UNKNOWN])

    def test_composite_metadata_augmented(self):
        """Assert model card contains both ConformalUQ and Tanimoto k-NN details."""
        composite = wrap_with_uq_and_ad(
            backend=self.base_backend,
            training_smiles=self.training_smiles,
            calibration_residuals=self.calibration_residuals
        )
        
        card = composite.metadata()
        self.assertIsInstance(card, ModelCard)
        
        # Verify UQ metadata is present
        self.assertEqual(card.uncertainty_method, "ConformalUQ")
        # Note: ModelCard's version field is updated to version+uq by UQWrapper
        # UQWrapper: "version": f"{card.version}+uq"
        # ADWrapper doesn't change version in card. So it becomes "1.0.0+uq" in the card,
        # which is correct since UQWrapper modifies the card's version.
        self.assertEqual(card.version, "1.0.0+uq")
        
        # Verify AD metadata is present
        self.assertIsNotNone(card.applicability_domain)
        self.assertEqual(card.applicability_domain.method, "tanimoto_knn")
        self.assertIsNotNone(card.applicability_domain.threshold)

if __name__ == "__main__":
    unittest.main()
