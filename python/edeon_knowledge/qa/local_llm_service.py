import re
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from edeon_knowledge.embedding.store import KnowledgeEmbeddingStore

class LocalLLMQAService:
    """
    RAG QA assistant powered by a locally running OpenAI-compatible API (e.g., Ollama or LM Studio).
    Enforces strict context boundaries and inline citation extraction.
    """
    
    SYSTEM_PROMPT = """You are Edeon's research assistant. You answer questions about
agrochemicals, pesticides, and related regulatory science. You answer ONLY from the
context provided in each user message. If the context does not contain the answer,
say "I don't have information about that in the Knowledge Hub" — do NOT use general
knowledge.

For every factual claim in your answer, cite the supporting source using inline
citations in the format [Source-X] (where X is the Source ID, e.g. [Source-1]). Do NOT make up citations.

Be concise. Be technically accurate. Do not speculate. Do not extrapolate beyond
the provided context."""

    def __init__(self,
                 endpoint_url: str,
                 embedding_store: KnowledgeEmbeddingStore,
                 model: str = "qwen2.5:3b",
                 api_key: Optional[str] = None):
        self._endpoint_url = endpoint_url.rstrip('/')
        self._embedding_store = embedding_store
        self._model = model
        self._api_key = api_key or "local-token"

    def answer(self, query: str, conversation_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Runs RAG vector search, constructs prompt, calls Local LLM, and returns validated citations."""
        # 1. Retrieve top-k matches from local vector index
        matches = self._embedding_store.search(query, top_k=6)
        
        # 2. Build context block
        context_blocks = []
        for idx, match in enumerate(matches):
            context_blocks.append(
                f"Source ID: [Source-{idx + 1}]\n"
                f"Entity ID: {match.entity_id} (Type: {match.entity_type})\n"
                f"Content:\n{match.text}\n"
                f"----------------------------------------"
            )
        
        context_text = "\n".join(context_blocks)
        
        # 3. Format conversational messages
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role")
                content = msg.get("content")
                if role in ["user", "assistant"]:
                    messages.append({"role": role, "content": content})
                    
        # Append the final user message carrying the context and query
        user_prompt = (
            f"Here are the retrieved sources from Edeon's local databases:\n\n"
            f"{context_text}\n\n"
            f"Based on the sources above, answer the query: {query}"
        )
        messages.append({"role": "user", "content": user_prompt})

        # 4. Invoke Local LLM API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}"
        }
        
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.0, # Strict grounding
            "max_tokens": 1500
        }

        # Try configured URL first
        url = f"{self._endpoint_url}/chat/completions"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            resp_data = resp.json()
        except Exception as e:
            # Check if it was localhost / 127.0.0.1 and try resolving host nameserver from WSL
            from urllib.parse import urlparse
            parsed = urlparse(self._endpoint_url)
            if parsed.hostname in ("localhost", "127.0.0.1"):
                wsl_host_ip = None
                try:
                    with open("/etc/resolv.conf", "r") as f:
                        for line in f:
                            if line.startswith("nameserver"):
                                wsl_host_ip = line.split()[1].strip()
                                break
                except Exception:
                    pass
                
                if wsl_host_ip:
                    port_str = f":{parsed.port}" if parsed.port else ""
                    new_endpoint = f"{parsed.scheme}://{wsl_host_ip}{port_str}{parsed.path}"
                    fallback_url = f"{new_endpoint}/chat/completions"
                    try:
                        resp = requests.post(fallback_url, headers=headers, json=payload, timeout=60)
                        resp.raise_for_status()
                        resp_data = resp.json()
                    except Exception as fallback_exc:
                        raise RuntimeError(
                            f"Local LLM API call failed.\n"
                            f"Tried WSL loopback: {url} (Error: {e})\n"
                            f"Tried WSL host IP: {fallback_url} (Error: {fallback_exc})\n\n"
                            f"Please ensure Ollama or LM Studio is running on your Windows host and listening on all interfaces.\n"
                            f"- For Ollama on Windows, set the system environment variable OLLAMA_HOST=0.0.0.0 and restart Ollama.\n"
                            f"- For LM Studio on Windows, enable 'Local Server' and ensure 'Share on local network' is checked."
                        )
                else:
                    raise RuntimeError(
                        f"Local LLM API call failed at {url}: {e}\n\n"
                        f"Please ensure Ollama or LM Studio is running on your Windows host."
                    )
            else:
                raise RuntimeError(f"Local LLM API call failed at {url}: {e}")

        # 5. Extract token counts
        usage = resp_data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        
        # Cost is 0 for local execution, save model name for dynamic UI labeling
        tokens_used = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": 0.0,
            "model": self._model
        }

        # 6. Extract text response
        choices = resp_data.get("choices", [])
        if not choices:
            raise RuntimeError("Empty response received from local LLM")
            
        answer_text = choices[0].get("message", {}).get("content", "")

        # 7. Validate and clean citations
        citations = []
        citation_pattern = re.compile(r"\[Source-(\d+)\]")
        raw_citations = citation_pattern.findall(answer_text)
        
        valid_indices = set()
        for idx_str in raw_citations:
            idx = int(idx_str)
            if 1 <= idx <= len(matches):
                valid_indices.add(idx)
                
        def clean_citation(match_obj):
            idx = int(match_obj.group(1))
            if 1 <= idx <= len(matches):
                return f"[Source-{idx}]"
            return "" # Strip invalid citation
            
        cleaned_answer = citation_pattern.sub(clean_citation, answer_text)

        # Build list of active citations
        for idx in sorted(valid_indices):
            match_obj = matches[idx - 1]
            citations.append({
                "label": f"[Source-{idx}]",
                "entity_id": match_obj.entity_id,
                "entity_type": match_obj.entity_type,
                "text": match_obj.text,
                "source_url": match_obj.source_url
            })

        # Return structured results
        return {
            "query": query,
            "answer": cleaned_answer,
            "citations": citations,
            "retrieved_sources": [
                {
                    "entity_id": m.entity_id,
                    "entity_type": m.entity_type,
                    "text": m.text,
                    "source_url": m.source_url,
                    "citation": m.citation
                }
                for m in matches
            ],
            "model": self._model,
            "tokens_used": tokens_used,
            "timestamp": datetime.utcnow().isoformat()
        }
