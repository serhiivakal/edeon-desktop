/// Edeon Desktop — Python Engine Manager
///
/// Spawns and manages the Python cheminformatics engine process.
/// Communicates via JSON-RPC over stdin/stdout (line-delimited JSON).

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use tauri::Emitter;

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
            .stderr(Stdio::inherit())
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

    /// Send a JSON-RPC request, processing intermediate log/progress streams, and read the final response.
    pub fn send_request_with_app(&mut self, method: &str, params: Value, app: Option<&tauri::AppHandle>) -> Result<Value, String> {
        let id = self.request_id.fetch_add(1, Ordering::SeqCst);

        let request = serde_json::json!({
            "id": id,
            "method": method,
            "params": params,
        });

        self.write_line(&request.to_string())?;

        loop {
            let response_line = self.read_line()?;
            
            if response_line.starts_with("[TRIAL_RESULT]") {
                if let Some(app_handle) = app {
                    let payload_str = response_line["[TRIAL_RESULT]".len()..].trim();
                    if let Ok(payload_val) = serde_json::from_str::<serde_json::Value>(payload_str) {
                        let _ = app_handle.emit("training://trial", payload_val);
                    }
                }
                continue;
            }
            
            if response_line.starts_with("[ARENA_PROGRESS]") {
                if let Some(app_handle) = app {
                    let payload_str = response_line["[ARENA_PROGRESS]".len()..].trim();
                    if let Ok(payload_val) = serde_json::from_str::<serde_json::Value>(payload_str) {
                        let _ = app_handle.emit("arena://progress", payload_val);
                    }
                }
                continue;
            }

            if response_line.starts_with("[DOCKING_PROGRESS]") {
                if let Some(app_handle) = app {
                    let payload_str = response_line["[DOCKING_PROGRESS]".len()..].trim();
                    if let Ok(payload_val) = serde_json::from_str::<serde_json::Value>(payload_str) {
                        let _ = app_handle.emit("docking://progress", payload_val);
                    }
                }
                continue;
            }

            if response_line.starts_with("[WORKFLOW_PROGRESS]") {
                if let Some(app_handle) = app {
                    let payload_str = response_line["[WORKFLOW_PROGRESS]".len()..].trim();
                    if let Ok(payload_val) = serde_json::from_str::<serde_json::Value>(payload_str) {
                        let _ = app_handle.emit("workflow://progress", payload_val);
                    }
                }
                continue;
            }

            let response: Value = serde_json::from_str(&response_line)
                .map_err(|e| format!("Invalid JSON from Python: {} (line: {})", e, response_line))?;

            // Check for error
            if let Some(error) = response.get("error") {
                return Err(format!("Python engine error: {}", error));
            }

            return Ok(response.get("result").cloned().unwrap_or(Value::Null));
        }
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

    /// Check if the Python engine process is still running.
    pub fn is_alive(&mut self) -> bool {
        match self.child.try_wait() {
            Ok(None) => true,
            _ => false,
        }
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
pub fn find_python() -> Result<String, String> {
    // 0. Check absolute Miniconda/Anaconda paths directly for the user's WSL environment
    let direct_paths = [
        "/home/svakal/miniconda3/envs/poe/bin/python3",
        "/home/svakal/miniconda3/envs/poe/bin/python",
        "/home/svakal/miniconda3/bin/python3",
        "/home/svakal/miniconda3/bin/python",
        "/home/svakal/anaconda3/bin/python3",
        "/home/svakal/anaconda3/bin/python",
    ];
    for path in &direct_paths {
        if std::path::Path::new(path).exists() {
            return Ok(path.to_string());
        }
    }

    // 1. Check common Conda paths in the user's HOME directory
    if let Ok(home) = std::env::var("HOME") {
        let paths = [
            format!("{}/miniconda3/envs/poe/bin/python3", home),
            format!("{}/miniconda3/envs/poe/bin/python", home),
            format!("{}/miniconda3/bin/python3", home),
            format!("{}/miniconda3/bin/python", home),
            format!("{}/anaconda3/bin/python3", home),
            format!("{}/anaconda3/bin/python", home),
        ];
        for path in &paths {
            if std::path::Path::new(path).exists() {
                return Ok(path.clone());
            }
        }
    }

    // 2. Check for local virtual environment (.venv) inside CWD
    for local_path in &["./.venv/bin/python3", "./.venv/bin/python", "../.venv/bin/python3", "../.venv/bin/python"] {
        if std::path::Path::new(local_path).exists() {
            if let Ok(full_path) = std::fs::canonicalize(local_path) {
                if let Some(path_str) = full_path.to_str() {
                    return Ok(path_str.to_string());
                }
            }
        }
    }

    // 3. Fall back to standard commands on the system PATH
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

