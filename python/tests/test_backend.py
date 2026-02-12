import unittest
from typing import Optional
from edeon_models.endpoints import Endpoint
from edeon_models.backend import ModelBackend
from edeon_models.types import Prediction, ADStatus, ModelCard

class MockBackend(ModelBackend):
    """A minimal mock implementation of ModelBackend."""
    
    def endpoint(self) -> Endpoint:
        return Endpoint.BEE_ACUTE_ORAL_LD50
        
    def tier(self) -> int:
        return 2
        
    def version(self) -> str:
        return "1.2.3"
        
    def predict(self, smiles: list[str], conditions: Optional[dict] = None) -> list[Prediction]:
        return []
        
    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        return [ADStatus.UNKNOWN] * len(smiles)
        
    def metadata(self) -> ModelCard:
        # Mock metadata
        return None

class TestBackend(unittest.TestCase):
    
    def test_direct_instantiation_fails(self):
        """Assert that attempting to directly instantiate ModelBackend raises TypeError."""
        with self.assertRaises(TypeError):
            ModelBackend()
            
    def test_mock_backend_instantiates(self):
        """Assert that MockBackend (which implements all abstract methods) can be instantiated."""
        backend = MockBackend()
        self.assertIsInstance(backend, ModelBackend)
        
    def test_model_id_convenience_format(self):
        """Verify that the model_id convenience method matches the expected format."""
        backend = MockBackend()
        self.assertEqual(backend.model_id(), "bee_acute_oral_ld50.t2.1.2.3")

if __name__ == "__main__":
    unittest.main()
