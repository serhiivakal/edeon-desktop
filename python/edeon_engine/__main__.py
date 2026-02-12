"""
Edeon Engine — JSON-RPC stdio server

Reads JSON requests from stdin (one per line), dispatches to handlers,
writes JSON responses to stdout (one per line). Flushes after every write.

Protocol:
  → {"id": 1, "method": "ping", "params": {}}
  ← {"id": 1, "result": "pong"}

Methods:
  - ping                → "pong"
  - standardize         → canonicalize SMILES batch
  - compute_properties  → MW, LogP, TPSA, HBD, HBA, RotBonds
  - pesticide_likeness  → Tice rules scoring
  - quit                → shutdown engine
"""

import sys
import json
import traceback

from .standardize import standardize_batch
from .properties import compute_properties_batch
from .tice_rules import pesticide_likeness_batch


def handle_request(request: dict) -> dict:
    """Dispatch a JSON-RPC request to the appropriate handler."""
    req_id = request.get("id", 0)
    method = request.get("method", "")
    params = request.get("params", {})

    try:
        if method == "ping":
            return {"id": req_id, "result": "pong"}

        elif method == "standardize":
            smiles_list = params.get("smiles", [])
            result = standardize_batch(smiles_list)
            return {"id": req_id, "result": result}

        elif method == "compute_properties":
            smiles_list = params.get("smiles", [])
            result = compute_properties_batch(smiles_list)
            return {"id": req_id, "result": result}

        elif method == "pesticide_likeness":
            compounds = params.get("compounds", [])
            result = pesticide_likeness_batch(compounds)
            return {"id": req_id, "result": result}

        elif method == "quit":
            return {"id": req_id, "result": "shutting_down"}

        else:
            return {"id": req_id, "error": f"Unknown method: {method}"}

    except Exception as e:
        return {
            "id": req_id,
            "error": f"{type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc(),
        }


def send_response(response: dict):
    """Write a JSON response line to stdout and flush."""
    line = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main():
    """Main loop: read stdin line by line, dispatch, respond."""
    # Signal readiness
    send_response({"id": 0, "result": "ready", "engine": "edeon_engine", "version": "0.1.0"})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            send_response({"id": 0, "error": f"Invalid JSON: {str(e)}"})
            continue

        response = handle_request(request)
        send_response(response)

        # Check for quit command
        if request.get("method") == "quit":
            break


if __name__ == "__main__":
    main()
