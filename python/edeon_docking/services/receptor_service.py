import os
import json
import hashlib
import urllib.request
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from Bio.PDB import PDBParser, PDBIO, Select

from ..schema import (
    PreparedReceptor, 
    ReceptorPreparationParams, 
    HetEntry
)
from ..prep.het_parser import parse_het_atoms, load_cofactor_whitelist, ALL_ION_RESNAMES, COFACTOR_ION_WHITELIST

logger = logging.getLogger("edeon_docking")

PRESET_PDB_MAP = {
    "als": "1YBH",
    "epsps": "2AAY",
    "hppd": "1TFZ",
    "gs": "2O2A",
    "accase": "1UYR",
    "ppo": "1SEZ",
    "ps2": "1FEV",
    "sdh": "2FBW",
}

# Select class for Bio.PDB to keep/strip specific residues and chains
class ReceptorSelect(Select):
    def __init__(self, 
                 keep_chains: Optional[List[str]] = None,
                 keep_residues: Optional[List[Tuple[str, int, str]]] = None, # (chain, resnum, resname)
                 strip_resnames: Optional[List[str]] = None):
        self.keep_chains = keep_chains
        self.keep_residues = keep_residues or []
        self.strip_resnames = strip_resnames or []

    def accept_chain(self, chain):
        if self.keep_chains is not None:
            return chain.id in self.keep_chains
        return 1

    def accept_residue(self, residue):
        resname = residue.get_resname().strip()
        chain_id = residue.get_parent().id
        resnum = residue.id[1]
        
        # Check explicit strip names (like water, buffers, etc.)
        if resname in self.strip_resnames:
            return 0
            
        # If it is a HETATM, check if we keep it
        is_hetero = residue.id[0].startswith("H_") or residue.id[0].startswith("W_")
        if is_hetero:
            # Check if this specific residue is marked to keep
            # Match by (chain_id, resnum, resname)
            match = False
            for k_chain, k_resnum, k_resname in self.keep_residues:
                if k_chain == chain_id and k_resnum == resnum and k_resname == resname:
                    match = True
                    break
            
            if not match:
                return 0 # strip hetero atom unless explicitly in keep list
                
        return 1

