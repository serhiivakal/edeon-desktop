import pytest
from edeon_train.gates import TestSetGate

def test_test_set_gate_guard():
    # 1. Obtain gate for an endpoint
    gate = TestSetGate.get("synth_endpoint")
    
    # Reset internal state if it was previously registered
    gate._opened = False
    gate._evaluations = 0

    def mock_load():
        return "loaded_test_set_data"

    # 2. Assert that loading test split without opening raises RuntimeError
    with pytest.raises(RuntimeError) as excinfo:
        gate.load_test(mock_load)
    assert "Accidental test-set loading blocked" in str(excinfo.value)

    # 3. Open gate and load
    gate.open("Final evaluation run on test split")
    res = gate.load_test(mock_load)
    assert res == "loaded_test_set_data"

    # 4. Assert that gate is auto-closed after one load (subsequent load throws)
    with pytest.raises(RuntimeError) as excinfo:
        gate.load_test(mock_load)
    assert "Accidental test-set loading blocked" in str(excinfo.value)

    # 5. Assert that attempting to re-open after it has been evaluated throws
    with pytest.raises(RuntimeError) as excinfo:
        gate.open("Attempting secondary evaluation")
    assert "already been evaluated" in str(excinfo.value)
