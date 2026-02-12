/// Edeon Desktop — Knowledge Commands
///
/// Tauri IPC handlers for querying unified agrochemical registries and AI Q&A RAG engine.

use crate::AppState;
use serde_json::json;
use tauri::State;

/// Dynamically queries SQLite for the absolute path to the main database file.
fn get_db_path(state: &State<'_, AppState>) -> Result<String, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let path: String = db.query_row(
        "SELECT file FROM pragma_database_list WHERE name='main'",
        [],
        |row| row.get(0),
    )
    .map_err(|e| e.to_string())?;
    Ok(path)
}

#[tauri::command]
pub fn search_knowledge(
    state: State<'_, AppState>,
    query: String,
    databases: Vec<String>,
) -> Result<serde_json::Value, String> {
    if query.trim().is_empty() && databases.is_empty() {
        return Ok(json!([]));
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "search_knowledge",
        json!({
            "query": query,
            "databases": databases,
        }),
    )
}

#[tauri::command]
pub fn knowledge_qa_ask(
    state: State<'_, AppState>,
    query: String,
    conversation_id: Option<String>,
    provider: Option<String>,
    api_key: Option<String>,
    model: Option<String>,
    local_endpoint: Option<String>,
    local_model: Option<String>,
    local_api_key: Option<String>,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "knowledge_qa_ask",
        json!({
            "query": query,
            "conversation_id": conversation_id,
            "db_path": db_path,
            "provider": provider.unwrap_or_else(|| "local".to_string()),
            "api_key": api_key.unwrap_or_default(),
            "model": model.unwrap_or_else(|| "claude-3-5-haiku-20241022".to_string()),
            "local_endpoint": local_endpoint.unwrap_or_else(|| "http://localhost:11434/v1".to_string()),
            "local_model": local_model.unwrap_or_else(|| "qwen2.5:3b".to_string()),
            "local_api_key": local_api_key.unwrap_or_default(),
        }),
    )
}

#[tauri::command]
pub fn knowledge_qa_list_conversations(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "knowledge_qa_list_conversations",
        json!({ "db_path": db_path }),
    )
}

#[tauri::command]
pub fn knowledge_qa_load_conversation(
    state: State<'_, AppState>,
    conversation_id: String,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "knowledge_qa_load_conversation",
        json!({ "db_path": db_path, "conversation_id": conversation_id }),
    )
}

#[tauri::command]
pub fn knowledge_qa_star_conversation(
    state: State<'_, AppState>,
    conversation_id: String,
    starred: bool,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "knowledge_qa_star_conversation",
        json!({ "db_path": db_path, "conversation_id": conversation_id, "starred": starred }),
    )
}

#[tauri::command]
pub fn knowledge_qa_delete_conversation(
    state: State<'_, AppState>,
    conversation_id: String,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "knowledge_qa_delete_conversation",
        json!({ "db_path": db_path, "conversation_id": conversation_id }),
    )
}

#[tauri::command]
pub fn knowledge_qa_reindex(
    state: State<'_, AppState>,
    force: bool,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "knowledge_qa_reindex",
        json!({ "db_path": db_path, "force": force }),
    )
}

#[tauri::command]
pub fn ollama_check_status(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "ollama_check_status",
        json!({ "db_path": db_path }),
    )
}

#[tauri::command]
pub fn ollama_start_sidecar(
    state: State<'_, AppState>,
    model_name: String,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "ollama_start_sidecar",
        json!({ "db_path": db_path, "model_name": model_name }),
    )
}
