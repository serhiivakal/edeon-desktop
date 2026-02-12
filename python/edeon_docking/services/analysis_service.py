import os
import re
import json
import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from rdkit import Chem
from rdkit.Chem import AllChem

from ..schema import InteractionFingerprint, DockedPose
from .docking_service import DockingService
from .receptor_service import ReceptorService

logger = logging.getLogger("edeon_docking")

class AnalysisService:
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            self.base_dir = Path(__file__).resolve().parents[3]
            self.cache_dir = self.base_dir / "data" / "docking" / "cache"
        else:
            self.cache_dir = Path(cache_dir)
            self.base_dir = self.cache_dir.parents[2]
            
        self.docking_service = DockingService(self.cache_dir)
        self.receptor_service = ReceptorService(self.cache_dir)

    def _get_atom_res_info(self, atom: Chem.Atom) -> str:
        """Helper to format residue info for an atom, e.g. A:HIS-440."""
        info = atom.GetPDBResidueInfo()
        if info:
            resname = info.GetResidueName().strip()
            chain = info.GetChainId().strip() or "A"
            resnum = info.GetResidueNumber()
            return f"{chain}:{resname}-{resnum}"
        return "A:UNK-0"

    def analyze_interactions(self, 
                             receptor_pdb_path: Path, 
                             pose_sdf_block: str,
                             pose_index: int = 1) -> InteractionFingerprint:
        """
        Compute the interaction fingerprint for a ligand pose against the receptor.
        Uses custom geometry rules in RDKit for high reliability and speed.
        """
        receptor_pdb_path = Path(receptor_pdb_path)
        if not receptor_pdb_path.is_absolute():
            resolved = self.base_dir / receptor_pdb_path
            if resolved.exists():
                receptor_pdb_path = resolved
        if not receptor_pdb_path.exists():
            raise FileNotFoundError(f"Receptor PDB not found: {receptor_pdb_path}")
            
        # 1. Parse molecules
        receptor_mol = Chem.MolFromPDBFile(str(receptor_pdb_path), removeHs=False)
        if not receptor_mol:
            raise ValueError("RDKit failed to parse receptor PDB file")
            
        ligand_mol = Chem.MolFromMolBlock(pose_sdf_block, removeHs=False)
        if not ligand_mol:
            # Try parsing from PDB block as fallback
            ligand_mol = Chem.MolFromPDBBlock(pose_sdf_block, removeHs=False)
            
        if not ligand_mol:
            raise ValueError("RDKit failed to parse ligand pose SDF block")
            
        # Precompute conformers
        rec_conf = receptor_mol.GetConformer()
        lig_conf = ligand_mol.GetConformer()
        
        # Interactions lists
        hbond_donor: List[Dict[str, Any]] = []
        hbond_acceptor: List[Dict[str, Any]] = []
        hydrophobic: List[Dict[str, Any]] = []
        pi_stacking: List[Dict[str, Any]] = []
        pi_cation: List[Dict[str, Any]] = []
        salt_bridge: List[Dict[str, Any]] = []
        halogen_bond: List[Dict[str, Any]] = []
        metal_coordination: List[Dict[str, Any]] = []
        
        # Helper lists of atoms
        # Apolar carbons: carbon with only C or H attached
        def is_apolar_carbon(atom):
            if atom.GetSymbol() != 'C':
                return False
            for n in atom.GetNeighbors():
                if n.GetSymbol() not in ('C', 'H'):
                    return False
            return True
            
        lig_apolar = [a for a in ligand_mol.GetAtoms() if is_apolar_carbon(a)]
        rec_apolar = [a for a in receptor_mol.GetAtoms() if is_apolar_carbon(a)]
        
        # Hydrogen bond donors / acceptors SMARTS
        # Donors: N, O, S with H
        donor_pat = Chem.MolFromSmarts('[$([N,O,S;H1,H2,H3,H4]),$([n;H1])]')
        # Acceptors: N, O, S (excluding positively charged or sulfone oxygens etc. in strict cases, but general is fine)
        acceptor_pat = Chem.MolFromSmarts('[$([O,N,S;H0;!$([O-][N+]=O)]),$([o,n;H0])]')
        
        lig_donors = ligand_mol.GetSubstructMatches(donor_pat) if donor_pat else []
        lig_acceptors = ligand_mol.GetSubstructMatches(acceptor_pat) if acceptor_pat else []
        rec_donors = receptor_mol.GetSubstructMatches(donor_pat) if donor_pat else []
        rec_acceptors = receptor_mol.GetSubstructMatches(acceptor_pat) if acceptor_pat else []
        
        # Positively / Negatively charged centers for Salt Bridges
        pos_pat = Chem.MolFromSmarts('[+,++,$([NX3;H2,H1,H0;!$(NC=O);!$(N-[#6]=*)])]')
        neg_pat = Chem.MolFromSmarts('[-,-,$([CX3](=[OX1])[OX1H0-,OX2H1]),$([SX4](=[OX1])(=[OX1])[OX1H0-,OX2H1]),$([PX4](=[OX1])(=[OX1])[OX1H0-,OX2H1])]')
        
        lig_pos = ligand_mol.GetSubstructMatches(pos_pat) if pos_pat else []
        lig_neg = ligand_mol.GetSubstructMatches(neg_pat) if neg_pat else []
        rec_pos = receptor_mol.GetSubstructMatches(pos_pat) if pos_pat else []
        rec_neg = receptor_mol.GetSubstructMatches(neg_pat) if neg_pat else []
        
        # 2. Compute distances and classify
        
        # --- A. Hydrophobic contacts (< 4.5 Å) ---
        for la in lig_apolar:
            l_pos = lig_conf.GetAtomPosition(la.GetIdx())
            for ra in rec_apolar:
                r_pos = rec_conf.GetAtomPosition(ra.GetIdx())
                dist = l_pos.Distance(r_pos)
                if dist < 4.5:
                    hydrophobic.append({
                        "ligand_atom": f"{la.GetSymbol()}{la.GetIdx()+1}",
                        "ligand_atom_idx": la.GetIdx(),
                        "residue": self._get_atom_res_info(ra),
                        "distance": round(dist, 2)
                    })
                    break # one contact per ligand atom is enough to prevent clutter
                    
        # --- B. Hydrogen bonds (< 3.5 Å) ---
        # Ligand as donor, Receptor as acceptor
        for dm in lig_donors:
            d_idx = dm[0]
            d_atom = ligand_mol.GetAtomWithIdx(d_idx)
            d_pos = lig_conf.GetAtomPosition(d_idx)
            for am in rec_acceptors:
                a_idx = am[0]
                a_atom = receptor_mol.GetAtomWithIdx(a_idx)
                a_pos = rec_conf.GetAtomPosition(a_idx)
                dist = d_pos.Distance(a_pos)
                if dist < 3.5:
                    hbond_donor.append({
                        "ligand_atom": f"{d_atom.GetSymbol()}{d_idx+1}",
                        "ligand_atom_idx": d_idx,
                        "residue": self._get_atom_res_info(a_atom),
                        "distance": round(dist, 2)
                    })
                    
        # Ligand as acceptor, Receptor as donor
        for am in lig_acceptors:
            a_idx = am[0]
            a_atom = ligand_mol.GetAtomWithIdx(a_idx)
            a_pos = lig_conf.GetAtomPosition(a_idx)
            for dm in rec_donors:
                d_idx = dm[0]
                d_atom = receptor_mol.GetAtomWithIdx(d_idx)
                d_pos = rec_conf.GetAtomPosition(d_idx)
                dist = a_pos.Distance(d_pos)
                if dist < 3.5:
                    hbond_acceptor.append({
                        "ligand_atom": f"{a_atom.GetSymbol()}{a_idx+1}",
                        "ligand_atom_idx": a_idx,
                        "residue": self._get_atom_res_info(d_atom),
                        "distance": round(dist, 2)
                    })
                    
        # --- C. Salt bridges (< 4.5 Å) ---
        # Ligand pos, Receptor neg
        for pm in lig_pos:
            p_idx = pm[0]
            p_atom = ligand_mol.GetAtomWithIdx(p_idx)
            p_pos = lig_conf.GetAtomPosition(p_idx)
            for nm in rec_neg:
                n_idx = nm[0]
                n_atom = receptor_mol.GetAtomWithIdx(n_idx)
                n_pos = rec_conf.GetAtomPosition(n_idx)
                dist = p_pos.Distance(n_pos)
                if dist < 4.5:
                    salt_bridge.append({
                        "ligand_atom": f"{p_atom.GetSymbol()}{p_idx+1}",
                        "ligand_atom_idx": p_idx,
                        "residue": self._get_atom_res_info(n_atom),
                        "distance": round(dist, 2)
                    })
                    
        # Ligand neg, Receptor pos
        for nm in lig_neg:
            n_idx = nm[0]
            n_atom = ligand_mol.GetAtomWithIdx(n_idx)
            n_pos = lig_conf.GetAtomPosition(n_idx)
            for pm in rec_pos:
                p_idx = pm[0]
                p_atom = receptor_mol.GetAtomWithIdx(p_idx)
                p_pos = rec_conf.GetAtomPosition(p_idx)
                dist = n_pos.Distance(p_pos)
                if dist < 4.5:
                    salt_bridge.append({
                        "ligand_atom": f"{n_atom.GetSymbol()}{n_idx+1}",
                        "ligand_atom_idx": n_idx,
                        "residue": self._get_atom_res_info(p_atom),
                        "distance": round(dist, 2)
                    })

        # --- D. Pi-Stacking (< 5.5 Å) ---
        # Identify aromatic rings in ligand & receptor
        lig_rings = [list(r) for r in ligand_mol.GetRingInfo().AtomRings() if len(r) in (5, 6)]
        lig_aromatic_rings = []
        for ring in lig_rings:
            if all(ligand_mol.GetAtomWithIdx(idx).GetIsAromatic() for idx in ring):
                lig_aromatic_rings.append(ring)
                
        rec_rings = [list(r) for r in receptor_mol.GetRingInfo().AtomRings() if len(r) in (5, 6)]
        rec_aromatic_rings = []
        for ring in rec_rings:
            if all(receptor_mol.GetAtomWithIdx(idx).GetIsAromatic() for idx in ring):
                rec_aromatic_rings.append(ring)
                
        for l_ring in lig_aromatic_rings:
            l_coords = [np.array(lig_conf.GetAtomPosition(idx)) for idx in l_ring]
            l_centroid = np.mean(l_coords, axis=0)
            
            for r_ring in rec_aromatic_rings:
                r_coords = [np.array(rec_conf.GetAtomPosition(idx)) for idx in r_ring]
                r_centroid = np.mean(r_coords, axis=0)
                
                dist = np.linalg.norm(l_centroid - r_centroid)
                if dist < 5.5:
                    # Get residue info from the first atom in the receptor ring
                    ref_atom = receptor_mol.GetAtomWithIdx(r_ring[0])
                    # Construct description labels
                    lig_label = f"RingCentroid{l_ring[0]+1}"
                    pi_stacking.append({
                        "ligand_atom": lig_label,
                        "ligand_atom_indices": l_ring,
                        "residue": self._get_atom_res_info(ref_atom),
                        "distance": round(dist, 2)
                    })

        return InteractionFingerprint(
            pose_index=pose_index,
            hbond_donor=hbond_donor,
            hbond_acceptor=hbond_acceptor,
            hydrophobic=hydrophobic,
            pi_stacking=pi_stacking,
            pi_cation=pi_cation,
            salt_bridge=salt_bridge,
            halogen_bond=halogen_bond,
            metal_coordination=metal_coordination
        )

    def generate_2d_interaction_map(self, 
                                    receptor_pdb_path: Path, 
                                    pose_sdf_block: str,
                                    pose_index: int = 1) -> str:
        """
        Generate a 2D interaction map SVG.
        Detects interactions, highlights interacting atoms on the 2D ligand,
        and annotates them with interacting residue labels.
        """
        receptor_pdb_path = Path(receptor_pdb_path)
        if not receptor_pdb_path.is_absolute():
            resolved = self.base_dir / receptor_pdb_path
            if resolved.exists():
                receptor_pdb_path = resolved
        if not receptor_pdb_path.exists():
            raise FileNotFoundError(f"Receptor PDB not found: {receptor_pdb_path}")
            
        # 1. Parse molecules
        receptor_mol = Chem.MolFromPDBFile(str(receptor_pdb_path), removeHs=False)
        ligand_mol = Chem.MolFromMolBlock(pose_sdf_block, removeHs=False)
        if not ligand_mol:
            ligand_mol = Chem.MolFromPDBBlock(pose_sdf_block, removeHs=False)
            
        if not ligand_mol or not receptor_mol:
            # Fallback to plain depiction if receptor or pose parsing fails
            if ligand_mol:
                from rdkit.Chem.Draw import rdMolDraw2D
                draw_mol = Chem.RemoveHs(ligand_mol)
                AllChem.Compute2DCoords(draw_mol)
                drawer = rdMolDraw2D.MolDraw2DSVG(450, 350)
                drawer.DrawMolecule(draw_mol)
                drawer.FinishDrawing()
                return drawer.GetDrawingText()
            raise ValueError("Failed to parse ligand pose")
            
        # 2. Get 3D interactions
        fingerprint = self.analyze_interactions(receptor_pdb_path, pose_sdf_block, pose_index)
        
        # 3. Create a 2D copy of ligand for drawing, mapping original index of heavy atoms
        for idx, atom in enumerate(ligand_mol.GetAtoms()):
            atom.SetIntProp("orig_idx", idx)
            
        draw_mol = Chem.RemoveHs(ligand_mol)
        AllChem.Compute2DCoords(draw_mol)
        
        orig_to_draw_atom = {}
        for atom in draw_mol.GetAtoms():
            if atom.HasProp("orig_idx"):
                orig_idx = atom.GetIntProp("orig_idx")
                orig_to_draw_atom[orig_idx] = atom
                
        # 4. Collect annotations and highlight colors for draw_mol atoms
        annotations = {}
        highlight_colors = {}
        
        # Highlight colors
        color_hb = (0.2, 0.8, 0.2)  # Green
        color_hp = (0.9, 0.6, 0.2)  # Amber/Orange
        color_sb = (0.2, 0.6, 0.9)  # Blue
        color_pi = (0.7, 0.3, 0.9)  # Purple
        
        for hb in fingerprint.hbond_donor:
            idx = hb.get("ligand_atom_idx")
            if idx is not None and idx in orig_to_draw_atom:
                draw_atom = orig_to_draw_atom[idx]
                draw_idx = draw_atom.GetIdx()
                res_name = hb["residue"].split(":")[-1]
                annotations.setdefault(draw_idx, []).append(f"hb:{res_name}")
                highlight_colors[draw_idx] = color_hb
                
        for hb in fingerprint.hbond_acceptor:
            idx = hb.get("ligand_atom_idx")
            if idx is not None and idx in orig_to_draw_atom:
                draw_atom = orig_to_draw_atom[idx]
                draw_idx = draw_atom.GetIdx()
                res_name = hb["residue"].split(":")[-1]
                annotations.setdefault(draw_idx, []).append(f"hb:{res_name}")
                highlight_colors[draw_idx] = color_hb
                
        for hp in fingerprint.hydrophobic:
            idx = hp.get("ligand_atom_idx")
            if idx is not None and idx in orig_to_draw_atom:
                draw_atom = orig_to_draw_atom[idx]
                draw_idx = draw_atom.GetIdx()
                res_name = hp["residue"].split(":")[-1]
                annotations.setdefault(draw_idx, []).append(f"hp:{res_name}")
                if draw_idx not in highlight_colors:
                    highlight_colors[draw_idx] = color_hp
                    
        for sb in fingerprint.salt_bridge:
            idx = sb.get("ligand_atom_idx")
            if idx is not None and idx in orig_to_draw_atom:
                draw_atom = orig_to_draw_atom[idx]
                draw_idx = draw_atom.GetIdx()
                res_name = sb["residue"].split(":")[-1]
                annotations.setdefault(draw_idx, []).append(f"sb:{res_name}")
                highlight_colors[draw_idx] = color_sb
                
        for pi in fingerprint.pi_stacking:
            indices = pi.get("ligand_atom_indices", [])
            res_name = pi["residue"].split(":")[-1]
            for idx in indices:
                if idx in orig_to_draw_atom:
                    draw_atom = orig_to_draw_atom[idx]
                    draw_idx = draw_atom.GetIdx()
                    annotations.setdefault(draw_idx, []).append(f"pi:{res_name}")
                    highlight_colors[draw_idx] = color_pi
                    
        # Apply annotations to draw_mol atoms
        for draw_idx, notes in annotations.items():
            atom = draw_mol.GetAtomWithIdx(draw_idx)
            unique_notes = sorted(list(set(notes)))
            atom.SetProp("atomNote", ", ".join(unique_notes))
            
        # 5. Draw
        from rdkit.Chem.Draw import rdMolDraw2D
        drawer = rdMolDraw2D.MolDraw2DSVG(450, 350)
        opts = drawer.drawOptions()
        opts.bondLineWidth = 2.0
        opts.padding = 0.04
        opts.clearBackground = False  # Transparent background
        opts.annotationFontScale = 0.7
        
        drawer.DrawMolecule(
            draw_mol,
            highlightAtoms=list(highlight_colors.keys()),
            highlightAtomColors=highlight_colors
        )
        drawer.FinishDrawing()
        
        svg = drawer.GetDrawingText()
        
        # Strip XML declaration if present
        if svg.startswith('<?xml'):
            svg = svg[svg.index('?>') + 2:].strip()
            
        return svg

    def measure_distance(self, 
                         pose_sdf_block: str, 
                         receptor_pdb_path: Path,
                         atom1_selector: str, 
                         atom2_selector: str) -> float:
        """
        Compute Euclidean distance between two atoms.
        atom1_selector: 'ligand:atom_3' or 'ligand:4'
        atom2_selector: 'A:HIS-440:NE2' (chain:resname-resnum:atomname)
        """
        receptor_pdb_path = Path(receptor_pdb_path)
        if not receptor_pdb_path.is_absolute():
            resolved = self.base_dir / receptor_pdb_path
            if resolved.exists():
                receptor_pdb_path = resolved
        
        # 1. Parse selectors and resolve coords
        
        # Helper to parse selector coord
        def get_selector_coord(sel: str, lig_mol: Chem.Mol, rec_mol: Chem.Mol) -> Tuple[float, float, float]:
            sel = sel.strip()
            
            # Ligand selector match: ligand:atom_<idx> or ligand:<idx>
            lig_match = re.match(r"^ligand:(?:atom_)?(\d+)$", sel, re.IGNORECASE)
            if lig_match:
                atom_idx = int(lig_match.group(1))
                # SDF/PDB QT atom index might be 1-based or 0-based.
                # In Edeon, selector idx is 1-based matching viewer displays.
                rdkit_idx = atom_idx - 1
                if 0 <= rdkit_idx < lig_mol.GetNumAtoms():
                    pos = lig_mol.GetConformer().GetAtomPosition(rdkit_idx)
                    return (pos.x, pos.y, pos.z)
                raise IndexError(f"Ligand atom index {atom_idx} out of bounds")
                
            # Receptor selector match: chain:resname-resnum:atomname e.g. A:HIS-440:NE2
            rec_match = re.match(r"^([a-zA-Z0-9]):([a-zA-Z0-9]+)-(\d+):([a-zA-Z0-9]+)$", sel)
            if rec_match:
                chain_id = rec_match.group(1).upper()
                resname = rec_match.group(2).upper()
                resnum = int(rec_match.group(3))
                atom_name = rec_match.group(4).upper()
                
                for atom in rec_mol.GetAtoms():
                    info = atom.GetPDBResidueInfo()
                    if info:
                        a_chain = info.GetChainId().strip().upper()
                        a_resname = info.GetResidueName().strip().upper()
                        a_resnum = info.GetResidueNumber()
                        a_name = info.GetName().strip().upper()
                        
                        if a_chain == chain_id and a_resname == resname and a_resnum == resnum and a_name == atom_name:
                            pos = rec_mol.GetConformer().GetAtomPosition(atom.GetIdx())
                            return (pos.x, pos.y, pos.z)
                            
                raise ValueError(f"Receptor atom not found matching selector: {sel}")
                
            raise ValueError(f"Invalid atom selector format: {sel}")

        # Parse molecules
        lig_mol = Chem.MolFromMolBlock(pose_sdf_block, removeHs=False)
        if not lig_mol:
            lig_mol = Chem.MolFromPDBBlock(pose_sdf_block, removeHs=False)
        if not lig_mol:
            raise ValueError("Failed to parse ligand pose")
            
        rec_mol = Chem.MolFromPDBFile(str(receptor_pdb_path), removeHs=False)
        if not rec_mol:
            raise ValueError("Failed to parse receptor PDB")

        c1 = get_selector_coord(atom1_selector, lig_mol, rec_mol)
        c2 = get_selector_coord(atom2_selector, lig_mol, rec_mol)
        
        # Compute distance
        dx = c1[0] - c2[0]
        dy = c1[1] - c2[1]
        dz = c1[2] - c2[2]
        
        return round(float(np.sqrt(dx*dx + dy*dy + dz*dz)), 3)

    def cluster_poses_by_rmsd(self, 
                              poses: List[DockedPose], 
                              rmsd_cutoff: float = 2.0) -> List[List[int]]:
        """
        Cluster docked poses by heavy-atom RMSD.
        Returns a list of clusters. Each cluster is a list of 1-based pose indices.
        """
        if not poses:
            return []
            
        mols = []
        for p in poses:
            mol = Chem.MolFromMolBlock(p.sdf_block or p.pdbqt_block, removeHs=False)
            if not mol:
                mol = Chem.MolFromPDBBlock(p.pdbqt_block, removeHs=False)
            if mol:
                mols.append(mol)
                
        if len(mols) < 2:
            return [[p.pose_index] for p in poses]
            
        # Greedy clustering algorithm:
        # Poses are processed in order (pre-sorted by score).
        # We check each pose against the seeds of existing clusters.
        # If it is within the rmsd_cutoff of an existing seed, it joins that cluster.
        # Otherwise, it starts a new cluster.
        clusters = []  # List of lists of 1-based pose indices
        seed_mols = []  # List of heavy-atom Chem.Mol representing the seed of each cluster
        
        for idx, p in enumerate(poses):
            if idx >= len(mols):
                continue
            mol = mols[idx]
            try:
                mol_heavy = Chem.RemoveHs(mol)
                c_current = mol_heavy.GetConformer().GetPositions()
            except Exception:
                try:
                    c_current = mol.GetConformer().GetPositions()
                    mol_heavy = mol
                except Exception:
                    # If coordinates cannot be extracted, start a new cluster
                    clusters.append([p.pose_index])
                    continue
                    
            assigned = False
            for c_idx, seed_heavy in enumerate(seed_mols):
                try:
                    c_seed = seed_heavy.GetConformer().GetPositions()
                    if len(c_current) == len(c_seed):
                        diff = c_current - c_seed
                        rmsd = np.sqrt(np.mean(np.sum(diff**2, axis=1)))
                        if rmsd <= rmsd_cutoff:
                            clusters[c_idx].append(p.pose_index)
                            assigned = True
                            break
                except Exception:
                    pass
                    
            if not assigned:
                clusters.append([p.pose_index])
                seed_mols.append(mol_heavy)
                
        return clusters
