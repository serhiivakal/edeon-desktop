import sys
import os
import asyncio
import shutil
import yaml
from pathlib import Path

# Add python directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "python"))

from edeon_docking.services.receptor_service import ReceptorService, PRESET_PDB_MAP
from edeon_docking.services.pocket_service import PocketService
from edeon_docking.schema import ReceptorPreparationParams

async def main():
    receptor_service = ReceptorService()
    pocket_service = PocketService()
    
    default_boxes = {}
    
    # Target prepared receptors directory
    prepared_receptors_dir = Path(__file__).resolve().parent.parent / "data" / "docking" / "prepared_receptors"
    prepared_receptors_dir.mkdir(parents=True, exist_ok=True)
    
    for preset_name, pdb_code in PRESET_PDB_MAP.items():
        print(f"Preparing preset: {preset_name} ({pdb_code})...")
        try:
            # 1. Download PDB
            raw_path, source_url = await receptor_service.load_from_source("pdb_code", pdb_code)
            
            # 2. Prepare receptor PDBQT
            params = ReceptorPreparationParams()
            prepared = await receptor_service.prepare(raw_path, params, source_url)
            
            # 3. Create folder and copy files to the prepared_receptors/<preset> folder
            preset_out_dir = prepared_receptors_dir / preset_name.lower()
            preset_out_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy prepared PDBQT
            prepared_pdbqt_dest = preset_out_dir / f"{preset_name.lower()}.pdbqt"
            shutil.copy(prepared.pdbqt_path, prepared_pdbqt_dest)
            
            # Copy cleaned PDB
            job_folder = Path(prepared.pdbqt_path).parent
            cleaned_pdb_src = job_folder / "cleaned.pdb"
            cleaned_pdb_dest = preset_out_dir / f"{preset_name.lower()}.pdb"
            if cleaned_pdb_src.exists():
                shutil.copy(cleaned_pdb_src, cleaned_pdb_dest)
            
            print(f"  Saved prepared files to {preset_out_dir}")
            
            # 4. Detect default box coordinates (cocrystal or pocket)
            box_center = [0.0, 0.0, 0.0]
            box_size = [20.0, 20.0, 20.0]
            
            if prepared.cocrystal_ligands:
                # Use centroid of the first cocrystal ligand
                lig = prepared.cocrystal_ligands[0]
                box_center = lig["centroid_xyz"]
                print(f"  Found cocrystal ligand {lig['residue_name']} at {box_center}")
            else:
                # Detect pockets
                detected = await pocket_service.detect(prepared.receptor_hash)
                if detected.fpocket_results:
                    # Use centroid of the top fpocket result
                    pock = detected.fpocket_results[0]
                    box_center = list(pock.centroid)
                    print(f"  No cocrystal ligand. Using fpocket rank-1 pocket at {box_center}")
                elif detected.cocrystal_pockets:
                    pock = detected.cocrystal_pockets[0]
                    box_center = pock["centroid_xyz"]
                    print(f"  Using cocrystal pocket at {box_center}")
                else:
                    print(f"  Warning: No pockets or cocrystal ligands found for {preset_name}. Using [0.0, 0.0, 0.0]")
            
            default_boxes[preset_name.lower()] = {
                "box_center": [round(c, 3) for c in box_center],
                "box_size": box_size
            }
            
        except Exception as e:
            print(f"Error preparing preset {preset_name}: {e}")
            import traceback
            traceback.print_exc()
            
    # Write default boxes to yaml
    yaml_path = Path(__file__).resolve().parent.parent / "data" / "docking" / "preset_default_boxes.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(default_boxes, f, default_flow_style=False)
    print(f"Wrote default box configurations to {yaml_path}")

if __name__ == "__main__":
    asyncio.run(main())
