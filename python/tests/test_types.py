import unittest
from datetime import datetime, timezone
from pydantic import ValidationError
from edeon_models.types import (
    ADStatus,
    Tier,
    PredictionValue,
    Prediction,
    TrainingDataInfo,
    PerformanceMetrics,
    ADDefinition,
    ModelCard
)

class TestTypes(unittest.TestCase):
    
    def test_ad_status_enum(self):
        """Assert ADStatus values match the expected strings."""
        self.assertEqual(ADStatus.IN, "in")
        self.assertEqual(ADStatus.BORDERLINE, "borderline")
        self.assertEqual(ADStatus.OUT, "out")
        self.assertEqual(ADStatus.UNKNOWN, "unknown")
        
    def test_tier_enum(self):
        """Assert Tier values match their respective integers."""
        self.assertEqual(Tier.REFERENCE, 1)
        self.assertEqual(Tier.BASELINE, 2)
        self.assertEqual(Tier.EXTERNAL, 3)
        self.assertEqual(Tier.USER, 4)
        self.assertTrue(isinstance(Tier.REFERENCE, int))
        
    def test_prediction_value_numeric(self):
        """Verify numeric PredictionValue instantiation and serialization."""
        val = PredictionValue(kind="numeric", numeric=1.23)
        self.assertEqual(val.kind, "numeric")
        self.assertEqual(val.numeric, 1.23)
        self.assertIsNone(val.categorical)
        
        # Test freezing constraint (frozen=True)
        with self.assertRaises(ValidationError):
            val.kind = "categorical"  # Should be read-only / immutable
            
        # Test round-trip JSON serialization
        json_data = val.model_dump_json()
        restored = PredictionValue.model_validate_json(json_data)
        self.assertEqual(restored.kind, "numeric")
        self.assertEqual(restored.numeric, 1.23)

    def test_prediction_validation_and_serialization(self):
        """Verify Prediction instantiation, freezing, defaults, and round-trip serialization."""
        pred_val = PredictionValue(kind="numeric", numeric=10.5)
        now = datetime.now(timezone.utc)
        
        pred = Prediction(
            smiles="CCO",
            endpoint="bee_acute_oral_ld50",
            value=pred_val,
            ci_lower=8.0,
            ci_upper=13.0,
            ci_level=0.95,
            ad_status=ADStatus.IN,
            ad_score=0.05,
            units="µg/bee",
            model_id="bee_acute_oral_ld50.t2.0.1.0",
            model_version="0.1.0",
            tier=Tier.BASELINE,
            timestamp=now,
            provenance={"source": "legacy_logp_model"},
            warnings=["Screening estimate"]
        )
        
        self.assertEqual(pred.smiles, "CCO")
        self.assertEqual(pred.value.numeric, 10.5)
        self.assertEqual(pred.ad_status, ADStatus.IN)
        self.assertEqual(pred.tier, 2)
        self.assertEqual(pred.warnings, ["Screening estimate"])
        
        # Test freezing constraint (frozen=True)
        with self.assertRaises(ValidationError):
            pred.smiles = "CCC"
            
        # Test round-trip JSON serialization
        json_data = pred.model_dump_json()
        restored = Prediction.model_validate_json(json_data)
        self.assertEqual(restored.smiles, "CCO")
        self.assertEqual(restored.value.numeric, 10.5)
        self.assertEqual(restored.ad_status, ADStatus.IN)
        self.assertEqual(restored.tier, 2)
        # Ensure datetimes align properly across conversion
        self.assertEqual(restored.timestamp.replace(tzinfo=timezone.utc), now.replace(tzinfo=timezone.utc))

    def test_training_data_info(self):
        """Verify TrainingDataInfo validation."""
        info = TrainingDataInfo(
            n_compounds=100,
            sources=["ApisTox", "Pesticide Properties Database"],
            sha256="abc123sha",
            split_strategy="scaffold",
            license="CC-BY-4.0"
        )
        self.assertEqual(info.n_compounds, 100)
        self.assertEqual(info.sources[0], "ApisTox")
        
        # Test type validation failure
        with self.assertRaises(ValidationError):
            TrainingDataInfo(n_compounds="not-an-int", sources=["src"])

    def test_performance_metrics(self):
        """Verify PerformanceMetrics validation."""
        metrics = PerformanceMetrics(
            metrics={"rmse": 0.45, "r2": 0.81},
            test_set_n=25,
            cv_folds=5,
            calibration_coverage_95=0.96
        )
        self.assertEqual(metrics.metrics["r2"], 0.81)
        self.assertEqual(metrics.cv_folds, 5)

    def test_ad_definition(self):
        """Verify ADDefinition validation."""
        ad = ADDefinition(
            method="tanimoto_knn",
            threshold=0.15,
            k=5,
            training_set_size=120,
            notes="Calculated at 95th percentile"
        )
        self.assertEqual(ad.method, "tanimoto_knn")
        self.assertEqual(ad.k, 5)

    def test_model_card(self):
        """Verify ModelCard instantiation, defaults, and round-trip serialization."""
        info = TrainingDataInfo(n_compounds=50, sources=["ApisTox"])
        metrics = PerformanceMetrics(metrics={"accuracy": 0.85})
        ad = ADDefinition(method="none")
        
        card = ModelCard(
            model_id="bee_acute_oral_ld50.t2.0.1.0",
            name="Edeon Legacy Bee LD50 (LogP-based)",
            version="0.1.0",
            tier=Tier.BASELINE,
            endpoint="bee_acute_oral_ld50",
            description="Tier-2 baseline screening estimate of honeybee acute oral LD50",
            intended_use="Tier-2 baseline screening",
            training_data=info,
            performance=metrics,
            applicability_domain=ad,
            authors=["Edeon Science Team"]
        )
        
        self.assertEqual(card.model_id, "bee_acute_oral_ld50.t2.0.1.0")
        self.assertEqual(card.license, "Proprietary")  # Default value
        self.assertEqual(card.authors, ["Edeon Science Team"])
        
        # Test round-trip JSON serialization
        json_data = card.model_dump_json()
        restored = ModelCard.model_validate_json(json_data)
        self.assertEqual(restored.model_id, "bee_acute_oral_ld50.t2.0.1.0")
        self.assertEqual(restored.training_data.n_compounds, 50)
        self.assertEqual(restored.performance.metrics["accuracy"], 0.85)

if __name__ == "__main__":
    unittest.main()
