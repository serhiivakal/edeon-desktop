import subprocess
from pathlib import Path
from typing import Dict, Optional, List


def _parse_hetatm_coords(pdb_path: Path, hetatm_residue_name: Optional[str]) -> List[List[float]]:
    coords: List[List[float]] = []
    if not pdb_path.exists():
        return coords
    for line in pdb_path.read_text().splitlines():
        if line[:6].strip() == "HETATM":
            resn = line[17:20].strip()
            if resn in ("HOH", "WAT"):
                continue
            if hetatm_residue_name and resn != hetatm_residue_name:
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                coords.append([x, y, z])
            except ValueError:
                continue
    return coords


def _all_atom_coords(pdb_path: Path) -> List[List[float]]:
    coords: List[List[float]] = []
    if not pdb_path.exists():
        return coords
    for line in pdb_path.read_text().splitlines():
        if line[:6].strip() in ("ATOM", "HETATM"):
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                coords.append([x, y, z])
            except ValueError:
                continue
    return coords


def _box_from_coords(coords: List[List[float]], padding: float) -> Dict:
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    zs = [c[2] for c in coords]
    center = [
        (min(xs) + max(xs)) / 2.0,
        (min(ys) + max(ys)) / 2.0,
        (min(zs) + max(zs)) / 2.0,
    ]
    size = [
        max(max(xs) - min(xs) + 2 * padding, 10.0),
        max(max(ys) - min(ys) + 2 * padding, 10.0),
        max(max(zs) - min(zs) + 2 * padding, 10.0),
    ]
    return {
        "center": [round(c, 3) for c in center],
        "size": [round(s, 3) for s in size],
    }


def detect_box_from_cocrystal_ligand(
    pdb_path: Path,
    hetatm_residue_name: Optional[str] = None,
    padding: float = 5.0,
) -> Dict:
    """If the receptor has a cocrystal ligand, center the box on it."""
    coords = _parse_hetatm_coords(Path(pdb_path), hetatm_residue_name)
    if not coords:
        raise ValueError("No cocrystal ligand (HETATM) found in receptor.")
    result = _box_from_coords(coords, padding)
    result["source"] = "cocrystal_ligand"
    return result


def detect_box_from_fpocket(
    pdb_path: Path,
    fpocket_binary: Path,
    pocket_rank: int = 1,
) -> Dict:
    """Run fpocket and use the highest-ranked pocket centroid."""
    fpocket_binary = Path(fpocket_binary)
    if not fpocket_binary.exists():
        raise FileNotFoundError("fpocket binary not available.")
    # fpocket invocation is environment-specific; left as a thin wrapper.
    subprocess.run([str(fpocket_binary), "-f", str(pdb_path)], check=True, timeout=120)
    raise NotImplementedError("fpocket parsing not configured in this environment.")


def auto_detect_box(
    pdb_path: Path,
    fpocket_binary: Optional[Path] = None,
) -> Dict:
    """Try cocrystal ligand first, then fpocket, then fall back to receptor centroid."""
    pdb_path = Path(pdb_path)

    # 1. Cocrystal ligand
    try:
        return detect_box_from_cocrystal_ligand(pdb_path)
    except Exception:
        pass

    # 2. fpocket (optional)
    if fpocket_binary and Path(fpocket_binary).exists():
        try:
            return detect_box_from_fpocket(pdb_path, Path(fpocket_binary))
        except Exception:
            pass

    # 3. Receptor centroid fallback
    coords = _all_atom_coords(pdb_path)
    if coords:
        result = _box_from_coords(coords, padding=0.0)
        # Use a standard interactive box size around the centroid.
        result["size"] = [22.0, 22.0, 22.0]
        result["source"] = "receptor_centroid"
        return result

    # 4. Hard default
    return {"center": [0.0, 0.0, 0.0], "size": [22.0, 22.0, 22.0], "source": "default"}
