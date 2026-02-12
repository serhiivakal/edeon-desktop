import os
import subprocess
import time
from pathlib import Path
from typing import Tuple, List, Optional
from .schema import DockingResult, DockedPose


class GninaRunner:
    """Optional GNINA runner.

    GNINA is GPL-licensed and therefore never bundled with Edeon. The user must
    supply a path to their own GNINA binary via settings. If no valid binary is
    provided, the runner reports itself unavailable rather than failing silently.
    """

    def __init__(self, gnina_binary: Optional[Path]):
        self._binary = Path(gnina_binary) if gnina_binary else None

    @property
    def available(self) -> bool:
        return bool(
            self._binary
            and self._binary.exists()
            and os.access(self._binary, os.X_OK)
        )

    def run(
        self,
        receptor_pdbqt: Path,
        ligand_pdbqt: Path,
        center: Tuple[float, float, float],
        size: Tuple[float, float, float] = (22.0, 22.0, 22.0),
        exhaustiveness: int = 8,
        num_modes: int = 9,
        cnn_scoring: str = "rescore",
        output_sdf: Optional[Path] = None,
        timeout_sec: int = 600,
    ) -> DockingResult:
        if not self.available:
            raise RuntimeError(
                "GNINA binary not available. Provide a valid GNINA path in Settings "
                "to enable CNN-rescored docking. (GNINA is GPL-licensed and is not "
                "bundled with Edeon.)"
            )

        output_sdf = Path(output_sdf) if output_sdf else Path("gnina_poses.sdf")
        cmd = [
            str(self._binary),
            "--receptor", str(receptor_pdbqt),
            "--ligand", str(ligand_pdbqt),
            "--center_x", f"{center[0]:.3f}",
            "--center_y", f"{center[1]:.3f}",
            "--center_z", f"{center[2]:.3f}",
            "--size_x", f"{size[0]:.3f}",
            "--size_y", f"{size[1]:.3f}",
            "--size_z", f"{size[2]:.3f}",
            "--exhaustiveness", str(exhaustiveness),
            "--num_modes", str(num_modes),
            "--cnn_scoring", cnn_scoring,
            "--out", str(output_sdf),
        ]

        start = time.time()
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
        )
        elapsed = time.time() - start

        if proc.returncode != 0:
            raise RuntimeError(f"GNINA failed: {proc.stderr.strip()}")

        # Parsing of GNINA SDF output (Vina affinity + CNNscore tags) is left to the
        # production parser; here we surface the raw run as a result placeholder.
        poses: List[DockedPose] = []
        return DockingResult(
            poses=poses,
            vina_version="GNINA (user-provided)",
            command_line=" ".join(cmd),
            elapsed_time_sec=elapsed,
            warnings=[w for w in [proc.stderr.strip()] if w],
        )
