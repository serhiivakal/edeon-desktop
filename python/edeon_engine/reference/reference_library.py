import os
import sqlite3
from rdkit import Chem
from rdkit import DataStructs
from rdkit.Chem import AllChem

def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), "reference_actives.sqlite")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def reference_lookup(by: str, query: str, limit: int = 10) -> list:
    """
    Looks up reference actives by name, moa, use_class, or similarity.
    Returns:
        list of dicts containing active metadata, profile values, and optionally similarity.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    actives = []
    
    if by == "similarity":
        # 1. Parse query smiles
        query_mol = Chem.MolFromSmiles(query)
        if not query_mol:
            conn.close()
            return []
        
        query_fp = AllChem.GetMorganFingerprintAsBitVect(query_mol, 2, nBits=2048)
        
        # 2. Fetch all actives
        cursor.execute("SELECT id, name, cas, smiles, use_class, moa_group, approval_status FROM actives")
        all_rows = cursor.fetchall()
        
        scored_actives = []
        for row in all_rows:
            target_smiles = row["smiles"]
            target_mol = Chem.MolFromSmiles(target_smiles)
            if not target_mol:
                continue
            
            target_fp = AllChem.GetMorganFingerprintAsBitVect(target_mol, 2, nBits=2048)
            sim = DataStructs.TanimotoSimilarity(query_fp, target_fp)
            
            scored_actives.append((sim, row))
            
        # 3. Sort by similarity descending
        scored_actives.sort(key=lambda x: x[0], reverse=True)
        selected_actives = scored_actives[:limit]
        
        # 4. Fetch profiles
        for sim, row in selected_actives:
            active_id = row["id"]
            cursor.execute(
                "SELECT axis, value, unit, source_type, source_ref FROM active_values WHERE active_id = ?",
                (active_id,)
            )
            profile_rows = cursor.fetchall()
            profile = [dict(p) for p in profile_rows]
            
            active_dict = dict(row)
            # Add similarity to the active dict itself or to the top-level
            actives.append({
                "active": active_dict,
                "profile": profile,
                "similarity": round(sim, 4)
            })
            
    else:
        # 1. Standard SQL search
        sql_query = ""
        param = f"%{query}%"
        
        if by == "moa":
            sql_query = "SELECT id, name, cas, smiles, use_class, moa_group, approval_status FROM actives WHERE LOWER(moa_group) LIKE LOWER(?)"
        elif by == "use_class":
            sql_query = "SELECT id, name, cas, smiles, use_class, moa_group, approval_status FROM actives WHERE LOWER(use_class) LIKE LOWER(?)"
        elif by == "name":
            sql_query = "SELECT id, name, cas, smiles, use_class, moa_group, approval_status FROM actives WHERE LOWER(name) LIKE LOWER(?)"
        else:
            # Fallback to search all fields if unknown type
            sql_query = """
                SELECT id, name, cas, smiles, use_class, moa_group, approval_status FROM actives 
                WHERE LOWER(name) LIKE LOWER(?) OR LOWER(moa_group) LIKE LOWER(?) OR LOWER(use_class) LIKE LOWER(?)
            """
            
        if by in ["moa", "use_class", "name"]:
            cursor.execute(sql_query + f" LIMIT {int(limit)}", (param,))
        else:
            cursor.execute(sql_query + f" LIMIT {int(limit)}", (param, param, param))
            
        rows = cursor.fetchall()
        
        # 2. Fetch profiles
        for row in rows:
            active_id = row["id"]
            cursor.execute(
                "SELECT axis, value, unit, source_type, source_ref FROM active_values WHERE active_id = ?",
                (active_id,)
            )
            profile_rows = cursor.fetchall()
            profile = [dict(p) for p in profile_rows]
            
            actives.append({
                "active": dict(row),
                "profile": profile
            })
            
    conn.close()
    return actives
