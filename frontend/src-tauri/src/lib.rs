mod backend;

use backend::{BackendProcessInfo, BackendState};
use tauri::{Manager, State};

#[tauri::command]
fn get_backend_status(state: State<BackendState>) -> BackendProcessInfo {
    state.get_status()
}

#[tauri::command]
fn restart_backend(state: State<BackendState>) -> Result<BackendProcessInfo, String> {
    state.stop();
    let _ = state.start();
    Ok(state.get_status())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend = BackendState::new(8000);
    // Attempt starting local backend process on app launch
    let _ = backend.start();

    tauri::Builder::default()
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .manage(backend)
        .invoke_handler(tauri::generate_handler![
            get_backend_status,
            restart_backend
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(state) = app_handle.try_state::<BackendState>() {
                    state.stop();
                }
            }
        });
}
