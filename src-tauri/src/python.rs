/// Edeon Desktop — Python Engine Manager
///
/// Spawns and manages the Python cheminformatics engine process.
/// Communicates via JSON-RPC over stdin/stdout (line-delimited JSON).

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};

use serde_json::Value;

pub struct PythonEngine {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    request_id: AtomicU64,
}

impl PythonEngine {
    /// Spawn the Python engine process.
    /// Looks for `python3` on PATH, falls back to `python`.
    pub fn spawn() -> Result<Self, String> {
        let python_cmd = find_python()?;

        let mut child = Command::new(&python_cmd)
            .arg("-m")
            .arg("edeon_engine")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .current_dir(Self::python_dir()?)
            .spawn()
            .map_err(|e| format!("Failed to spawn Python engine ({}): {}", python_cmd, e))?;

        let stdin = child.stdin.take().ok_or("Failed to get Python stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to get Python stdout")?;
        let stdout = BufReader::new(stdout);

        let mut engine = PythonEngine {
            child,
            stdin,
            stdout,
            request_id: AtomicU64::new(1),
        };

        // Wait for the "ready" signal from the engine
        let ready = engine.read_line()?;
        let ready: Value = serde_json::from_str(&ready)
            .map_err(|e| format!("Invalid ready signal from Python: {}", e))?;

        if ready.get("result").and_then(|v| v.as_str()) != Some("ready") {
            return Err(format!("Unexpected ready signal: {}", ready));
        }

        Ok(engine)
    }

    /// Get the path to the `python/` directory relative to the project root.
    fn python_dir() -> Result<std::path::PathBuf, String> {
        // In dev mode, the CWD is src-tauri/, so python/ is at ../python/
        let dev_path = std::path::PathBuf::from("../python");
        if dev_path.exists() {
            return Ok(dev_path);
        }

        // Also try the CWD itself (if running from project root)
        let root_path = std::path::PathBuf::from("python");
        if root_path.exists() {
            return Ok(root_path);
        }

        Err("Could not find python/ directory. Expected at ../python/ or ./python/".to_string())
    }

    /// Send a JSON-RPC request and read the response.
    pub fn send_request(&mut self, method: &str, params: Value) -> Result<Value, String> {
        let id = self.request_id.fetch_add(1, Ordering::SeqCst);

        let request = serde_json::json!({
            "id": id,
            "method": method,
            "params": params,
        });

        self.write_line(&request.to_string())?;
        let response_line = self.read_line()?;

        let response: Value = serde_json::from_str(&response_line)
            .map_err(|e| format!("Invalid JSON from Python: {} (line: {})", e, response_line))?;

        // Check for error
        if let Some(error) = response.get("error") {
            return Err(format!("Python engine error: {}", error));
        }

        Ok(response.get("result").cloned().unwrap_or(Value::Null))
    }

    /// Send a line to Python's stdin.
    fn write_line(&mut self, line: &str) -> Result<(), String> {
        writeln!(self.stdin, "{}", line)
            .map_err(|e| format!("Failed to write to Python stdin: {}", e))?;
        self.stdin.flush()
            .map_err(|e| format!("Failed to flush Python stdin: {}", e))?;
        Ok(())
    }

    /// Read a line from Python's stdout.
    fn read_line(&mut self) -> Result<String, String> {
        let mut line = String::new();
        self.stdout.read_line(&mut line)
            .map_err(|e| format!("Failed to read from Python stdout: {}", e))?;

        if line.is_empty() {
            return Err("Python engine closed stdout (process may have crashed)".to_string());
        }

        Ok(line.trim().to_string())
    }

    /// Health check — ping the engine.
    pub fn ping(&mut self) -> Result<bool, String> {
        let result = self.send_request("ping", serde_json::json!({}))?;
        Ok(result.as_str() == Some("pong"))
    }

    /// Gracefully shut down the engine.
    pub fn shutdown(&mut self) {
        // Try graceful quit
        let _ = self.send_request("quit", serde_json::json!({}));
        // Wait briefly, then kill if still running
        std::thread::sleep(std::time::Duration::from_millis(500));
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl Drop for PythonEngine {
    fn drop(&mut self) {
        self.shutdown();
    }
}

/// Find a working Python interpreter on the system.
fn find_python() -> Result<String, String> {
    for cmd in &["python3", "python"] {
        if Command::new(cmd)
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok()
        {
            return Ok(cmd.to_string());
        }
    }
    Err("Python not found. Please install Python 3 and ensure it's on your PATH.".to_string())
}
