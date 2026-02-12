from typing import Optional
import math
from edeon_models.backend import ModelBackend
from edeon_models.types import Prediction, PredictionValue, ADStatus, ModelCard
from edeon_models.endpoints import Endpoint
from edeon_engine.properties import compute_properties_single

class SkinSensitization_T2(ModelBackend):
    _ENDPOINT = Endpoint.SKIN_SENSITIZATION
    _VERSION = "0.1.0-legacy"
    _UNITS = "category"

    def endpoint(self) -> Endpoint: return self._ENDPOINT
    def tier(self) -> int: return 2
    def version(self) -> str: return self._VERSION

    def predict(self, smiles: list[str], conditions: Optional[dict] = None) -> list[Prediction]:
        out = []
        for s in smiles:
            try:
                props = compute_properties_single(s)
                if not props.get("valid", False):
                    raise ValueError("Invalid SMILES structure.")
                logp = props.get("logp", 2.0)
                mw = props.get("mol_weight", 300)
                if logp is None: logp = 2.0
                if mw is None: mw = 300
                
                if logp > 3.5 and mw < 400:
                    value = "Strong"
                elif logp > 2.0 and mw < 500:
                    value = "Weak"
                else:
                    value = "Non-sensitizer"
                    
                out.append(Prediction(
                    smiles=s,
                    endpoint=self._ENDPOINT.value,
                    value=PredictionValue(kind="categorical", categorical=value),
                    ad_status=ADStatus.UNKNOWN,
                    units=self._UNITS,
                    model_id=self.model_id(),
                    model_version=self._VERSION,
                    tier=2,
                    warnings=["Screening estimate — Tier-2 LogP-based heuristic"],
                ))
            except Exception as e:
                out.append(Prediction(
                    smiles=s,
                    endpoint=self._ENDPOINT.value,
                    value=PredictionValue(kind="categorical", categorical="Unknown"),
                    ad_status=ADStatus.UNKNOWN,
                    units=self._UNITS,
                    model_id=self.model_id(),
                    model_version=self._VERSION,
                    tier=2,
                    warnings=[f"Prediction failed: {e}"],
                ))
        return out

    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        return [ADStatus.UNKNOWN] * len(smiles)

    def metadata(self) -> ModelCard:
        return ModelCard(
            model_id=self.model_id(),
            name="Edeon Legacy Skin Sensitization (LogP-based)",
            version=self._VERSION,
            tier=2,
            endpoint=self._ENDPOINT.value,
            description=(
                "Tier-2 baseline screening estimate of skin sensitization "
                "using a LogP-based heuristic from the original Edeon implementation."
            ),
            intended_use="Early-stage triage and qualitative ranking only.",
            not_intended_for=[
                "Regulatory dossier submission",
                "Quantitative risk assessment",
                "Replacement of LLNA testing",
            ],
            uncertainty_method=None,
            known_failure_modes=[
                "Structurally novel chemotypes outside typical agrochemical space",
            ],
            references=[],
            license="Proprietary",
            authors=["Edeon Development Team"],
        )
