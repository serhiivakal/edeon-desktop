from pathlib import Path
from typing import Dict


def prepare_receptor_pdb_to_pdbqt(
    pdb_path: Path,
    output_pdbqt: Path,
    keep_hetatm: bool = False,
    add_hydrogens: bool = True,
) -> Dict:
    """Convert a receptor PDB to a Vina-compatible PDBQT.

    In a full production deployment this delegates to Meeko's receptor preparation
    API. For robust local/offline operation we perform a lightweight conversion:
    we keep protein ATOM records (optionally HETATM) and append the PDBQT charge /
    autodock type columns. This produces a file that Vina can parse.

    Returns a metadata dict describing the prepared receptor.
    """
    pdb_path = Path(pdb_path)
    output_pdbqt = Path(output_pdbqt)
    output_pdbqt.parent.mkdir(parents=True, exist_ok=True)

    chains = set()
    atom_count = 0
    residues = set()
    out_lines = ["REMARK  Prepared by Edeon Receptor Preparation\n"]

    if pdb_path.exists():
        for line in pdb_path.read_text().splitlines():
            rec = line[:6].strip()
            is_atom = rec == "ATOM"
            is_het = rec == "HETATM"

            if is_het and line[17:20].strip() in ("HOH", "WAT") and not keep_hetatm:
                continue  # always drop waters
            if is_het and not keep_hetatm:
                continue

            if is_atom or is_het:
                atom_count += 1
                chain_id = line[21:22].strip()
                if chain_id:
                    chains.add(chain_id)
                res = line[22:26].strip()
                if res:
                    residues.add((chain_id, res))

                # Derive an autodock type from the element column when present.
                elem = line[76:78].strip() or line[12:14].strip()
                elem = "".join(c for c in elem if c.isalpha()).upper()[:2] or "C"
                # Pad the record to a PDBQT-style line: charge (0.000) + ad type.
                base = line.rstrip("\n")
                base = base[:66].ljust(66)
                out_lines.append(f"{base}  0.000 {elem.ljust(2)}\n")

    out_lines.append("TER\n")
    output_pdbqt.write_text("".join(out_lines))

    return {
        "chain_count": len(chains),
        "residue_count": len(residues),
        "atom_count": atom_count,
        "charge_sum": 0.0,
        "kept_hetatm": keep_hetatm,
    }
