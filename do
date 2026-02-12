# Edeon Phase 6 — Technical Documentation & Notes

## Vina Binary Versions
- Linux x86_64: `vina_linux_x86_64` (AutoDock Vina 1.2.5)
- macOS arm64: `vina_macos_arm64` (AutoDock Vina 1.2.5)
- macOS x86_64: `vina_macos_x86_64` (AutoDock Vina 1.2.5)
- Windows x86_64: `vina_windows_x86_64.exe` (AutoDock Vina 1.2.5)

## SwissBioisostere Licensing Resolution
Derived bioisosteric rules are unencumbered and packaged within a local SQLite database (`bioisostere.db`) to comply with academic and commercial licensing restrictions.

## mmpdb & ChEMBL Version
- ChEMBL version: v33
- mmpdb version: 3.0

## fpocket Availability
fpocket is optional and falls back gracefully to cocrystal ligand or receptor centroid-based binding box detection.
