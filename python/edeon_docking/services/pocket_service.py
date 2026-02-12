import os
import re
import json
import logging
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from ..schema import (
    PocketDetectionResult,
    FpocketResult
)
from .receptor_service import ReceptorService

logger = logging.getLogger("edeon_docking")

class PocketService:
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            self.base_dir = Path(__file__).resolve().parents[3]
            self.cache_dir = self.base_dir / "data" / "docking" / "cache"
        else:
            self.cache_dir = Path(cache_dir)
            self.base_dir = self.cache_dir.parents[2]
            
        self.pockets_dir = self.cache_dir / "pockets"
        self.pockets_dir.mkdir(parents=True, exist_ok=True)
        
        self.receptor_service = ReceptorService(self.cache_dir)

    def get_cached(self, receptor_hash: str) -> Optional[PocketDetectionResult]:
        """Check cache for pocket detection result."""
        cache_path = self.pockets_dir / receptor_hash / "pockets.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    data = json.load(f)
                    res = PocketDetectionResult.model_validate(data)
                    # If it was cached as empty, ignore it to force re-detection with fpocket
                    if not res.fpocket_results and not res.cocrystal_pockets:
                        return None
                    return res
            except Exception as e:
                logger.warning(f"Failed to read cached pockets at {cache_path}: {e}")
        return None

    def _parse_fpocket_output(self, out_dir: Path, base_name: str) -> List[FpocketResult]:
        """Parse fpocket info text and pocket pdb files."""
        info_file = out_dir / f"{base_name}_info.txt"
        pockets_pdb_dir = out_dir / "pockets"
        
        if not info_file.exists() or not pockets_pdb_dir.exists():
            logger.error(f"fpocket output files not found in: {out_dir}")
            return []
            
        # 1. Parse pocket parameters from the info file
        # Standard fpocket format:
        # Pocket 1 :
        #   - Druggability Score : 0.854
        #   - Volume : 1245.2
        pockets_meta = {}
        content = info_file.read_text()
        
        # Split by Pocket (\d+)
        pocket_blocks = re.split(r"Pocket\s+(\d+)\s*:", content)
        if len(pocket_blocks) > 1:
            for i in range(1, len(pocket_blocks), 2):
                pocket_id = int(pocket_blocks[i])
                block_content = pocket_blocks[i+1]
                
                drug_match = re.search(r"Druggability\s+Score\s*:\s*([\d\.]+)", block_content)
                vol_match = re.search(r"Volume\s*:\s*([\d\.]+)", block_content)
                
                drug_score = float(drug_match.group(1)) if drug_match else 0.0
                volume = float(vol_match.group(1)) if vol_match else 0.0
                
                pockets_meta[pocket_id] = {
                    "druggability_score": drug_score,
                    "volume": volume
                }

        # 2. Parse coordinates and residues from pocket PDB files
        fpocket_results: List[FpocketResult] = []
        
        pdb_files = list(pockets_pdb_dir.glob("pocket*_atm.pdb"))
        for pdb_file in pdb_files:
            # Extract pocket ID from filename e.g. pocket1_atm.pdb
            match_id = re.search(r"pocket(\d+)_atm\.pdb", pdb_file.name)
            if not match_id:
                continue
            pocket_id = int(match_id.group(1))
            
            coords = []
            pocket_residues = set()
            
            # Read atom coordinates and lining residues
            for line in pdb_file.read_text().splitlines():
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    try:
                        x = float(line[30:38])
                        y = float(line[38:46])
                        z = float(line[46:54])
                        coords.append((x, y, z))
                        
                        resname = line[17:20].strip()
                        chain = line[21:22].strip() or "A"
                        resnum = int(line[22:26].strip())
                        pocket_residues.add(f"{chain}:{resname}-{resnum}")
                    except ValueError:
                        continue
                        
            if not coords:
                continue
                
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            zs = [c[2] for c in coords]
            
            centroid = (
                sum(xs) / len(coords),
                sum(ys) / len(coords),
                sum(zs) / len(coords)
            )
            
            bounding_box = {
                "min_x": min(xs), "max_x": max(xs),
                "min_y": min(ys), "max_y": max(ys),
                "min_z": min(zs), "max_z": max(zs),
            }
            
            meta = pockets_meta.get(pocket_id, {"druggability_score": 0.0, "volume": 0.0})
            
            fpocket_results.append(FpocketResult(
                pocket_id=pocket_id,
                rank=0, # will rank shortly
                druggability_score=meta["druggability_score"],
                volume_angstrom_cubed=meta["volume"],
                centroid=[round(c, 3) for c in centroid],
                pocket_residues=sorted(list(pocket_residues)),
                bounding_box=bounding_box
            ))
            
        # Rank by druggability score descending
        fpocket_results.sort(key=lambda x: x.druggability_score, reverse=True)
        for rank, res in enumerate(fpocket_results, 1):
            res.rank = rank
            
        return fpocket_results

    def _calculate_receptor_centroid_and_box(self, pdb_path: Path) -> Tuple[Tuple[float, float, float], Dict[str, float]]:
        coords = []
        if pdb_path.exists():
            for line in pdb_path.read_text().splitlines():
                if line[:6].strip() in ("ATOM", "HETATM"):
                    try:
                        x = float(line[30:38])
                        y = float(line[38:46])
                        z = float(line[46:54])
                        coords.append((x, y, z))
                    except ValueError:
                        continue
        if not coords:
            return (0.0, 0.0, 0.0), {"min_x": 0.0, "max_x": 0.0, "min_y": 0.0, "max_y": 0.0, "min_z": 0.0, "max_z": 0.0}
        
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        zs = [c[2] for c in coords]
        
        centroid = (
            sum(xs) / len(coords),
            sum(ys) / len(coords),
            sum(zs) / len(coords)
        )
        
        bounding_box = {
            "min_x": min(xs), "max_x": max(xs),
            "min_y": min(ys), "max_y": max(ys),
            "min_z": min(zs), "max_z": max(zs),
        }
        
        return centroid, bounding_box

    async def detect(self, receptor_hash: str) -> PocketDetectionResult:
        """Run pocket detection on prepared receptor."""
        # Check cache
        cached = self.get_cached(receptor_hash)
        if cached:
            return cached
            
        # Resolve prepared receptor
        prepared_receptor = self.receptor_service.get_cached(receptor_hash)
        if not prepared_receptor:
            raise ValueError(f"Receptor not prepared/found in cache for hash: {receptor_hash}")
            
        cleaned_pdb_path = Path(prepared_receptor.pdbqt_path).parent / "cleaned.pdb"
        if not cleaned_pdb_path.exists():
            raise FileNotFoundError(f"Cleaned PDB file not found in receptor cache folder: {cleaned_pdb_path}")
            
        # 1. Gather cocrystal ligand pockets from receptor metadata
        cocrystal_pockets = []
        for lig in prepared_receptor.cocrystal_ligands:
            centroid = lig["centroid_xyz"]
            # Envelop with 5 Å padding
            cocrystal_pockets.append({
                "residue_name": lig["residue_name"],
                "chain_id": lig["chain_id"],
                "residue_number": lig["residue_number"],
                "centroid": centroid,
                "box_size": [15.0, 15.0, 15.0] # standard box size around cocrystal ligand
            })
            
        # 2. Run fpocket (if binary available)
        fpocket_bin = "/home/svakal/miniconda3/envs/docking/bin/fpocket"
        if not os.path.exists(fpocket_bin):
            fpocket_bin = "/home/svakal/.conda/envs/docking/bin/fpocket"
        if not os.path.exists(fpocket_bin):
            fpocket_bin = shutil.which("fpocket") or "fpocket"
            
        fpocket_results: List[FpocketResult] = []
        
        if os.path.exists(fpocket_bin):
            target_out_dir = self.pockets_dir / receptor_hash
            target_out_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy cleaned PDB to temp folder to run fpocket cleanly
            temp_pdb = target_out_dir / "cleaned.pdb"
            shutil.copy(cleaned_pdb_path, temp_pdb)
            
            # fpocket creates a folder named '<pdb_name>_out' in the same folder as PDB file
            cmd = [fpocket_bin, "-f", str(temp_pdb)]
            logger.info(f"Running fpocket: {' '.join(cmd)}")
            
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60
            )
            
            if proc.returncode == 0:
                # Parse
                out_dir = target_out_dir / "cleaned_out"
                fpocket_results = self._parse_fpocket_output(out_dir, "cleaned")
            else:
                logger.error(f"fpocket execution failed: {proc.stderr}")
        else:
            logger.warning(f"fpocket binary not found at {fpocket_bin}. Skipping fpocket pocket detection.")

        # 3. Prepend cocrystal pockets as top-ranked fpocket results
        # so any frontend code looking only at fpocket_results gets the best binding pocket
        co_results = []
        for idx, cop in enumerate(cocrystal_pockets, 1):
            co_results.append(FpocketResult(
                pocket_id=1000 + idx,  # distinct ID range for cocrystal pockets
                rank=idx,
                druggability_score=1.0,  # high score since it holds a cocrystal ligand
                volume_angstrom_cubed=1000.0,
                centroid=cop["centroid"],
                pocket_residues=[],  # we don't have residue list easily, but centroid is what matters
                bounding_box={
                    "min_x": cop["centroid"][0] - 7.5, "max_x": cop["centroid"][0] + 7.5,
                    "min_y": cop["centroid"][1] - 7.5, "max_y": cop["centroid"][1] + 7.5,
                    "min_z": cop["centroid"][2] - 7.5, "max_z": cop["centroid"][2] + 7.5,
                }
            ))
            
        if co_results:
            # Shift existing fpocket ranks down
            for r in fpocket_results:
                r.rank += len(co_results)
            fpocket_results = co_results + fpocket_results

        # 4. Fallback to receptor centroid if no pockets found
        if not fpocket_results:
            centroid, bbox = self._calculate_receptor_centroid_and_box(cleaned_pdb_path)
            fallback_pocket = FpocketResult(
                pocket_id=0,
                rank=1,
                druggability_score=0.0,
                volume_angstrom_cubed=0.0,
                centroid=[round(c, 3) for c in centroid],
                pocket_residues=[],
                bounding_box=bbox
            )
            fpocket_results.append(fallback_pocket)

        result = PocketDetectionResult(
            receptor_hash=receptor_hash,
            fpocket_results=fpocket_results,
            cocrystal_pockets=cocrystal_pockets,
            detected_at=datetime.utcnow().isoformat()
        )
        
        # Save cache
        cache_path = self.pockets_dir / receptor_hash / "pockets.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write(result.model_dump_json(indent=2))
            
        return result
