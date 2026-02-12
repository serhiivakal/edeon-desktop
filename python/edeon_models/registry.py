from typing import Optional
from .backend import ModelBackend
from .endpoints import Endpoint

class BackendRegistry:
    """Central registry mapping endpoints to available backends."""

    def __init__(self):
        self._backends: dict[Endpoint, dict[int, ModelBackend]] = {}
        self._preferences: dict[Endpoint, int] = {}  # endpoint → preferred tier

    def register(self, backend: ModelBackend) -> None:
        ep = backend.endpoint()
        tier = backend.tier()
        self._backends.setdefault(ep, {})[tier] = backend

    def get(
        self,
        endpoint: Endpoint,
        preferred_tier: Optional[int] = None
    ) -> ModelBackend:
        """Resolve a backend for the endpoint. Resolution order:
        1. Explicit preferred_tier if registered.
        2. User preference for this endpoint if set.
        3. Lowest available tier number (T1 before T2 before T3 before T4).
        Raises KeyError if no backend exists for the endpoint.
        """
        resolved_ep = Endpoint(endpoint)
        if resolved_ep not in self._backends:
            raise KeyError(f"No backend registered for {endpoint}")
        available = self._backends[resolved_ep]
        if preferred_tier is not None and preferred_tier in available:
            return available[preferred_tier]
        user_pref = self._preferences.get(resolved_ep)
        if user_pref is not None and user_pref in available:
            return available[user_pref]
        # Default: lowest tier number wins (T1 preferred)
        return available[min(available.keys())]

    def list_for_endpoint(self, endpoint: Endpoint) -> list[ModelBackend]:
        resolved_ep = Endpoint(endpoint)
        return list(self._backends.get(resolved_ep, {}).values())

    def set_preference(self, endpoint: Endpoint, tier: int) -> None:
        resolved_ep = Endpoint(endpoint)
        self._preferences[resolved_ep] = tier

    def all_endpoints(self) -> list[Endpoint]:
        return list(self._backends.keys())
