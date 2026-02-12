from typing import Optional
import math
from edeon_models.backend import ModelBackend
from edeon_models.types import Prediction, PredictionValue, ADStatus, ModelCard
from edeon_models.endpoints import Endpoint
from edeon_engine.properties import compute_properties_single

class GUSIndex_T2(ModelBackend):
    _ENDPOINT = Endpoint.GUS_INDEX
    _VERSION = "0.1.0-legacy"
    _UNITS = "unitless"

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
                tpsa = props.get("tpsa", 60)
                if logp is None: logp = 2.0
                if mw is None: mw = 300
                if tpsa is None: tpsa = 60
                
                log_koc = max(0.0, min(6.0, 0.47 * logp + 1.09))
                dt50 = 20.0 * (1.0 + 0.3 * max(0.0, logp)) * (1.0 + 0.2 * max(0.0, (mw - 200.0) / 100.0)) * math.exp(-tpsa / 150.0)
                dt50 = max(2.0, min(365.0, dt50))
                
                gus = math.log10(dt50) * (4.0 - log_koc) if log_koc < 4.0 else 0.0
                
                out.append(Prediction(
                    smiles=s,
                    endpoint=self._ENDPOINT.value,
                    value=PredictionValue(kind="numeric", numeric=float(gus)),
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
                    value=PredictionValue(kind="numeric", numeric=float("nan")),
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
            name="Edeon Legacy GUS Index (LogP-based)",
            version=self._VERSION,
            tier=2,
            endpoint=self._ENDPOINT.value,
            description=(
                "Tier-2 baseline screening estimate of Gustafson groundwater ubiquity score "
                "using a LogP-based heuristic from the original Edeon implementation."
            ),
            intended_use="Early-stage triage and qualitative ranking only.",
            not_intended_for=[
                "Regulatory dossier submission",
                "Quantitative risk assessment",
            ],
            uncertainty_method=None,
            known_failure_modes=[
                "Structurally novel chemotypes outside typical agrochemical space",
            ],
            references=[],
            license="Proprietary",
            authors=["Edeon Development Team"],
        )
