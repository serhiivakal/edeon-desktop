"""Experimental value prediction overlay service for Edeon Phase 2.

Enriches model predictions with matching historical, curated measurements
stored in the ExperimentalValueIndex before they are returned to the Tauri frontend.
"""

import logging
from typing import List
from edeon_models.types import Prediction
from edeon_models.endpoints import Endpoint
from edeon_models.overlay.lookup import ExperimentalValueIndex

logger = logging.getLogger("edeon_models.overlay.service")

class OverlayService:
    """Attaches experimental curated values to Prediction provenance objects."""
    
    def __init__(self, index: ExperimentalValueIndex):
        self._index = index

    def enrich(self, predictions: List[Prediction]) -> List[Prediction]:
        """Scans the index for each prediction and attaches experimental records to provenance."""
        if not predictions:
            return []
            
        enriched_predictions = []
        for pred in predictions:
            try:
                # Try to map prediction endpoint to enum
                ep = Endpoint(pred.endpoint)
                
                # Perform lookup in our in-memory index
                exp_values = self._index.lookup_smiles(pred.smiles, ep)
                
                if exp_values:
                    # Since Prediction is frozen (ConfigDict(frozen=True)), we must use model_copy
                    updated_prov = dict(pred.provenance) if pred.provenance else {}
                    
                    # Cap at the 3 highest quality / most recent records (mitigates frontend overflow)
                    # For simplicity, since curated data has high-quality aggregated rows, we take the top 3
                    updated_prov["experimental_values"] = exp_values[:3]
                    
                    # Return copy with updated provenance
                    enriched_pred = pred.model_copy(update={"provenance": updated_prov})
                    enriched_predictions.append(enriched_pred)
                    logger.debug(f"Enriched prediction for SMILES {pred.smiles} with {len(exp_values)} experimental records.")
                else:
                    enriched_predictions.append(pred)
            except Exception as e:
                logger.warning(f"Failed to enrich prediction for SMILES {pred.smiles}: {e}")
                enriched_predictions.append(pred)
                
        return enriched_predictions
