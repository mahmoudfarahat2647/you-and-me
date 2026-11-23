use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackendProcessInfo {
    pub running: bool,
    pub port: u16,
    pub error: Option<String>,
}

pub struct BackendState {
    pub child: Mutex<Option<Child>>,
    pub port: u16,
    pub last_error: Mutex<Option<String>>,
}

impl BackendState {
    pub fn new(port: u16) -> Self {
        Self {
            child: Mutex::new(None),
            port,
            last_error: Mutex::new(None),
        }
    }

    pub fn find_python_path() -> Result<PathBuf, String> {
        // 1. Check workspace .venv
        let candidates = [
            PathBuf::from(r"D:\you-and-me\.venv\Scripts\python.exe"),
            PathBuf::from(r"..\.venv\Scripts\python.exe"),
            PathBuf::from(r"..\..\.venv\Scripts\python.exe"),
            PathBuf::from(r".venv\Scripts\python.exe"),
        ];

        for candidate in &candidates {
            if candidate.exists() {
                return Ok(candidate.clone());
            }
        }

        // 2. Check if python is on PATH
        if let Ok(output) = Command::new("where").arg("python.exe").output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                if let Some(line) = stdout.lines().next() {
                    let p = PathBuf::from(line.trim());
                    if p.exists() {
                        return Ok(p);
                    }
                }
            }
        }

        Err("Python executable not found in .venv/Scripts/python.exe or PATH. Please ensure Python 3.12+ is installed.".to_string())
    }

    pub fn start(&self) -> Result<(), String> {
        let mut child_guard = self.child.lock().map_err(|e| e.to_string())?;
        if child_guard.is_some() {
            // Already running
            return Ok(());
        }

        let python_path = match Self::find_python_path() {
            Ok(p) => p,
            Err(err) => {
                let mut err_guard = self.last_error.lock().map_err(|e| e.to_string())?;
                *err_guard = Some(err.clone());
                return Err(err);
            }
        };

        // Determine working directory (root of repository)
        let working_dir = if Path::new(r"D:\you-and-me").exists() {
            PathBuf::from(r"D:\you-and-me")
        } else {
            std::env::current_dir()
                .unwrap_or_else(|_| PathBuf::from("."))
                .parent()
                .unwrap_or_else(|| Path::new("."))
                .to_path_buf()
        };

        let mut cmd = Command::new(&python_path);
        cmd.args(["-m", "src.adapters.api.server", "--port", &self.port.to_string()])
            .current_dir(&working_dir);

        match cmd.spawn() {
            Ok(child) => {
                *child_guard = Some(child);
                let mut err_guard = self.last_error.lock().map_err(|e| e.to_string())?;
                *err_guard = None;
                Ok(())
            }
            Err(e) => {
                let err_msg = format!("Failed to spawn local backend: {}", e);
                let mut err_guard = self.last_error.lock().map_err(|e| e.to_string())?;
                *err_guard = Some(err_msg.clone());
                Err(err_msg)
            }
        }
    }

    pub fn stop(&self) {
        if let Ok(mut child_guard) = self.child.lock() {
            if let Some(mut child) = child_guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }

    pub fn get_status(&self) -> BackendProcessInfo {
        let mut running = false;
        if let Ok(mut child_guard) = self.child.lock() {
            if let Some(child) = child_guard.as_mut() {
                match child.try_wait() {
                    Ok(None) => running = true, // process still running
                    Ok(Some(status)) => {
                        let _ = child_guard.take();
                        if let Ok(mut err_guard) = self.last_error.lock() {
                            *err_guard = Some(format!("Backend process exited unexpectedly with {}", status));
                        }
                    }
                    Err(e) => {
                        let _ = child_guard.take();
                        if let Ok(mut err_guard) = self.last_error.lock() {
                            *err_guard = Some(format!("Error querying backend process: {}", e));
                        }
                    }
                }
            }
        }

        let error = self.last_error.lock().ok().and_then(|g| g.clone());

        BackendProcessInfo {
            running,
            port: self.port,
            error,
        }
    }
}
