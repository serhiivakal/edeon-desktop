# Licensing Audit: Phase G — Feature G5 (pH-Dependent Speciation)

## Overview
Feature G5 introduces pH-dependent chemical speciation calculations for Edeon Desktop to enumerate protonation states, calculate Henderson–Hasselbalch fractional species distributions across target soil pH ranges (4.0–8.0), and select dominant chemical species for ecotox and fate models.

## Dependencies Audited

| Tool / Dependency | Primary License | Status | Notes |
|-------------------|-----------------|--------|-------|
| **Dimorphite-DL** | Apache-2.0 | **Approved** | Open-source Python package for protonation state enumeration over a specified pH window. |
| **pkasolver** | MIT | **Approved** | Graph neural network pKa predictor. Open-source MIT license. |
| **BR-SAScore / SAscore** | BSD-3-Clause / MIT | **Approved** | Embedded default fragment/ring complexity SA score. Runs locally with zero external network dependencies. |
| **AiZynthFinder** | MIT | **Approved** | Open-source MCTS template retrosynthesis planner. Optional heavy extra `retro`. |
| **RDKit** | BSD-3-Clause | **Approved** | Core cheminformatics library already embedded in Edeon. |

## Bundle Posture & Sidecar Safety
- BR-SAScore is included in base installation with zero external model weight dependencies.
- AiZynthFinder and ONNX models are registered under the `retro` optional-dependencies group in `pyproject.toml`.
- Heavy imports are lazily loaded inside handlers (`edeon_retro/ipc_handlers.py`).
- If `aizynthfinder` is absent, handlers return a structured `feature_unavailable` error envelope while falling back gracefully to BR-SAScore batch gating.
