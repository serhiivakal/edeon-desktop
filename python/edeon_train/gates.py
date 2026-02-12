from typing import Any, Callable

class TestSetGate:
    """Global gate preventing accidental test-set evaluation (contamination protection).
    
    A separate gate is created per endpoint. Loading the test split increments a counter;
    the test split may only be loaded if the gate is explicitly opened.
    """
    __test__ = False
    _registry: dict[str, "TestSetGate"] = {}

    @classmethod
    def get(cls, endpoint: str) -> "TestSetGate":
        """Retrieves or registers the gate for a specific endpoint."""
        if endpoint not in cls._registry:
            cls._registry[endpoint] = cls(endpoint)
        return cls._registry[endpoint]

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self._opened = False
        self._evaluations = 0

    def open(self, reason: str) -> None:
        """Open the gate for final evaluation only."""
        if self._evaluations > 0:
            raise RuntimeError(
                f"Test set for '{self.endpoint}' has already been evaluated {self._evaluations} times. "
                f"Refusing to re-evaluate to maintain strict partition separation. "
                f"Reason logged: {reason}"
            )
        self._opened = True
        print(f"[GATE OPENED] Test gate opened for '{self.endpoint}'. Reason: {reason}")

    def load_test(self, loader_fn: Callable[[], Any]) -> Any:
        """Loads the test set safely if the gate is open. Auto-closes the gate immediately after."""
        if not self._opened:
            raise RuntimeError(
                f"Accidental test-set loading blocked for '{self.endpoint}'. "
                f"The test set may only be loaded if the gate has been explicitly opened via gate.open() "
                f"exactly once during the final evaluation stage."
            )
        self._evaluations += 1
        self._opened = False  # Auto-close immediately after first load
        print(f"[GATE CLOSED] Test gate auto-closed for '{self.endpoint}' after loading.")
        return loader_fn()
