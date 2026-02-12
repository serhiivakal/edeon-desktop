/// Edeon Desktop — Reference Library Commands
///
/// Tauri IPC handlers for querying the marketed reference active agrochemicals library.

use crate::AppState;
use serde_json::json;
use tauri::State;

#[tauri::command]
pub fn list_reference_actives(
    state: State<'_, AppState>,
    by: String,
    query: String,
    limit: Option<u32>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "reference_lookup",
        json!({
            "by": by,
            "query": query,
            "limit": limit.unwrap_or(10),
        }),
    )
}
