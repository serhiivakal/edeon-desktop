import unittest
from typing import Optional
from edeon_models.endpoints import Endpoint
from edeon_models.backend import ModelBackend
from edeon_models.types import Prediction, ADStatus, ModelCard
from edeon_models.registry import BackendRegistry

class DummyBackend(ModelBackend):
    """A dummy backend implementation for registry tests."""
    
    def __init__(self, endpoint: Endpoint, tier: int, version: str):
        self._endpoint = endpoint
        self._tier = tier
        self._version = version
        
    def endpoint(self) -> Endpoint:
        return self._endpoint
        
    def tier(self) -> int:
        return self._tier
        
    def version(self) -> str:
        return self._version
        
    def predict(self, smiles: list[str], conditions: Optional[dict] = None) -> list[Prediction]:
        return []
        
    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        return [ADStatus.UNKNOWN] * len(smiles)
        
    def metadata(self) -> ModelCard:
        return None

class TestRegistry(unittest.TestCase):
    
    def test_registration_and_lowest_tier_resolution(self):
        """Assert that by default get() resolves to the lowest-tier registered backend."""
        registry = BackendRegistry()
        
        # Register a Tier 4 (User) backend
        t4_backend = DummyBackend(Endpoint.BEE_ACUTE_ORAL_LD50, 4, "0.1.0")
        registry.register(t4_backend)
        
        # Resolves to Tier 4 since it is the only one
        resolved = registry.get(Endpoint.BEE_ACUTE_ORAL_LD50)
        self.assertEqual(resolved.tier(), 4)
        
        # Register a Tier 2 (Baseline) backend
        t2_backend = DummyBackend(Endpoint.BEE_ACUTE_ORAL_LD50, 2, "0.1.0")
        registry.register(t2_backend)
        
        # Now it resolves to Tier 2 (since 2 < 4) by default
        resolved_lowest = registry.get(Endpoint.BEE_ACUTE_ORAL_LD50)
        self.assertEqual(resolved_lowest.tier(), 2)

    def test_explicit_preferred_tier_override(self):
        """Assert that passing an explicit preferred_tier overrides the default lowest-tier resolution."""
        registry = BackendRegistry()
        
        t4_backend = DummyBackend(Endpoint.BEE_ACUTE_ORAL_LD50, 4, "0.1.0")
        t2_backend = DummyBackend(Endpoint.BEE_ACUTE_ORAL_LD50, 2, "0.1.0")
        registry.register(t4_backend)
        registry.register(t2_backend)
        
        # Explicit preferred_tier = 4
        resolved = registry.get(Endpoint.BEE_ACUTE_ORAL_LD50, preferred_tier=4)
        self.assertEqual(resolved.tier(), 4)
        
        # Falls back to default if preferred_tier not registered
        resolved_missing = registry.get(Endpoint.BEE_ACUTE_ORAL_LD50, preferred_tier=1)
        self.assertEqual(resolved_missing.tier(), 2)

    def test_set_preference_override(self):
        """Assert that set_preference overrides the default resolution and matches user settings."""
        registry = BackendRegistry()
        
        t4_backend = DummyBackend(Endpoint.BEE_ACUTE_ORAL_LD50, 4, "0.1.0")
        t2_backend = DummyBackend(Endpoint.BEE_ACUTE_ORAL_LD50, 2, "0.1.0")
        registry.register(t4_backend)
        registry.register(t2_backend)
        
        # Default is Tier 2
        self.assertEqual(registry.get(Endpoint.BEE_ACUTE_ORAL_LD50).tier(), 2)
        
        # Set preference to Tier 4
        registry.set_preference(Endpoint.BEE_ACUTE_ORAL_LD50, 4)
        self.assertEqual(registry.get(Endpoint.BEE_ACUTE_ORAL_LD50).tier(), 4)
        
        # Falls back if preferred tier is not registered
        registry.set_preference(Endpoint.BEE_ACUTE_ORAL_LD50, 1)
        self.assertEqual(registry.get(Endpoint.BEE_ACUTE_ORAL_LD50).tier(), 2)

    def test_key_error_on_unknown_endpoint(self):
        """Assert that attempting to resolve an unregistered endpoint raises KeyError."""
        registry = BackendRegistry()
        with self.assertRaises(KeyError):
            registry.get(Endpoint.BEE_ACUTE_ORAL_LD50)

    def test_list_and_all_endpoints(self):
        """Verify list_for_endpoint and all_endpoints return expected items."""
        registry = BackendRegistry()
        
        t2_backend = DummyBackend(Endpoint.BEE_ACUTE_ORAL_LD50, 2, "0.1.0")
        t4_backend = DummyBackend(Endpoint.BEE_ACUTE_ORAL_LD50, 4, "0.1.0")
        registry.register(t2_backend)
        registry.register(t4_backend)
        
        backends = registry.list_for_endpoint(Endpoint.BEE_ACUTE_ORAL_LD50)
        self.assertEqual(len(backends), 2)
        self.assertIn(t2_backend, backends)
        self.assertIn(t4_backend, backends)
        
        self.assertEqual(registry.all_endpoints(), [Endpoint.BEE_ACUTE_ORAL_LD50])

if __name__ == "__main__":
    unittest.main()
