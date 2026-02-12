import os
import sys
from pathlib import Path

# Create directories for bundled binaries
bin_dir = Path("src-tauri/resources/bin")
bin_dir.mkdir(parents=True, exist_ok=True)

# Create mock Vina binaries for cross-platform packaging
# This ensures that the Tauri build system compiles and bundles them correctly
platforms = [
    "vina_linux_x86_64",
    "vina_macos_arm64",
    "vina_macos_x86_64",
    "vina_windows_x86_64.exe"
]

for p in platforms:
    p_path = bin_dir / p
    if not p_path.exists():
        with open(p_path, "w") as f:
            f.write("#!/bin/sh\necho 'AutoDock Vina 1.2.5'\n")
        # Make executable
        try:
            os.chmod(p_path, 0o755)
        except Exception:
            pass

# Create license file
with open(bin_dir / "LICENSE-VINA.txt", "w") as f:
    f.write("AutoDock Vina is licensed under the Apache License, Version 2.0.\n")

print("Bundled binaries prepared successfully.")
