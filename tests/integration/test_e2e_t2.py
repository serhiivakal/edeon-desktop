import subprocess
import json
import os
import sys
from pathlib import Path

def test_e2e_t2_prediction():
    # 1. Start the Python IPC server in a subprocess
    server_path = Path(__file__).parents[2] / "python"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(server_path)
    
    process = subprocess.Popen(
        [sys.executable, "-m", "edeon_models.ipc.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    
    try:
        # Read the initial "ready" signal from standard output
        ready_line = process.stdout.readline().strip()
        ready_data = json.loads(ready_line)
        assert ready_data.get("result") == "ready"
        
        # 2. Call model_predict (via JSON-RPC predict method equivalent to Rust's call)
        request = {
            "id": "test-req-1",
            "method": "predict",
            "params": {
                "endpoint": "bee_acute_oral_ld50",
                "smiles": ["CCO"],
                "preferred_tier": 2
            }
        }
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        
        # Read the prediction response
        response_line = process.stdout.readline().strip()
        response = json.loads(response_line)
        
        assert response.get("error") is None
        result = response.get("result")
        assert isinstance(result, list)
        assert len(result) == 1
        
        pred = result[0]
        # 3. Assert response shape: tier=2, units="ug/bee" (or µg/bee), warnings contains "Screening estimate"
        assert pred.get("tier") == 2
        # Check units, accepting both the Unicode and ascii formats
        assert pred.get("units") in ["µg/bee", "ug/bee"]
        
        warnings = pred.get("warnings", [])
        assert any("Screening estimate" in w for w in warnings)
        
    finally:
        # Send quit signal or terminate process
        try:
            process.stdin.write(json.dumps({"command": "quit"}) + "\n")
            process.stdin.flush()
            process.wait(timeout=2)
        except Exception:
            process.kill()
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()
