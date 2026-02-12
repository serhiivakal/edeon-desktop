# Edeon Knowledge Hub Layer 3 (RAG) Architecture & Usage Guide

Edeon's Knowledge Hub Layer 3 implements a secure, local-first Retrieval-Augmented Generation (RAG) pipeline. This system grounds LLM responses exclusively in the verified, structured content available in the Edeon Knowledge Hub databases (including model cards, pesticide registries, and regulatory guidelines).

---

## 1. Architectural Overview

The RAG pipeline is designed to work fully offline for search and indexing, using local embedding models, and calls the Anthropic Claude API using encrypted credentials for generating grounded responses.

```
+-----------------------------------------------------------------+
|                         React Frontend                          |
|  - Three-Pane Chat Interface                                    |
|  - Encrypted Credentials Store (SQLite settings)                |
+-------------------------------+---------------------------------+
                                |
                                | Tauri IPC Invoke
                                v
+-----------------------------------------------------------------+
|                       Tauri / Rust Shell                        |
|  - Decrypts Anthropic API Key (Fernet / MAC address salt)       |
|  - Coordinates local vector database querying                   |
+-------------------------------+---------------------------------+
                                |
                                | JSON-RPC Stdin/Stdout
                                v
+-----------------------------------------------------------------+
|                         Python Sidecar                          |
|                                                                 |
|   +-------------------+              +-----------------------+  |
|   |  Embedding Store  |              |    Claude service     |  |
|   |  - all-MiniLM-L6  |              |  - Grounding Prompts  |  |
|   |  - Cosine Sim     |              |  - Citation Parser    |  |
|   +---------+---------+              +-----------+-----------+  |
|             |                                    |              |
+-------------|------------------------------------|--------------+
              |                                    |
              | SQLite query                       | HTTPS API request
              v                                    v
       data/knowledge.db                   Anthropic API Gateway
```

---

## 2. Key Components

### A. Embedding & Vector Indexing (`python/edeon_knowledge/embedding/`)
* **Local Embedding Model**: By default, `all-MiniLM-L6-v2` (384-dimensional dense vectors) is used via `sentence-transformers` for fast local inference.
* **Storage**: Vector databases are mapped in Edeon's database `data/knowledge/embeddings.db`. Vectors are stored as binary BLOBs and compared using optimized numpy cosine similarity.
* **Incremental Indexing**: Search indexes walk files, indexing modified dates to minimize redundant embedding calculations.

### B. Secure API Key Encryption (`python/edeon_knowledge/qa/encryption.py`)
To prevent plaintext exposure of private Anthropic API keys at rest:
* Edeon utilizes **Fernet symmetric cryptography**.
* The encryption key is derived using a PBKDF2 key derivation function salted with the local machine's unique **hardware MAC address**.
* Decryption happens in memory only when a query is dispatched.

### C. Grounding & Citation Validation (`python/edeon_knowledge/qa/claude_service.py`)
To eliminate LLM hallucinations and enforce compliance:
* **System Prompt Constraints**: Enforces that Claude answers *only* from the provided context sources. If the context does not contain the answer, it responds: *"I don't have information about that in the Knowledge Hub."*
* **Citation Extraction**: The service parses inline tags matching `[Source-X]`.
* **Post-processing Validation**: Compares parsed citations against the indices of retrieved sources. Any hallucinated citation (e.g., referencing source indices outside the retrieved array) is automatically stripped from the text before sending the payload to the frontend.

---

## 3. UI and UX Design

The user interface is integrated into Edeon's **Knowledge Hub** view and features a three-pane layout:
1. **Left Pane (History Sidebar)**: Displays previous chat history records, starring flags, and delete commands (persisted in Edeon's SQLite database).
2. **Center Pane (Chat Thread)**: Renders standard conversation cards. Clicking inline source badges (e.g., `[Source-1]`) highlights the reference inside the citation pane.
3. **Right Pane (Citation Drawer)**: Expands to show details of cited sources (source title, text content snippet, database provenance, and external URLs).

---

## 4. Usage & Configuration

### Settings View
Under Edeon's Settings panel, users can configure:
* **Anthropic API Key**: Input field with hidden characters. Key is validated and encrypted locally.
* **LLM Model**: Select between `claude-3-5-haiku` (fast and economic) or `claude-3-5-sonnet` (for complex, multi-hop reasoning).

### Token Cost Tracking
Every query response displays token consumption and approximate USD costs in the bottom status indicator:
* **Claude 3.5 Haiku**: Input: \$0.80 / MTok | Output: \$4.00 / MTok
* **Claude 3.5 Sonnet**: Input: \$3.00 / MTok | Output: \$15.00 / MTok
