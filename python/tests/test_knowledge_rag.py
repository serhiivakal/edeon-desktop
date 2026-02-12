import unittest
import tempfile
import os
import sqlite3
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

from edeon_knowledge.embedding.store import KnowledgeEmbeddingStore, KnowledgeMatch
from edeon_knowledge.qa.encryption import encrypt_value, decrypt_value, get_machine_key
from edeon_knowledge.qa.claude_service import ClaudeQAService

class MockModel:
    def __init__(self, model_name, trust_remote_code=True):
        self.model_name = model_name

    def encode(self, sentences, convert_to_numpy=True, **kwargs):
        # Return a simple mock vector (384-dimensional unit vector) for each sentence
        if isinstance(sentences, str):
            return np.ones(384, dtype=np.float32) / np.sqrt(384)
        else:
            return np.ones((len(sentences), 384), dtype=np.float32) / np.sqrt(384)

class TestKnowledgeEncryption(unittest.TestCase):
    def test_stable_machine_key(self):
        key1 = get_machine_key()
        key2 = get_machine_key()
        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 44)  # Fernet base64 key length is 44

    def test_encrypt_decrypt_roundtrip(self):
        plain_text = "sk-ant-api03-my-super-secret-key-123456789"
        cipher = encrypt_value(plain_text)
        self.assertNotEqual(plain_text, cipher)
        
        decrypted = decrypt_value(cipher)
        self.assertEqual(plain_text, decrypted)

    def test_encrypt_decrypt_empty(self):
        self.assertEqual(encrypt_value(""), "")
        self.assertEqual(decrypt_value(""), "")

    def test_decrypt_corrupted_key_raises_error(self):
        with self.assertRaises(ValueError):
            decrypt_value("invalid_cipher_text_that_is_not_fernet_encoded")

