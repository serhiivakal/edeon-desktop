import unittest
import os
import tempfile
import time
from datetime import datetime, timedelta

from edeon_models.endpoints import Endpoint
from edeon_models.types import (
    ModelCard,
    Tier,
    TrainingDataInfo,
    PerformanceMetrics,
    ADDefinition,
)
from edeon_models.card import save_card, load_card, list_cards, delete_card

class TestModelCardCRUD(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary file for the SQLite database
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Build a complex ModelCard with nested data structures
        self.complex_card = ModelCard(
            model_id="bee_acute_oral_ld50.t1.1.2.3",
            name="Honeybee Acute Oral QSAR",
            version="1.2.3",
            tier=Tier.REFERENCE,
            endpoint=Endpoint.BEE_ACUTE_ORAL_LD50.value,
            description="Highly accurate QSAR random forest model predicting bee oral toxicity.",
            intended_use="Environmental screening",
            not_intended_for=["Human medicine ingestion"],
            training_data=TrainingDataInfo(
                n_compounds=452,
                sources=["EPA ECOTOX", "EFSA Reports"],
                sha256="abcdef1234567890",
                split_strategy="scaffold"
            ),
            performance=PerformanceMetrics(
                metrics={"rmse": 0.35, "r2": 0.81},
                test_set_n=90,
                cv_folds=5,
                calibration_coverage_95=0.942
            ),
            applicability_domain=ADDefinition(
                method="tanimoto_knn",
                threshold=0.35,
                k=5,
                training_set_size=452
            ),
            uncertainty_method="ConformalUQ",
            known_failure_modes=["Organometallic compounds"],
            references=["Author et al., J. Chem. Inf. 2026"],
            authors=["Dr. Alice", "Dr. Bob"]
        )

    def tearDown(self):
        # Close and delete the temporary database file
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
    def test_save_and_load_card_round_trip(self):
        """Assert that a ModelCard can be saved and loaded with all nested objects preserved exactly."""
        # 1. Save
        save_card(self.complex_card, db_path=self.db_path)
        
        # 2. Load
        loaded = load_card(self.complex_card.model_id, db_path=self.db_path)
        
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.model_id, self.complex_card.model_id)
        self.assertEqual(loaded.name, self.complex_card.name)
        self.assertEqual(loaded.tier, self.complex_card.tier)
        self.assertEqual(loaded.endpoint, self.complex_card.endpoint)
        self.assertEqual(loaded.description, self.complex_card.description)
        self.assertEqual(loaded.uncertainty_method, self.complex_card.uncertainty_method)
        
        # Check list fields
        self.assertEqual(loaded.authors, self.complex_card.authors)
        self.assertEqual(loaded.not_intended_for, self.complex_card.not_intended_for)
        
        # Check nested structures
        self.assertIsNotNone(loaded.training_data)
        self.assertEqual(loaded.training_data.n_compounds, 452)
        self.assertEqual(loaded.training_data.split_strategy, "scaffold")
        
        self.assertIsNotNone(loaded.performance)
        self.assertEqual(loaded.performance.metrics["r2"], 0.81)
        self.assertEqual(loaded.performance.calibration_coverage_95, 0.942)
        
        self.assertIsNotNone(loaded.applicability_domain)
        self.assertEqual(loaded.applicability_domain.method, "tanimoto_knn")
        self.assertEqual(loaded.applicability_domain.threshold, 0.35)
        
        # Check datetime deserialization
        self.assertIsInstance(loaded.created, datetime)
        self.assertEqual(loaded.created.year, self.complex_card.created.year)

    def test_load_non_existent_card(self):
        """Assert loading a card that does not exist returns None."""
        loaded = load_card("non_existent_id", db_path=self.db_path)
        self.assertIsNone(loaded)

    def test_list_cards_filtering(self):
        """Assert listing all cards and filtering by endpoint operates properly."""
        # Save two different cards
        save_card(self.complex_card, db_path=self.db_path)
        
        second_card = ModelCard(
            model_id="bee_acute_contact_ld50.t2.2.0.0",
            name="Bee Contact Baseline",
            version="2.0.0",
            tier=Tier.BASELINE,
            endpoint=Endpoint.BEE_ACUTE_CONTACT_LD50.value,
            description="Baseline contact toxicity estimator.",
            intended_use="Baseline"
        )
        save_card(second_card, db_path=self.db_path)
        
        # 1. List all
        all_cards = list_cards(db_path=self.db_path)
        self.assertEqual(len(all_cards), 2)
        
        # 2. Filter by BEE_ACUTE_ORAL_LD50
        oral_cards = list_cards(endpoint=Endpoint.BEE_ACUTE_ORAL_LD50, db_path=self.db_path)
        self.assertEqual(len(oral_cards), 1)
        self.assertEqual(oral_cards[0].model_id, self.complex_card.model_id)
        
        # 3. Filter by BEE_ACUTE_CONTACT_LD50
        contact_cards = list_cards(endpoint=Endpoint.BEE_ACUTE_CONTACT_LD50, db_path=self.db_path)
        self.assertEqual(len(contact_cards), 1)
        self.assertEqual(contact_cards[0].model_id, second_card.model_id)

    def test_delete_card(self):
        """Assert deleting a card removes it from database and returns appropriate status."""
        save_card(self.complex_card, db_path=self.db_path)
        
        # Check it exists
        self.assertIsNotNone(load_card(self.complex_card.model_id, db_path=self.db_path))
        
        # Delete it
        deleted = delete_card(self.complex_card.model_id, db_path=self.db_path)
        self.assertTrue(deleted)
        
        # Verify it is gone
        self.assertIsNone(load_card(self.complex_card.model_id, db_path=self.db_path))
        
        # Deleting again returns False
        deleted_again = delete_card(self.complex_card.model_id, db_path=self.db_path)
        self.assertFalse(deleted_again)

    def test_preserves_created_at_on_resave(self):
        """Assert that re-saving a card with the same ID preserves its original created_at timestamp."""
        # Save initial card
        save_card(self.complex_card, db_path=self.db_path)
        
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT created_at, updated_at FROM model_cards WHERE model_id = ?", (self.complex_card.model_id,))
        first_created, first_updated = cursor.fetchone()
        conn.close()
        
        # Wait a brief moment to ensure time difference
        time.sleep(0.1)
        
        # Save the card again
        save_card(self.complex_card, db_path=self.db_path)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT created_at, updated_at FROM model_cards WHERE model_id = ?", (self.complex_card.model_id,))
        second_created, second_updated = cursor.fetchone()
        conn.close()
        
        # Assert created_at is identical but updated_at is newer
        self.assertEqual(first_created, second_created)
        self.assertNotEqual(first_updated, second_updated)

if __name__ == "__main__":
    unittest.main()
