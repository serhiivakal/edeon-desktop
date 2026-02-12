import unittest
import subprocess
import json
import os
import sys

class TestIPCStdio(unittest.TestCase):
    
    def setUp(self):
        # Spawn the server module in a subprocess
        self.process = subprocess.Popen(
            [sys.executable, "-m", "edeon_models.ipc.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ
        )
        # Read initial ready signal from standard output
        ready_line = self.process.stdout.readline().strip()
        ready_data = json.loads(ready_line)
        assert ready_data.get("result") == "ready"

    def tearDown(self):
        if self.process.poll() is None:
            try:
                # Send quit signal
                self.process.stdin.write(json.dumps({"id": "99", "command": "quit"}) + "\n")
                self.process.stdin.flush()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.stderr.close()

    def send_request(self, command: str, args: dict, req_id: str = "1") -> dict:
        request = {"id": req_id, "command": command, "args": args}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        response_line = self.process.stdout.readline().strip()
        return json.loads(response_line)

    def test_stdio_list_endpoints(self):
        resp = self.send_request("list_endpoints", {})
        self.assertEqual(resp["id"], "1")
        self.assertIsNone(resp["error"])
        self.assertIsInstance(resp["result"], list)
        self.assertEqual(len(resp["result"]), 16)

    def test_stdio_get_card(self):
        resp = self.send_request("get_card", {"model_id": "bee_acute_oral_ld50.t2.0.1.0-legacy"})
        self.assertEqual(resp["id"], "1")
        self.assertIsNone(resp["error"])
        self.assertEqual(resp["result"]["model_id"], "bee_acute_oral_ld50.t2.0.1.0-legacy")

    def test_stdio_predict(self):
        resp = self.send_request("predict", {
            "endpoint": "bee_acute_oral_ld50",
            "smiles": ["CCO"],
            "preferred_tier": 2
        })
        self.assertEqual(resp["id"], "1")
        self.assertIsNone(resp["error"])
        self.assertIsInstance(resp["result"], list)
        self.assertEqual(len(resp["result"]), 1)
        self.assertEqual(resp["result"][0]["smiles"], "CCO")

if __name__ == "__main__":
    unittest.main()
