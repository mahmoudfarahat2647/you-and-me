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

#[cfg(test)]
mod tests {
    #[test]
    fn startup_does_not_embed_a_developer_checkout_path() {
        let source = include_str!("backend.rs");
        let forbidden = ["D:", "\\you-and-me"].concat();
        assert!(!source.contains(&forbidden), "startup embeds a developer checkout path");
    }
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
        let root = Self::find_development_root()?;
        let python = root.join(".venv").join("Scripts").join("python.exe");
        if python.is_file() {
            Ok(python)
        } else {
            Err(format!("Python runtime not found at {}. Create the repository virtual environment and install the backend dependencies.", python.display()))
        }
    }

    fn find_development_root() -> Result<PathBuf, String> {
        Path::new(env!("CARGO_MANIFEST_DIR")).ancestors()
            .find(|root| root.join("pyproject.toml").is_file()
                && root.join("src/adapters/api/server.py").is_file())
            .map(Path::to_path_buf)
            .ok_or_else(|| "Backend development root not found. Run the desktop app from a complete source checkout; packaged backend runtime is not available.".to_string())
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

        let working_dir = Self::find_development_root()?;

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
