# Licensing Audit for Edeon Phase 6

This document reviews the licensing terms of all bundled and optional third-party components introduced in Phase 6.

## Bundled Components
- **AutoDock Vina**: Apache License 2.0. Bundling with Edeon is fully compliant.
- **Meeko**: LGPL-2.1. Compliant to bundle as a Python dependency.

## Optional/User-Provided Components
- **GNINA**: GPL-2.0 / GPL-3.0. To comply with commercial licensing and avoid copyleft obligations, GNINA is **never** bundled. Support is opt-in via a user-provided binary path in the application settings.
- **Open Babel**: GPL-2.0. Invoked only if the user provides the binary locally.