class ReceptorService:
    def __init__(self, cache_dir: Optional[Path] = None):
        # We place cache inside Edeon/data/docking/cache relative to the project root
        if cache_dir is None:
            self.base_dir = Path(__file__).resolve().parents[3]
            self.cache_dir = self.base_dir / "data" / "docking" / "cache"
        else:
            self.cache_dir = Path(cache_dir)
            self.base_dir = self.cache_dir.parents[2]
            
        self.raw_pdb_dir = self.cache_dir / "raw_pdbs"
        self.prepared_dir = self.cache_dir / "receptors"
        
        self.raw_pdb_dir.mkdir(parents=True, exist_ok=True)
        self.prepared_dir.mkdir(parents=True, exist_ok=True)

    def _get_preset_path(self, preset_id: str) -> Tuple[Optional[Path], Optional[Path]]:
        """Return preset paths (PDB, PDBQT) if they exist in pre-bundled locations."""
        preset_dir = self.base_dir / "data" / "docking" / "prepared_receptors" / preset_id.lower()
        pdb_path = preset_dir / f"{preset_id.lower()}.pdb"
        pdbqt_path = preset_dir / f"{preset_id.lower()}.pdbqt"
        if pdb_path.exists() and pdbqt_path.exists():
            return pdb_path, pdbqt_path
        return None, None

    async def load_from_source(self, source_type: str, identifier: str) -> Tuple[Path, str]:
        """
        Load raw PDB from source. 
        Returns (local_pdb_path, source_url_or_path).
        """
        source_type = source_type.lower()
        
        if source_type == "preset":
            # Check if pre-prepared preset exists
            pdb_path, _ = self._get_preset_path(identifier)
            if pdb_path:
                return pdb_path, f"preset:{identifier}"
            
            # If not pre-prepared, resolve using its PDB code
            pdb_code = PRESET_PDB_MAP.get(identifier.lower())
            if not pdb_code:
                raise ValueError(f"Unknown preset identifier: {identifier}")
            return await self.load_from_source("pdb_code", pdb_code)
            
        elif source_type == "pdb_code":
            pdb_code = identifier.upper().strip()
            if len(pdb_code) != 4:
                raise ValueError(f"Invalid PDB code: {pdb_code}")
                
            local_path = self.raw_pdb_dir / f"{pdb_code}.pdb"
            if local_path.exists():
                return local_path, f"https://files.rcsb.org/download/{pdb_code}.pdb"
                
            url = f"https://files.rcsb.org/download/{pdb_code}.pdb"
            logger.info(f"Downloading PDB {pdb_code} from RCSB...")
            try:
                urllib.request.urlretrieve(url, str(local_path))
                return local_path, url
            except Exception as e:
                # Try CIF fallback if PDB fails
                cif_path = self.raw_pdb_dir / f"{pdb_code}.cif"
                cif_url = f"https://files.rcsb.org/download/{pdb_code}.cif"
                try:
                    urllib.request.urlretrieve(cif_url, str(cif_path))
                    return cif_path, cif_url
                except Exception:
                    raise RuntimeError(f"Failed to fetch PDB/CIF for {pdb_code} from RCSB: {e}")
                    
        elif source_type == "alphafold":
            uniprot = identifier.upper().strip()
            local_path = self.raw_pdb_dir / f"AF-{uniprot}.pdb"
            if local_path.exists():
                return local_path, f"https://alphafold.ebi.ac.uk/files/AF-{uniprot}-F1-model_v4.pdb"
                
            url = f"https://alphafold.ebi.ac.uk/files/AF-{uniprot}-F1-model_v4.pdb"
            logger.info(f"Downloading AlphaFold structure for {uniprot}...")
            try:
                urllib.request.urlretrieve(url, str(local_path))
                return local_path, url
            except Exception as e:
                raise RuntimeError(f"Failed to fetch AlphaFold structure for {uniprot}: {e}")
                
        elif source_type == "upload":
            upload_path = Path(identifier)
            if not upload_path.exists():
                raise FileNotFoundError(f"Uploaded file not found: {identifier}")
            return upload_path, str(upload_path.resolve())
            
        else:
            raise ValueError(f"Unsupported receptor source type: {source_type}")

    def compute_hash(self, raw_pdb_path: Path, params: ReceptorPreparationParams) -> str:
        """Calculate SHA-256 hash representing PDB content + prep params."""
        hasher = hashlib.sha256()
        with open(raw_pdb_path, "rb") as f:
            hasher.update(f.read())
            
        # Canonicalize params to JSON with sorted keys
        params_json = params.model_dump_json()
        hasher.update(params_json.encode("utf-8"))
        
        return hasher.hexdigest()

    def get_cached(self, receptor_hash: str) -> Optional[PreparedReceptor]:
        """Check cache for prepared receptor metadata."""
        meta_path = self.prepared_dir / receptor_hash / "metadata.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r") as f:
                    data = json.load(f)
                    return PreparedReceptor.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to read cached metadata at {meta_path}: {e}")
        return None

    async def prepare(self, 
                      raw_pdb_path: Path, 
                      params: ReceptorPreparationParams, 
                      source_url: str) -> PreparedReceptor:
        """Execute full receptor preparation pipeline."""
        raw_pdb_path = Path(raw_pdb_path)
        receptor_hash = self.compute_hash(raw_pdb_path, params)
        
        # Check cache first
        cached = self.get_cached(receptor_hash)
        if cached and Path(cached.pdbqt_path).exists():
            logger.info(f"Returning cached prepared receptor for hash: {receptor_hash}")
            return cached
            
        # Invalidate/cleanup old cache if metadata exists but PDBQT is missing
        target_folder = self.prepared_dir / receptor_hash
        target_folder.mkdir(parents=True, exist_ok=True)
        
        # 1. Parse HET entries to decide keep/strip actions
        het_entries = parse_het_atoms(raw_pdb_path)
        
        # Determine residues to keep based on prep params and custom actions
        keep_residues = []
        strip_resnames = []
        
        for entry in het_entries:
            resname = entry.residue_name
            # Resolve user/custom override actions if present
            action = params.custom_het_actions.get(resname)
            if not action:
                if entry.type_classification == "water":
                    action = "keep" if params.keep_water else "strip"
                elif entry.type_classification == "ion":
                    action = "keep" if params.keep_ions or (resname in COFACTOR_ION_WHITELIST) else "strip"
                elif entry.type_classification == "cofactor":
                    action = "keep" if params.keep_cofactors else "strip"
                elif entry.type_classification == "cocrystal_ligand":
                    action = "keep" if params.keep_cocrystal_ligands else "strip"
                else:
                    action = "strip"
            
            if action == "keep":
                keep_residues.append((entry.chain_id, entry.residue_number, entry.residue_name))
            else:
                strip_resnames.append(entry.residue_name)

        # 2. Duplicate chains stripping (keep first chain by default)
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("receptor", str(raw_pdb_path))
        
        model = structure[0]
        chains = list(model.get_chains())
        keep_chains = None
        
        # If there are multiple chains, we by default keep only the first chain
        # (This is configurable, but keeping first chain is standard to prepare monomers)
        if len(chains) > 1:
            keep_chains = [chains[0].id]
            logger.info(f"Stripping duplicate chains. Keeping chain: {chains[0].id}")

        # Write clean PDB using Biopython PDBIO
        cleaned_pdb_path = target_folder / "cleaned.pdb"
        pdb_selector = ReceptorSelect(
            keep_chains=keep_chains,
            keep_residues=keep_residues,
            strip_resnames=strip_resnames
        )
        
        io = PDBIO()
        io.set_structure(structure)
        io.save(str(cleaned_pdb_path), select=pdb_selector)

        # 3. Add hydrogens and convert to PDBQT via Meeko's mk_prepare_receptor.py
        prepared_pdbqt_path = target_folder / "prepared.pdbqt"
        
        # Locate Meeko script in poe environment
        # Standard: /home/svakal/miniconda3/envs/poe/bin/mk_prepare_receptor.py
        meeko_script = "/home/svakal/miniconda3/envs/poe/bin/mk_prepare_receptor.py"
        python_bin = "/home/svakal/miniconda3/envs/poe/bin/python3"
        
        cmd = [
            python_bin,
            meeko_script,
            "--read_pdb", str(cleaned_pdb_path),
            "-o", str(target_folder / "prepared"),
            "-p",
            "-a",
            "--default_altloc", "A",
        ]
        
        # Add flexibility/hydrogen arguments based on options
        if not params.add_hydrogens:
            # Meeko receptor script does not have a "no hydrogens" flag since Vina requires PDBQT with polar Hs,
            # but we can configure it if necessary. By default, it adds hydrogens.
            pass
            
        logger.info(f"Running receptor preparation command: {' '.join(cmd)}")
        
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600
        )
        
        if proc.returncode != 0:
            raise RuntimeError(f"Meeko receptor preparation failed: {proc.stderr}")
            
        # 4. Extract Cocrystal Ligands Metadata (Centroid and Bounding Box)
        # Parse from raw het_entries and structure to keep track of where ligands were
        cocrystal_ligands = []
        for entry in het_entries:
            if entry.type_classification == "cocrystal_ligand":
                # Find residue coords in raw structure
                coords = []
                for res in structure.get_residues():
                    resname = res.get_resname().strip()
                    chain_id = res.get_parent().id
                    resnum = res.id[1]
                    if resname == entry.residue_name and chain_id == entry.chain_id and resnum == entry.residue_number:
                        for atom in res.get_atoms():
                            coords.append(atom.coord.tolist())
                            
                if coords:
                    xs = [c[0] for c in coords]
                    ys = [c[1] for c in coords]
                    zs = [c[2] for c in coords]
                    
                    centroid = [
                        sum(xs) / len(coords),
                        sum(ys) / len(coords),
                        sum(zs) / len(coords)
                    ]
                    
                    cocrystal_ligands.append({
                        "residue_name": entry.residue_name,
                        "chain_id": entry.chain_id,
                        "residue_number": entry.residue_number,
                        "centroid_xyz": [round(c, 3) for c in centroid],
                        "atom_count": len(coords)
                    })

        # Fallback for presets if no cocrystal ligands were detected (as they are pre-stripped)
        if not cocrystal_ligands and source_url.startswith("preset:"):
            preset_id = source_url.split(":")[1].lower()
            preset_coords = {
                "als": [54.126, 55.242, 46.549],
                "accase": [29.12, 42.644, 41.983],
                "epsps": [55.978, 11.213, 28.4],
                "gs": [0.0, 0.0, 0.0],
                "hppd": [43.962, 38.3, 53.083],
                "ppo": [-40.166, -6.351, 28.903],
                "ps2": [0.0, 0.0, 0.0],
                "sdh": [23.827, 51.214, 35.3],
            }
            if preset_id in preset_coords:
                cocrystal_ligands.append({
                    "residue_name": "LIG",
                    "chain_id": "A",
                    "residue_number": 999,
                    "centroid_xyz": preset_coords[preset_id],
                    "atom_count": 20
                })

        parser_cleaned = PDBParser(QUIET=True)
        struct_cleaned = parser_cleaned.get_structure("cleaned", str(cleaned_pdb_path))

        # Calculate final prepared metadata
        num_atoms = 0
        num_residues = 0
        cleaned_chains = set()
        
        for r in struct_cleaned.get_residues():
            num_residues += 1
            cleaned_chains.add(r.get_parent().id)
            num_atoms += len(list(r.get_atoms()))

        metadata = {
            "chain_count": len(cleaned_chains),
            "residue_count": num_residues,
            "atom_count": num_atoms,
            "charge_sum": 0.0, # Meeko assigns charge but doesn't output total charge sum easily; default 0
        }

        # Build return model
        prepared_receptor = PreparedReceptor(
            receptor_hash=receptor_hash,
            pdb_source=source_url,
            pdbqt_path=str(prepared_pdbqt_path.resolve()),
            raw_pdb_path=str(raw_pdb_path.resolve()),
            preparation_params=params,
            metadata=metadata,
            het_entries=het_entries,
            cocrystal_ligands=cocrystal_ligands,
            prepared_at=datetime.utcnow().isoformat()
        )
        
        # Save metadata to cache folder
        meta_path = target_folder / "metadata.json"
        with open(meta_path, "w") as f:
            f.write(prepared_receptor.model_dump_json(indent=2))
            
        return prepared_receptor
