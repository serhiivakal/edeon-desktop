import os
import socket
import subprocess
import tarfile
import threading
import time
from pathlib import Path
import requests

class OllamaManager:
    """
    Manages downloading, installing, starting, and pulling models for
    the local Ollama sidecar service inside Edeon's WSL environment.
    """
    
    def __init__(self, app_data_dir: str):
        self.app_data_dir = Path(app_data_dir)
        self.bin_dir = self.app_data_dir / "bin"
        self.ollama_bin = self.bin_dir / "ollama"
        
        # Installation / download status
        self.status = "idle" # "idle", "downloading", "starting", "pulling", "ready", "failed"
        self.progress = 0 # 0 to 100 percentage
        self.error_message = None
        self._lock = threading.Lock()
        
    def get_status(self) -> dict:
        """Returns the current manager state."""
        with self._lock:
            # Check if active on standard port
            running = self.is_port_active(11434)
            state = self.status
            if running and state in ("idle", "failed"):
                state = "ready"
            return {
                "status": state,
                "progress": self.progress,
                "running": running,
                "error": self.error_message,
                "binary_exists": self.ollama_bin.exists()
            }

    @staticmethod
    def is_port_active(port: int) -> bool:
        """Checks if a local port is listening."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(("127.0.0.1", port))
                return True
        except Exception:
            return False

    def start_install_and_run_async(self, model_name: str = "qwen2.5:3b"):
        """Launches installation and startup in a background thread."""
        thread = threading.Thread(target=self._run_sequence, args=(model_name,))
        thread.daemon = True
        thread.start()

    def _run_sequence(self, model_name: str):
        try:
            # 1. Check if already running on port 11434
            if self.is_port_active(11434):
                with self._lock:
                    self.status = "ready"
                    self.progress = 100
                self.ensure_model(model_name)
                return

            # 2. Download and extract binary if missing
            if not self.ollama_bin.exists():
                self.download_and_extract_ollama()

            # 3. Start the server
            self.start_server()

            # 4. Pull the model
            self.ensure_model(model_name)
            
            with self._lock:
                self.status = "ready"
                self.progress = 100
                
        except Exception as e:
            with self._lock:
                self.status = "failed"
                self.error_message = str(e)

    def download_and_extract_ollama(self):
        """Downloads the official Linux binary directly without requiring extraction tools."""
        with self._lock:
            self.status = "downloading"
            self.progress = 0
            self.error_message = None

        self.bin_dir.mkdir(parents=True, exist_ok=True)
        url = "https://github.com/ollama/ollama/releases/download/v0.3.4/ollama-linux-amd64"

        try:
            # Download file in chunks to show progress
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            downloaded = 0
            with open(self.ollama_bin, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            with self._lock:
                                self.progress = percent
                        
            # Set executable permissions
            os.chmod(self.ollama_bin, 0o755)

        except Exception as e:
            if self.ollama_bin.exists():
                try:
                    os.remove(self.ollama_bin)
                except Exception:
                    pass
            raise e

    def start_server(self):
        """Starts the Ollama server in the background."""
        with self._lock:
            self.status = "starting"
            self.progress = 0

        # Start process with OLLAMA_HOST=127.0.0.1 to avoid binding issues
        env = os.environ.copy()
        env["OLLAMA_HOST"] = "127.0.0.1"
        
        # Start serve daemon
        subprocess.Popen(
            [str(self.ollama_bin), "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env
        )

        # Wait up to 15 seconds for port to open
        for i in range(15):
            time.sleep(1.0)
            if self.is_port_active(11434):
                return
            with self._lock:
                self.progress = int(((i + 1) / 15) * 100)

        raise RuntimeError("Failed to start local Ollama server daemon on port 11434")

    def ensure_model(self, model_name: str):
        """Checks if the local model exists, and pulls it if missing."""
        with self._lock:
            self.status = "pulling"
            self.progress = 0

        # 1. Check if model is already pulled
        try:
            resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
            if resp.status_code == 200:
                tags = resp.json().get("models", [])
                if any(model_name in t.get("name", "") for t in tags):
                    # Already exists
                    return
        except Exception:
            pass

        # 2. Trigger asynchronous pull via Ollama API
        url = "http://127.0.0.1:11434/api/pull"
        payload = {"name": model_name, "stream": True}
        
        try:
            response = requests.post(url, json=payload, stream=True, timeout=600)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    import json
                    try:
                        data = json.loads(line.decode('utf-8'))
                        # Some status lines return progress
                        if "completed" in data and "total" in data:
                            total = data["total"]
                            completed = data["completed"]
                            if total > 0:
                                percent = int((completed / total) * 100)
                                with self._lock:
                                    self.progress = percent
                    except Exception:
                        pass
        except Exception as e:
            raise RuntimeError(f"Failed to pull model '{model_name}': {e}")
