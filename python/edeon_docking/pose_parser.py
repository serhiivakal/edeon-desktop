import re
from pathlib import Path
from typing import List, Optional
from .schema import DockedPose


def parse_vina_output_pdbqt(pdbqt_path: Path) -> List[DockedPose]:
    """Parse Vina's multi-model PDBQT output.

    Each MODEL ... ENDMDL block is one pose. The Vina score and RMSD bounds are
    stored on a `REMARK VINA RESULT:` line as three floats:
        REMARK VINA RESULT:    -8.5      0.000      0.000
    """
    pdbqt_path = Path(pdbqt_path)
    if not pdbqt_path.exists():
        return []

    text = pdbqt_path.read_text()
    poses: List[DockedPose] = []

    current_lines: List[str] = []
    in_model = False
    pose_index = 0
    score: Optional[float] = None
    rmsd_lb: Optional[float] = None
    rmsd_ub: Optional[float] = None

    def flush():
        nonlocal pose_index, score, rmsd_lb, rmsd_ub, current_lines
        if not current_lines:
            return
        pose_index += 1
        poses.append(
            DockedPose(
                pose_index=pose_index,
                score_kcal_per_mol=score if score is not None else 0.0,
                rmsd_to_top=rmsd_lb,
                rmsd_to_prev=rmsd_ub,
                pdbqt_block="".join(current_lines),
            )
        )

    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("MODEL"):
            in_model = True
            current_lines = [line]
            score = None
            rmsd_lb = None
            rmsd_ub = None
            continue

        if in_model:
            current_lines.append(line)

        if "VINA RESULT" in stripped:
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", stripped)
            if nums:
                try:
                    score = float(nums[0])
                    if len(nums) > 1:
                        rmsd_lb = float(nums[1])
                    if len(nums) > 2:
                        rmsd_ub = float(nums[2])
                except ValueError:
                    pass

        if stripped.startswith("ENDMDL"):
            flush()
            in_model = False
            current_lines = []

    # Handle a trailing block with no ENDMDL.
    if in_model and current_lines:
        flush()

    return poses
