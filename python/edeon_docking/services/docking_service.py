import os
import re
import json
import time
import asyncio
import hashlib
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from rdkit import Chem

from ..schema import (
    DockingJobSpec,
    DockedPose,
    DockingJobResult
)
from ..pose_parser import parse_vina_output_pdbqt
from .receptor_service import ReceptorService
from .ligand_service import LigandService

logger = logging.getLogger("edeon_docking")

class DockingService:
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            self.base_dir = Path(__file__).resolve().parents[3]
            self.cache_dir = self.base_dir / "data" / "docking" / "cache"
        else:
            self.cache_dir = Path(cache_dir)
            self.base_dir = self.cache_dir.parents[2]
            
        self.jobs_dir = self.cache_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        
        self.receptor_service = ReceptorService(self.cache_dir)
        self.ligand_service = LigandService(self.cache_dir)

    def compute_job_id(self, spec: DockingJobSpec) -> str:
        """Compute SHA-256 hash of canonical job spec details (excluding created_at)."""
        hasher = hashlib.sha256()
        hasher.update(spec.receptor_hash.encode("utf-8"))
        hasher.update(spec.ligand_hash.encode("utf-8"))
        hasher.update(f"{spec.box_center[0]:.3f},{spec.box_center[1]:.3f},{spec.box_center[2]:.3f}".encode("utf-8"))
        hasher.update(f"{spec.box_size[0]:.3f},{spec.box_size[1]:.3f},{spec.box_size[2]:.3f}".encode("utf-8"))
        hasher.update(str(spec.exhaustiveness).encode("utf-8"))
        hasher.update(str(spec.num_modes).encode("utf-8"))
        hasher.update(str(spec.seed).encode("utf-8"))
        hasher.update(spec.engine.encode("utf-8"))
        return hasher.hexdigest()

    def get_cached(self, job_id: str) -> Optional[DockingJobResult]:
        """Check cache for docking job results."""
        cache_path = self.jobs_dir / job_id / "result.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    data = json.load(f)
                    return DockingJobResult.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to read cached job result at {cache_path}: {e}")
        return None

    def _convert_pdbqt_to_sdf_block(self, pdbqt_block: str) -> Optional[str]:
        """Convert a PDBQT block string to a standard SDF block using RDKit."""
        try:
            # AutoDock Vina PDBQT files have AD4 atom types in columns 77-78 (like 'A' for aromatic carbon).
            # RDKit's MolFromPDBBlock rejects these non-standard elements.
            # We clean columns 77-78 to standard periodic table element symbols.
            ad_to_element = {
                "A": "C",
                "C": "C",
                "HD": "H",
                "HS": "H",
                "H": "H",
                "OA": "O",
                "O": "O",
                "N": "N",
                "NA": "N",
                "SA": "S",
                "S": "S",
                "P": "P",
                "F": "F",
                "CL": "Cl",
                "Cl": "Cl",
                "BR": "Br",
                "Br": "Br",
                "I": "I"
            }
            
            cleaned_lines = []
            for line in pdbqt_block.splitlines():
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    # Pad line to 78 chars if shorter
                    if len(line) < 78:
                        line = line.ljust(78)
                    ad_type = line[76:78].strip()
                    element = ad_to_element.get(ad_type, ad_type[0] if ad_type else "C")
                    line = line[:76] + element.rjust(2) + line[78:]
                cleaned_lines.append(line)
                
            cleaned_block = "\n".join(cleaned_lines)
            mol = Chem.MolFromPDBBlock(cleaned_block)
            if mol:
                return Chem.MolToMolBlock(mol)
        except Exception as e:
            logger.warning(f"Failed to convert PDBQT pose block to SDF block: {e}")
        return None

    async def run(self, spec: DockingJobSpec, cancel_event: Optional[asyncio.Event] = None) -> DockingJobResult:
        """Run docking job asynchronously."""
        # 1. Compute job_id and check cache
        job_id = self.compute_job_id(spec)
        spec.job_id = job_id
        
        cached = self.get_cached(job_id)
        if cached:
            logger.info(f"Returning cached docking results for job: {job_id}")
            return cached
            
        target_folder = self.jobs_dir / job_id
        target_folder.mkdir(parents=True, exist_ok=True)
        
        cancel_flag_path = target_folder / "cancel.flag"
        if cancel_flag_path.exists():
            cancel_flag_path.unlink() # remove stale cancel flags
            
        # 2. Resolve prepared receptor and ligand files
        prep_rec = self.receptor_service.get_cached(spec.receptor_hash)
        prep_lig = self.ligand_service.get_cached(spec.ligand_hash)
        
        if not prep_rec or not os.path.exists(prep_rec.pdbqt_path):
            raise FileNotFoundError(f"Prepared receptor not found for hash: {spec.receptor_hash}")
        if not prep_lig or not os.path.exists(prep_lig.pdbqt_path):
            raise FileNotFoundError(f"Prepared ligand not found for hash: {spec.ligand_hash}")
            
        # 3. Construct Vina command
        import shutil
        vina_bin = "/home/svakal/miniconda3/envs/docking/bin/vina"
        if not os.path.exists(vina_bin):
            vina_bin = "/home/svakal/.conda/envs/docking/bin/vina"
        if not os.path.exists(vina_bin):
            vina_bin = shutil.which("vina") or "vina"
            
        # Verify the binary is executable or exists
        if not os.path.exists(vina_bin) and not shutil.which(vina_bin):
            raise FileNotFoundError(f"AutoDock Vina binary not found at {vina_bin}")
            
        output_pdbqt = target_folder / "poses_out.pdbqt"
        if output_pdbqt.exists():
            output_pdbqt.unlink()
            
        cmd = [
            vina_bin,
            "--receptor", str(prep_rec.pdbqtqt_path if hasattr(prep_rec, 'pdbqtqt_path') else prep_rec.pdbqt_path),
            "--ligand", str(prep_lig.pdbqt_path),
            "--center_x", f"{spec.box_center[0]:.3f}",
            "--center_y", f"{spec.box_center[1]:.3f}",
            "--center_z", f"{spec.box_center[2]:.3f}",
            "--size_x", f"{spec.box_size[0]:.3f}",
            "--size_y", f"{spec.box_size[1]:.3f}",
            "--size_z", f"{spec.box_size[2]:.3f}",
            "--exhaustiveness", str(spec.exhaustiveness),
            "--num_modes", str(spec.num_modes),
            "--seed", str(spec.seed),
            "--out", str(output_pdbqt),
        ]
        
        logger.info(f"Running Vina docking command: {' '.join(cmd)}")
        
        start_time = time.time()
        
        # 4. Spawn subprocess and monitor progress / cancellation
        # We run it via asyncio to monitor progress and support cancel flags concurrently
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        
        total_asterisks = 0
        is_cancelled = False
        
        # Read stdout line by line asynchronously
        while True:
            # Check for cancellation
            if (cancel_event and cancel_event.is_set()) or cancel_flag_path.exists():
                is_cancelled = True
                logger.info(f"Cancellation request received for job: {job_id}. Terminating Vina...")
                try:
                    proc.terminate()
                    await asyncio.sleep(0.5)
                    proc.kill()
                except Exception as e:
                    logger.warning(f"Error terminating Vina process: {e}")
                break
                
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
                
            line = line_bytes.decode("utf-8", errors="ignore").strip()
            
            # Count asterisks in Vina's progress bar (there are 50 asterisks in total for 100%)
            # Each asterisk represents 2% progress
            if "*" in line:
                asterisks = line.count("*")
                total_asterisks += asterisks
                percent = min(total_asterisks * 2, 100)
                # Print special token to stdout so Rust can intercept and emit progress event
                print(f"[DOCKING_PROGRESS] {{\"job_id\": \"{job_id}\", \"percent\": {percent}}}", flush=True)
                
        # Wait for process exit code
        return_code = await proc.wait()
        
        # Cleanup cancel flag
        if cancel_flag_path.exists():
            cancel_flag_path.unlink()
            
        if is_cancelled:
            raise RuntimeError("Docking job was cancelled by user")
            
        if return_code != 0:
            raise RuntimeError(f"AutoDock Vina failed with exit code {return_code}")
            
        elapsed = time.time() - start_time
        
        # 5. Parse poses
        if not output_pdbqt.exists():
            raise FileNotFoundError("AutoDock Vina completed but poses output file was not created")
            
        poses = parse_vina_output_pdbqt(output_pdbqt)
        if not poses:
            raise RuntimeError("AutoDock Vina output did not contain any parseable poses")
            
        # Update each pose to include its SDF block representation
        for pose in poses:
            # Generate SDF block from PDBQT block for frontend NGL usage
            pose.sdf_block = self._convert_pdbqt_to_sdf_block(pose.pdbqt_block)
            
        # 6. Save job results to cache
        job_result = DockingJobResult(
            job_id=job_id,
            spec=spec,
            poses=poses,
            elapsed_seconds=round(elapsed, 2),
            engine_version="AutoDock Vina 1.2.5",
            command_line=" ".join(cmd),
            warnings=[],
            completed_at=datetime.utcnow().isoformat()
        )
        
        result_path = target_folder / "result.json"
        with open(result_path, "w") as f:
            f.write(job_result.model_dump_json(indent=2))
            
        return job_result
