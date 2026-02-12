import unittest
from datetime import datetime

from edeon_models.endpoints import Endpoint
from edeon_models.types import (
    ModelCard,
    Tier,
    TrainingDataInfo,
    PerformanceMetrics,
    ADDefinition,
)
from edeon_models.card import card_to_yaml, card_from_yaml

class TestModelCardYAML(unittest.TestCase):
    
    def setUp(self):
        # Construct a detailed, complex ModelCard
        self.card = ModelCard(
            model_id="bee_acute_contact_ld50.t1.2.2.2",
            name="Bee Contact Reference",
            version="2.2.2",
            tier=Tier.REFERENCE,
            endpoint=Endpoint.BEE_ACUTE_CONTACT_LD50.value,
            description="Reference Morgan fingerprint model for acute contact toxicity.",
            intended_use="General screening",
            not_intended_for=["Sub-lethal exposure assays"],
            training_data=TrainingDataInfo(
                n_compounds=890,
                sources=["ECOTOX", "ECHA"],
                sha256="deadbeef12345678",
                split_strategy="random"
            ),
            performance=PerformanceMetrics(
                metrics={"rmse": 0.42, "r2": 0.77},
                test_set_n=178,
                cv_folds=10,
                calibration_coverage_95=0.961
            ),
            applicability_domain=ADDefinition(
                method="leverage",
                threshold=0.5,
                notes="Checked with warning status"
            ),
            uncertainty_method="EnsembleVarianceUQ",
            known_failure_modes=["Synthetic peptides"],
            references=["Author, Chem. Research 2026"],
            authors=["Dr. Charles"]
        )

    def test_yaml_round_trip(self):
        """Assert that a ModelCard can be serialized to YAML and parsed back with identical fields."""
        # 1. Serialize
        yaml_str = card_to_yaml(self.card)
        self.assertIsInstance(yaml_str, str)
        self.assertTrue(len(yaml_str) > 0)
        self.assertIn("bee_acute_contact_ld50.t1.2.2.2", yaml_str)
        self.assertIn("Bee Contact Reference", yaml_str)
        self.assertIn("deadbeef12345678", yaml_str)
        
        # 2. Deserialize
        deserialized = card_from_yaml(yaml_str)
        self.assertIsInstance(deserialized, ModelCard)
        
        # 3. Assert deep equality
        self.assertEqual(deserialized.model_id, self.card.model_id)
        self.assertEqual(deserialized.name, self.card.name)
        self.assertEqual(deserialized.version, self.card.version)
        self.assertEqual(deserialized.tier, self.card.tier)
        self.assertEqual(deserialized.endpoint, self.card.endpoint)
        self.assertEqual(deserialized.description, self.card.description)
        self.assertEqual(deserialized.uncertainty_method, self.card.uncertainty_method)
        
        # Check nested structures
        self.assertIsNotNone(deserialized.training_data)
        self.assertEqual(deserialized.training_data.n_compounds, 890)
        self.assertEqual(deserialized.training_data.sha256, "deadbeef12345678")
        
        self.assertIsNotNone(deserialized.performance)
        self.assertEqual(deserialized.performance.metrics["rmse"], 0.42)
        self.assertEqual(deserialized.performance.calibration_coverage_95, 0.961)
        
        self.assertIsNotNone(deserialized.applicability_domain)
        self.assertEqual(deserialized.applicability_domain.method, "leverage")
        self.assertEqual(deserialized.applicability_domain.threshold, 0.5)
        
        # Check list items
        self.assertEqual(deserialized.authors, ["Dr. Charles"])
        self.assertEqual(deserialized.known_failure_modes, ["Synthetic peptides"])
        
        # Check datetime field parses back correctly
        self.assertIsInstance(deserialized.created, datetime)
        self.assertEqual(deserialized.created.year, self.card.created.year)

    def test_invalid_yaml_raises_error(self):
        """Assert that parsing invalid or empty YAML throws appropriate errors."""
        with self.assertRaises(Exception):
            card_from_yaml("invalid: : yaml: structure")
            
        with self.assertRaises(ValueError):
            card_from_yaml("")

if __name__ == "__main__":
    unittest.main()