class TestKnowledgeEmbeddingStore(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp()
        self.store_path = Path(self.temp_db_path)
        
        # Patch SentenceTransformer to return our mock model
        self.transformer_patcher = patch('sentence_transformers.SentenceTransformer', side_effect=MockModel)
        self.mock_transformer = self.transformer_patcher.start()
        
        self.store = KnowledgeEmbeddingStore(store_path=self.store_path)

    def tearDown(self):
        self.transformer_patcher.stop()
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_init_db(self):
        # Verify tables exist
        conn = sqlite3.connect(self.store_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'")
        self.assertIsNotNone(cursor.fetchone())
        conn.close()

    def test_search_empty_store(self):
        matches = self.store.search("query text")
        self.assertEqual(len(matches), 0)

    def test_insert_and_search(self):
        # Insert raw test record
        conn = sqlite3.connect(self.store_path)
        cursor = conn.cursor()
        
        # Compute a dummy vector and save it as float32 bytes
        dummy_vec = np.ones(384, dtype=np.float32) / np.sqrt(384)
        dummy_bytes = dummy_vec.tobytes()
        
        cursor.execute(
            "INSERT INTO embeddings (id, entity_type, entity_id, text, embedding, hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("model_card_test", "model_card", "test", "Briggs model card details", sqlite3.Binary(dummy_bytes), "hash123", "2026-06-20T12:00:00")
        )
        conn.commit()
        conn.close()

        # Search for it
        matches = self.store.search("Briggs", top_k=5)
        self.assertEqual(len(matches), 1)
        match = matches[0]
        self.assertEqual(match.entity_id, "test")
        self.assertEqual(match.entity_type, "model_card")
        self.assertEqual(match.text, "Briggs model card details")
        self.assertAlmostEqual(match.similarity, 1.0, places=4)
        self.assertEqual(match.source_url, "docs/TIER1_MODEL_CARDS/test.md")
        self.assertEqual(match.citation, "[Model Card: test]")

    @patch.object(KnowledgeEmbeddingStore, 'find_project_root')
    def test_index_knowledge_hub(self, mock_find_root):
        # Create a mock project structure in a temp directory
        with tempfile.TemporaryDirectory() as temp_root:
            mock_find_root.return_value = Path(temp_root)
            
            # 1. Model cards
            mc_dir = Path(temp_root) / "docs" / "TIER1_MODEL_CARDS"
            mc_dir.mkdir(parents=True)
            (mc_dir / "test_model_card.md").write_text("This is test model card content.", encoding="utf-8")
            
            # 2. Reference compounds
            rc_dir = Path(temp_root) / "data" / "demos"
            rc_dir.mkdir(parents=True)
            rc_yaml = rc_dir / "reference_compounds.yaml"
            rc_yaml.write_text(
                "reference_compounds:\n"
                "  - id: ref_001\n"
                "    name: MockPesticide\n"
                "    cas: 9999-99-9\n"
                "    smiles_canonical: CC(=O)O\n"
                "    class: TestClass\n"
                "    irac_group: 1A\n",
                encoding="utf-8"
            )
            
            # 3. Features list
            features_txt = Path(temp_root) / "EDEON_COMPLETE_FEATURE_LIST.txt"
            features_txt.write_text(
                "---------------------------------------------------\n"
                "This is the first feature description section which is longer than thirty characters.\n"
                "---------------------------------------------------\n"
                "This is the second feature description section which is also longer than thirty characters.\n",
                encoding="utf-8"
            )

            # Let's index the mock folder
            indexed = self.store.index_knowledge_hub()
            self.assertGreater(indexed, 0)
            
            # Search and verify we can retrieve features, reference compounds and model cards
            matches = self.store.search("MockPesticide")
            self.assertTrue(any(m.entity_id == "ref_001" for m in matches))
            
            matches_mc = self.store.search("test model card")
            self.assertTrue(any(m.entity_id == "test_model_card" for m in matches_mc))

class MockContentBlock:
    def __init__(self, text):
        self.text = text

class MockUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

class MockResponse:
    def __init__(self, text, input_tokens, output_tokens):
        self.content = [MockContentBlock(text)]
        self.usage = MockUsage(input_tokens, output_tokens)

class TestClaudeQAService(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp()
        self.store = KnowledgeEmbeddingStore(store_path=Path(self.temp_db_path))
        
        # Populate store with a few mock documents
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        dummy_vec = np.ones(384, dtype=np.float32) / np.sqrt(384)
        dummy_bytes = dummy_vec.tobytes()
        
        cursor.execute(
            "INSERT INTO embeddings (id, entity_type, entity_id, text, embedding, hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("pesticide_1", "pesticide", "imidacloprid", "Imidacloprid bee toxicity details", sqlite3.Binary(dummy_bytes), "h1", "now")
        )
        cursor.execute(
            "INSERT INTO embeddings (id, entity_type, entity_id, text, embedding, hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("framework_1", "framework", "section_1", "Briggs xylem systemicity rules", sqlite3.Binary(dummy_bytes), "h2", "now")
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    @patch('anthropic.Anthropic')
    def test_service_ask_and_citations(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        
        # Configure Anthropic model response
        mock_client.messages.create.return_value = MockResponse(
            text="Imidacloprid has high toxicity [Source-1]. Briggs rules are xylem transport coefficients [Source-2].",
            input_tokens=150,
            output_tokens=80
        )
        
        service = ClaudeQAService(anthropic_api_key="mock_key", embedding_store=self.store)
        res = service.answer("Tell me about Imidacloprid and Briggs")
        
        self.assertEqual(res["query"], "Tell me about Imidacloprid and Briggs")
        self.assertIn("toxicity [Source-1]", res["answer"])
        self.assertIn("[Source-2]", res["answer"])
        
        # Verify citation mappings
        citations = res["citations"]
        self.assertEqual(len(citations), 2)
        
        self.assertEqual(citations[0]["label"], "[Source-1]")
        self.assertEqual(citations[0]["entity_id"], "imidacloprid")
        
        self.assertEqual(citations[1]["label"], "[Source-2]")
        self.assertEqual(citations[1]["entity_id"], "section_1")

    @patch('anthropic.Anthropic')
    def test_strip_hallucinated_citations(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        
        # Model returns citation [Source-99] which does not exist in context matches (we only have 2)
        mock_client.messages.create.return_value = MockResponse(
            text="We found high toxicity [Source-1] and some fake info [Source-99].",
            input_tokens=100,
            output_tokens=50
        )
        
        service = ClaudeQAService(anthropic_api_key="mock_key", embedding_store=self.store)
        res = service.answer("Tell me about Imidacloprid")
        
        # Valid citations only
        self.assertEqual(len(res["citations"]), 1)
        self.assertEqual(res["citations"][0]["label"], "[Source-1]")
        
        # Check that [Source-99] is stripped out from the cleaned text
        self.assertNotIn("[Source-99]", res["answer"])
        self.assertIn("[Source-1]", res["answer"])

    @patch('anthropic.Anthropic')
    def test_model_cost_calculation(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        
        mock_client.messages.create.return_value = MockResponse(
            text="Response text",
            input_tokens=1000,
            output_tokens=500
        )
        
        # 1. Haiku cost: $0.80/M input, $4.00/M output -> 1000 * 0.8 / 1e6 + 500 * 4.0 / 1e6 = 0.0008 + 0.0020 = 0.0028
        service_haiku = ClaudeQAService(anthropic_api_key="mock_key", embedding_store=self.store, model="claude-3-5-haiku-20241022")
        res_haiku = service_haiku.answer("query")
        self.assertAlmostEqual(res_haiku["tokens_used"]["cost_usd"], 0.0028, places=6)
        
        # 2. Sonnet cost: $3.00/M input, $15.00/M output -> 1000 * 3.0 / 1e6 + 500 * 15.0 / 1e6 = 0.0030 + 0.0075 = 0.0105
        service_sonnet = ClaudeQAService(anthropic_api_key="mock_key", embedding_store=self.store, model="claude-3-5-sonnet-20241022")
        res_sonnet = service_sonnet.answer("query")
        self.assertAlmostEqual(res_sonnet["tokens_used"]["cost_usd"], 0.0105, places=6)

class TestLocalLLMQAService(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp()
        self.store = KnowledgeEmbeddingStore(store_path=Path(self.temp_db_path))
        
        # Populate store with a few mock documents
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        dummy_vec = np.ones(384, dtype=np.float32) / np.sqrt(384)
        dummy_bytes = dummy_vec.tobytes()
        
        cursor.execute(
            "INSERT INTO embeddings (id, entity_type, entity_id, text, embedding, hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("pesticide_1", "pesticide", "imidacloprid", "Imidacloprid bee toxicity details", sqlite3.Binary(dummy_bytes), "h1", "now")
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    @patch('requests.post')
    def test_local_service_ask_and_citations(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Imidacloprid is active [Source-1]. Fake info here [Source-2]."
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 60
            }
        }
        mock_post.return_value = mock_resp
        
        from edeon_knowledge.qa.local_llm_service import LocalLLMQAService
        service = LocalLLMQAService(
            endpoint_url="http://localhost:11434/v1",
            embedding_store=self.store,
            model="qwen2.5:3b"
        )
        
        res = service.answer("Tell me about Imidacloprid")
        
        self.assertEqual(res["query"], "Tell me about Imidacloprid")
        self.assertIn("active [Source-1]", res["answer"])
        self.assertNotIn("[Source-2]", res["answer"]) # stripped because we only have 1 source matching range
        self.assertEqual(res["tokens_used"]["cost_usd"], 0.0)
        self.assertEqual(res["tokens_used"]["model"], "qwen2.5:3b")
        
        citations = res["citations"]
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["label"], "[Source-1]")
        self.assertEqual(citations[0]["entity_id"], "imidacloprid")

if __name__ == "__main__":
    unittest.main()
