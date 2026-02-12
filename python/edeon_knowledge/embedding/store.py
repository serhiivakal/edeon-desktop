import os
import sqlite3
import hashlib
import json
import yaml
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional

@dataclass
class KnowledgeMatch:
    entity_id: str
    entity_type: str
    text: str
    similarity: float
    source_url: Optional[str] = None
    citation: Optional[str] = None

class KnowledgeEmbeddingStore:
    """Embeds Knowledge Hub entries and stores vectors in SQLite for offline cosine similarity search."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2",
                 store_path: Optional[Path] = None):
        if store_path is None:
            # Place in user application data dir or default project data dir
            default_dir = Path(os.path.expanduser("~/.local/share/com.edeon.desktop"))
            default_dir.mkdir(parents=True, exist_ok=True)
            self._store_path = default_dir / "embeddings.db"
        else:
            self._store_path = Path(store_path)
            self._store_path.parent.mkdir(parents=True, exist_ok=True)

        self.model_name = model_name
        self._model = None # Lazy-loaded on demand
        self._init_store()

    def _get_model(self):
        """Lazy load the sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            # Trust remote code is required for certain models like nomic-embed-text
            self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
        return self._model

    def _init_store(self):
        """Initialize standard SQLite database connection and tables."""
        conn = sqlite3.connect(self._store_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_type ON embeddings(entity_type);")
            conn.commit()
        finally:
            conn.close()

    def find_project_root(self) -> Path:
        """Helper to dynamically trace the project root folder."""
        current = Path(__file__).resolve().parent
        for _ in range(5):
            if (current / "EDEON_COMPLETE_FEATURE_LIST.txt").exists():
                return current
            current = current.parent
        # Fallback
        return Path(__file__).resolve().parent.parent.parent.parent

    def index_knowledge_hub(self, force: bool = False) -> int:
        """
        Walks local markdown files, yaml manifests, local databases, and complete features list.
        Chops text into chunks, computes vectors incrementally, and updates embeddings.db.
        """
        project_root = self.find_project_root()
        print(f"Indexing Knowledge Hub starting at project root: {project_root}")

        chunks: List[Dict[str, Any]] = []

        # 1. Index Model Cards from docs/TIER1_MODEL_CARDS/
        model_cards_dir = project_root / "docs" / "TIER1_MODEL_CARDS"
        if model_cards_dir.exists():
            for filepath in model_cards_dir.glob("*.md"):
                try:
                    content = filepath.read_text(encoding="utf-8")
                    filename_stem = filepath.stem
                    chunks.append({
                        "id": f"model_card_{filename_stem}",
                        "entity_type": "model_card",
                        "entity_id": filename_stem,
                        "text": f"Model Card: {filename_stem}\n\n{content}",
                    })
                except Exception as e:
                    print(f"Warning: Failed reading model card {filepath.name}: {e}")

        # 2. Index local agchem database from python/edeon_engine/knowledge.py
        try:
            # Adjust sys.path to import local modules dynamically
            import sys
            sys.path.insert(0, str(project_root / "python"))
            from edeon_engine.knowledge import AGCHEM_DATABASE
            for item in AGCHEM_DATABASE:
                cid = item["id"]
                name = item["name"]
                
                # Format a rich text block representing the chemical profile
                text_lines = [
                    f"Pesticide: {name} (CAS: {item.get('cas_number', 'N/A')})",
                    f"Chemical Formula: {item.get('formula', 'N/A')} | Class: {item.get('class', 'N/A')}",
                    f"Mode of Action: {item.get('moa', 'N/A')}"
                ]
                
                reg = item.get("regulatory_status", {})
                if reg:
                    reg_text = f"Regulatory Status: EU: {reg.get('eu_status', 'N/A')}, EPA: {reg.get('us_epa', 'N/A')}, MRL EU: {reg.get('mrl_eu', '—')}, Hazard Class: {reg.get('hazard_classification', '—')}"
                    text_lines.append(reg_text)
                    
                ecotox = item.get("ecotox_endpoints", {})
                if ecotox:
                    ecotox_text = f"Ecotox safety profile: Honeybee: {ecotox.get('honeybee_ld50', '—')}, Fish: {ecotox.get('fish_lc50', '—')}, Bird: {ecotox.get('bird_ld50', '—')}, Mammal: {ecotox.get('mammal_ld50', '—')}, Daphnia: {ecotox.get('daphnia_ec50', '—')}"
                    text_lines.append(ecotox_text)
                    
                res = item.get("resistance_factors", {})
                if res:
                    res_text = f"Resistance details: Risk: {res.get('risk', '—')}, Group: {res.get('hrac_irac', '—')}, Known Mutations: {res.get('known_mutations', '—')}"
                    text_lines.append(res_text)

                chunks.append({
                    "id": f"pesticide_local_{cid}",
                    "entity_type": "pesticide",
                    "entity_id": cid,
                    "text": "\n".join(text_lines),
                })
        except Exception as e:
            print(f"Warning: Failed importing local AGCHEM_DATABASE: {e}")

        # 3. Index reference compounds from data/demos/reference_compounds.yaml
        ref_comp_yaml = project_root / "data" / "demos" / "reference_compounds.yaml"
        if ref_comp_yaml.exists():
            try:
                with open(ref_comp_yaml, 'r', encoding='utf-8') as f:
                    manifest = yaml.safe_load(f)
                comp_list = manifest.get("reference_compounds", [])
                for comp in comp_list:
                    comp_id = comp.get("id")
                    name = comp.get("name")
                    text_lines = [
                        f"Reference Active Ingredient: {name} ({comp_id})",
                        f"CAS: {comp.get('cas', 'N/A')} | ChEMBL: {comp.get('chembl_id', 'N/A')}",
                        f"Canonical SMILES: {comp.get('smiles_canonical', 'N/A')}",
                        f"Class Subtype: {comp.get('class_subtype', 'N/A')} ({comp.get('class', 'N/A')})"
                    ]
                    
                    irac = comp.get("irac_group")
                    hrac = comp.get("hrac_group")
                    frac = comp.get("frac_group")
                    if irac: text_lines.append(f"IRAC Group: {irac}")
                    if hrac: text_lines.append(f"HRAC Group: {hrac}")
                    if frac: text_lines.append(f"FRAC Group: {frac}")

                    measured = comp.get("measured_values", {})
                    if measured:
                        meas_str = ", ".join(f"{k}: {v.get('value')} {v.get('units')}" for k, v in measured.items())
                        text_lines.append(f"Measured experimental values: {meas_str}")

                    chunks.append({
                        "id": f"reference_compound_{comp_id}",
                        "entity_type": "reference",
                        "entity_id": comp_id,
                        "text": "\n".join(text_lines),
                    })
            except Exception as e:
                print(f"Warning: Failed reading reference compounds YAML: {e}")

        # 4. Index system features list: EDEON_COMPLETE_FEATURE_LIST.txt
        feature_list_path = project_root / "EDEON_COMPLETE_FEATURE_LIST.txt"
        if feature_list_path.exists():
            try:
                content = feature_list_path.read_text(encoding="utf-8")
                # Split content into sections demarcated by double dashes or titles
                # We can split by section header "------"
                sections = re_split_sections(content)
                for idx, sec in enumerate(sections):
                    sec_clean = sec.strip()
                    if not sec_clean:
                        continue
                    
                    # Extract the first line as a title to identify the entity
                    first_line = sec_clean.split("\n")[0].strip("- ")
                    chunks.append({
                        "id": f"system_feature_section_{idx}",
                        "entity_type": "framework",
                        "entity_id": f"section_{idx}",
                        "text": f"Edeon Engine Specification & Formula:\n\n{sec_clean}",
                    })
            except Exception as e:
                print(f"Warning: Failed indexing EDEON_COMPLETE_FEATURE_LIST.txt: {e}")

        # Sync chunks to SQLite database with incremental logic
        conn = sqlite3.connect(self._store_path)
        indexed_count = 0
        try:
            cursor = conn.cursor()
            
            # If force-reindexing, clear the table
            if force:
                cursor.execute("DELETE FROM embeddings")
                conn.commit()

            # Retrieve currently indexed record hashes
            cursor.execute("SELECT id, hash FROM embeddings")
            existing_hashes = {row[0]: row[1] for row in cursor.fetchall()}
            processed_ids = set()

            for chunk in chunks:
                chunk_id = chunk["id"]
                processed_ids.add(chunk_id)
                text = chunk["text"]
                text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
                
                # Check if hash matches
                if chunk_id in existing_hashes and existing_hashes[chunk_id] == text_hash:
                    # Skip embedding generation
                    continue

                # Generate vector
                model = self._get_model()
                embedding = model.encode(text, convert_to_numpy=True)
                embedding_bytes = embedding.astype(np.float32).tobytes()
                
                now_str = datetime.utcnow().isoformat()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO embeddings (
                        id, entity_type, entity_id, text, embedding, hash, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        chunk["entity_type"],
                        chunk["entity_id"],
                        text,
                        sqlite3.Binary(embedding_bytes),
                        text_hash,
                        now_str
                    )
                )
                indexed_count += 1

            # Delete stale entries (removed from codebase)
            stale_ids = set(existing_hashes.keys()) - processed_ids
            if stale_ids:
                cursor.executemany("DELETE FROM embeddings WHERE id = ?", [(sid,) for sid in stale_ids])
                
            conn.commit()
        finally:
            conn.close()

        print(f"Re-indexed {indexed_count} new/updated entries. Cleaned up {len(stale_ids) if stale_ids else 0} stale records.")
        return indexed_count

    def search(self, query: str, top_k: int = 10, 
               entity_types: Optional[List[str]] = None) -> List[KnowledgeMatch]:
        """Runs cosine similarity in Python using numpy against SQLite candidates."""
        # 1. Load active candidates from SQLite
        conn = sqlite3.connect(self._store_path)
        candidates = []
        try:
            cursor = conn.cursor()
            if entity_types:
                placeholders = ",".join("?" for _ in entity_types)
                cursor.execute(
                    f"SELECT id, entity_type, entity_id, text, embedding FROM embeddings WHERE entity_type IN ({placeholders})",
                    entity_types
                )
            else:
                cursor.execute("SELECT id, entity_type, entity_id, text, embedding FROM embeddings")
            
            for row in cursor.fetchall():
                eid, etype, ent_id, text, vec_bytes = row
                vec = np.frombuffer(vec_bytes, dtype=np.float32)
                candidates.append((eid, etype, ent_id, text, vec))
        finally:
            conn.close()

        if not candidates:
            return []

        # 2. Embed the query
        model = self._get_model()
        query_vector = model.encode(query, convert_to_numpy=True).astype(np.float32)

        # 3. Calculate cosine similarities
        matches = []
        for eid, etype, ent_id, text, vec in candidates:
            # Cosine similarity: (A . B) / (||A|| * ||B||)
            dot_product = np.dot(query_vector, vec)
            norm_q = np.linalg.norm(query_vector)
            norm_v = np.linalg.norm(vec)
            
            similarity = float(dot_product / (norm_q * norm_v)) if (norm_q * norm_v) > 0 else 0.0
            
            # Compile a citation label
            citation_label = f"[{etype.replace('_', ' ').title()}: {ent_id}]"

            # Parse a source URL if any
            source_url = None
            if etype == "model_card":
                source_url = f"docs/TIER1_MODEL_CARDS/{ent_id}.md"
            elif etype == "pesticide":
                source_url = "python/edeon_engine/knowledge.py"
            elif etype == "reference":
                source_url = "data/demos/reference_compounds.yaml"
            elif etype == "framework":
                source_url = "EDEON_COMPLETE_FEATURE_LIST.txt"

            matches.append(KnowledgeMatch(
                entity_id=ent_id,
                entity_type=etype,
                text=text,
                similarity=similarity,
                source_url=source_url,
                citation=citation_label
            ))

        # Sort descending by similarity
        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches[:top_k]

def re_split_sections(content: str) -> List[str]:
    """Chop EDEON_COMPLETE_FEATURE_LIST.txt into section blocks."""
    import re
    # Match dividers like "---------------------------------------------------"
    sections = re.split(r"-{20,}", content)
    return [sec for sec in sections if len(sec.strip()) > 30]
