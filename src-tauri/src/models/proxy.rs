use std::collections::HashMap;
use tauri::{AppHandle, Manager};
use serde_json::Value;
use thiserror::Error;

use crate::AppState;
use crate::models::types::{Prediction, ModelCard};

#[derive(Debug, Error)]
#[allow(dead_code)]
pub enum BackendError {
    #[error("Python IPC error: {0}")]
    IpcError(String),
    #[error("Database error: {0}")]
    DbError(String),
    #[error("Endpoint not found: {0}")]
    EndpointNotFound(String),
    #[error("Model load error: {0}")]
    ModelLoad(String),
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
    #[error("Other error: {0}")]
    Other(String),
}

pub struct BackendProxy {
    app: AppHandle,
}

impl BackendProxy {
    /// Create a new BackendProxy instance wrapped around the Tauri AppHandle.
    pub fn new(app: AppHandle) -> Self {
        Self { app }
    }

    /// Helper to safely acquire the Python engine, execute a JSON-RPC request, and release it back to AppState.
    /// Holds the Mutex for the duration of the Python call to prevent concurrent access.
    fn call_python(&self, method: &str, params: Value) -> Result<Value, BackendError> {
        let state = self.app.state::<AppState>();
        
        let mut py = state.get_python_engine()
            .map_err(|e| BackendError::IpcError(e))?;
        let engine = py.as_mut()
            .ok_or_else(|| BackendError::IpcError("Python engine not available".to_string()))?;
        
        engine.send_request(method, params)
            .map_err(|e| BackendError::IpcError(e))
    }

    /// Run point-estimate predictions using the Python engine.
    pub async fn predict(
        &self,
        endpoint: &str,
        smiles: Vec<String>,
        preferred_tier: Option<u8>,
    ) -> Result<Vec<Prediction>, BackendError> {
        // Read the DB preference first, then drop the DB lock before acquiring the Python lock
        let tier = {
            let state = self.app.state::<AppState>();
            let conn = state.db.lock().map_err(|e| BackendError::DbError(e.to_string()))?;
            match preferred_tier {
                Some(t) => Some(t),
                None => crate::models::preferences::get_preference(&conn, endpoint)
                    .map_err(|e| BackendError::DbError(e.to_string()))?,
            }
            // conn (MutexGuard) is dropped here
        };

        let params = serde_json::json!({
            "endpoint": endpoint,
            "smiles": smiles,
            "preferred_tier": tier,
        });
        let result = self.call_python("predict", params)?;
        let predictions: Vec<Prediction> = serde_json::from_value(result)?;
        Ok(predictions)
    }

    /// List registered backends for a given endpoint.
    pub async fn list_backends(&self, endpoint: &str) -> Result<Vec<ModelCard>, BackendError> {
        let params = serde_json::json!({
            "endpoint": endpoint,
        });
        let result = self.call_python("list_backends", params)?;
        let cards: Vec<ModelCard> = serde_json::from_value(result)?;
        Ok(cards)
    }

    /// Retrieve the ModelCard for a specific model_id.
    pub async fn get_card(&self, model_id: &str) -> Result<ModelCard, BackendError> {
        let params = serde_json::json!({
            "model_id": model_id,
        });
        let result = self.call_python("get_card", params)?;
        let card: ModelCard = serde_json::from_value(result)?;
        Ok(card)
    }

    /// Set database preference for a specific endpoint's tier.
    pub async fn set_preference(&self, endpoint: &str, tier: u8) -> Result<(), BackendError> {
        let state = self.app.state::<AppState>();
        let conn = state.db.lock().map_err(|e| BackendError::DbError(e.to_string()))?;
        crate::models::preferences::set_preference(&conn, endpoint, tier)
            .map_err(|e| BackendError::DbError(e.to_string()))?;
        Ok(())
    }

    /// Get current tier preferences for all endpoints.
    #[allow(dead_code)]
    pub async fn get_preferences(&self) -> Result<HashMap<String, u8>, BackendError> {
        let state = self.app.state::<AppState>();
        let conn = state.db.lock().map_err(|e| BackendError::DbError(e.to_string()))?;
        let preferences = crate::models::preferences::get_all_preferences(&conn)
            .map_err(|e| BackendError::DbError(e.to_string()))?;
        Ok(preferences)
    }

    /// Deploy a QSAR Studio model as a T4 backend.
    pub async fn deploy_studio_model(
        &self,
        saved_model_id: &str,
        endpoint: &str,
    ) -> Result<ModelCard, BackendError> {
        let params = serde_json::json!({
            "saved_model_id": saved_model_id,
            "endpoint": endpoint,
        });
        let result = self.call_python("deploy_studio_model", params)?;
        let card: ModelCard = serde_json::from_value(result)?;
        Ok(card)
    }

    /// Undeploy a QSAR Studio model.
    pub async fn undeploy_studio_model(&self, saved_model_id: &str) -> Result<(), BackendError> {
        let params = serde_json::json!({
            "saved_model_id": saved_model_id,
        });
        self.call_python("undeploy_studio_model", params)?;
        Ok(())
    }

    /// Retrieve calibration diagnostics for a given model ID.
    pub async fn get_calibration_diagnostics(&self, model_id: &str) -> Result<Value, BackendError> {
        let params = serde_json::json!({
            "model_id": model_id,
        });
        let result = self.call_python("get_calibration_diagnostics", params)?;
        Ok(result)
    }
}
