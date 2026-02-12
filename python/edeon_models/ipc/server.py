import sys
import json
import traceback
from .commands import execute_command

def main():
    # Write ready signal for spawn verification
    sys.stdout.write(json.dumps({"result": "ready"}) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
            
        try:
            request = json.loads(line)
        except Exception as e:
            sys.stdout.write(json.dumps({"id": None, "error": f"Invalid JSON input: {str(e)}"}) + "\n")
            sys.stdout.flush()
            continue

        req_id = request.get("id")
        # Dual-support for both {"command", "args"} and standard JSON-RPC {"method", "params"}
        command = request.get("command") or request.get("method")
        args = request.get("args") or request.get("params") or {}

        if not command:
            sys.stdout.write(json.dumps({"id": req_id, "error": "Missing 'command' or 'method' field"}) + "\n")
            sys.stdout.flush()
            continue

        if command == "quit" or command == "exit":
            sys.stdout.write(json.dumps({"id": req_id, "result": "goodbye"}) + "\n")
            sys.stdout.flush()
            break

        try:
            result = execute_command(command, args)
            response = {"id": req_id, "result": result, "error": None}
        except Exception as e:
            err_msg = f"{str(e)}\n{traceback.format_exc()}"
            response = {"id": req_id, "result": None, "error": err_msg}

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
