import pytest
import os
import sys
import json
import sqlite3
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root and python folders to sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "python"))

from edeon_engine.__main__ import handle_request
from edeon_knowledge.qa.claude_service import ClaudeQAService

def setup_db(db_path):
    """Initializes the database schema for the integration test."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_conversations (
            conversation_id TEXT PRIMARY KEY,
            user_id TEXT,
            title TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            starred INTEGER DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_messages (
            message_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES knowledge_conversations(conversation_id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            citations_json TEXT,
            retrieved_sources_json TEXT,
            tokens_used_json TEXT,
            timestamp TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

def test_knowledge_qa_e2e_json_rpc():
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp()
    setup_db(db_path)

    try:
        # 1. Test Encryption/Decryption RPC Handlers
        plain_key = "sk-ant-mytestkey"
        encrypt_req = {
            "id": 1,
            "method": "encrypt_api_key",
            "params": {"value": plain_key}
        }
        encrypt_resp = handle_request(encrypt_req)
        assert "error" not in encrypt_resp, f"Encryption failed: {encrypt_resp.get('error')}"
        encrypted_val = encrypt_resp["result"]
        assert encrypted_val != plain_key

        decrypt_req = {
            "id": 2,
            "method": "decrypt_api_key",
            "params": {"value": encrypted_val}
        }
        decrypt_resp = handle_request(decrypt_req)
        assert "error" not in decrypt_resp, f"Decryption failed: {decrypt_resp.get('error')}"
        assert decrypt_resp["result"] == plain_key

        # 2. Test Reindex RPC Handler
        # Create mock project files inside a temporary folder
        with tempfile.TemporaryDirectory() as temp_root:
            with patch('edeon_knowledge.embedding.store.KnowledgeEmbeddingStore.find_project_root') as mock_find_root, \
                 patch('sentence_transformers.SentenceTransformer') as mock_transformer_class:
                
                # Mock find root to point to temp_root
                mock_find_root.return_value = Path(temp_root)
                
                # Mock sentence-transformers to avoid downloading models
                mock_model = MagicMock()
                mock_model.encode.return_value = np.ones(384, dtype=np.float32) / np.sqrt(384)
                mock_transformer_class.return_value = mock_model

                # Create files to index
                mc_dir = Path(temp_root) / "docs" / "TIER1_MODEL_CARDS"
                mc_dir.mkdir(parents=True)
                (mc_dir / "imidacloprid_toxicity.md").write_text("Imidacloprid neonicotinoid info", encoding="utf-8")

                features_txt = Path(temp_root) / "EDEON_COMPLETE_FEATURE_LIST.txt"
                features_txt.write_text(
                    "---------------------------------------------------\n"
                    "This is the first feature description section which is longer than thirty characters.\n",
                    encoding="utf-8"
                )

                reindex_req = {
                    "id": 3,
                    "method": "knowledge_qa_reindex",
                    "params": {
                        "db_path": db_path,
                        "force": True
                    }
                }
                reindex_resp = handle_request(reindex_req)
                assert "error" not in reindex_resp, f"Reindexing failed: {reindex_resp.get('error')}"
                assert reindex_resp["result"]["indexed_count"] == 10

        # 3. Test Ask RPC Handler (with mocked Claude response)
        mock_answer_value = {
            "query": "What is Imidacloprid?",
            "answer": "Imidacloprid is toxic [Source-1].",
            "citations": [
                {
                    "label": "[Source-1]",
                    "entity_id": "imidacloprid_toxicity",
                    "entity_type": "model_card",
                    "text": "Imidacloprid neonicotinoid info",
                    "source_url": "docs/TIER1_MODEL_CARDS/imidacloprid_toxicity.md"
                }
            ],
            "retrieved_sources": [],
            "model": "claude-3-5-haiku-20241022",
            "tokens_used": {"input_tokens": 100, "output_tokens": 50, "cost_usd": 0.00028},
            "timestamp": "2026-06-20T12:00:00"
        }

        with patch.object(ClaudeQAService, 'answer', return_value=mock_answer_value):
            ask_req = {
                "id": 4,
                "method": "knowledge_qa_ask",
                "params": {
                    "query": "What is Imidacloprid?",
                    "conversation_id": None,
                    "db_path": db_path,
                    "api_key": "dummy_key",
                    "model": "claude-3-5-haiku-20241022"
                }
            }
            ask_resp = handle_request(ask_req)
            assert "error" not in ask_resp, f"Ask failed: {ask_resp.get('error')}"
            
            result = ask_resp["result"]
            conversation_id = result["conversation_id"]
            assert conversation_id is not None
            assert result["answer"] == "Imidacloprid is toxic [Source-1]."

        # 4. Test List Conversations RPC Handler
        list_req = {
            "id": 5,
            "method": "knowledge_qa_list_conversations",
            "params": {"db_path": db_path}
        }
        list_resp = handle_request(list_req)
        assert "error" not in list_resp
        conversations = list_resp["result"]
        assert len(conversations) == 1
        assert conversations[0]["conversation_id"] == conversation_id
        assert conversations[0]["starred"] == 0

        # 5. Test Star Conversation RPC Handler
        star_req = {
            "id": 6,
            "method": "knowledge_qa_star_conversation",
            "params": {
                "db_path": db_path,
                "conversation_id": conversation_id,
                "starred": True
            }
        }
        star_resp = handle_request(star_req)
        assert "error" not in star_resp
        assert star_resp["result"] is True

        # Re-list conversations to verify star state
        list_resp2 = handle_request(list_req)
        assert list_resp2["result"][0]["starred"] == 1

        # 6. Test Load Conversation RPC Handler
        load_req = {
            "id": 7,
            "method": "knowledge_qa_load_conversation",
            "params": {
                "db_path": db_path,
                "conversation_id": conversation_id
            }
        }
        load_resp = handle_request(load_req)
        assert "error" not in load_resp
        details = load_resp["result"]
        assert details["conversation_id"] == conversation_id
        assert len(details["messages"]) == 2  # User message and Assistant message
        assert details["messages"][0]["role"] == "user"
        assert details["messages"][1]["role"] == "assistant"
        assert details["messages"][1]["citations"][0]["entity_id"] == "imidacloprid_toxicity"

        # 7. Test Delete Conversation RPC Handler
        delete_req = {
            "id": 8,
            "method": "knowledge_qa_delete_conversation",
            "params": {
                "db_path": db_path,
                "conversation_id": conversation_id
            }
        }
        delete_resp = handle_request(delete_req)
        assert "error" not in delete_resp
        assert delete_resp["result"] is True

        # Verify conversation list is now empty
        list_resp3 = handle_request(list_req)
        assert len(list_resp3["result"]) == 0

    finally:
        os.close(db_fd)
        if os.path.exists(db_path):
            os.remove(db_path)

if __name__ == "__main__":
    import numpy as np
    pytest.main([__file__])
