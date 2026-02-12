import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from edeon_knowledge.embedding.store import KnowledgeEmbeddingStore, KnowledgeMatch

class ClaudeQAService:
    """
    RAG QA assistant powered by Anthropic's Claude API.
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

    def __init__(self, anthropic_api_key: str,
                 embedding_store: KnowledgeEmbeddingStore,
                 model: str = "claude-3-5-haiku-20241022",
                 max_context_tokens: int = 30000):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=anthropic_api_key)
        self._embedding_store = embedding_store
        self._model = model
        self._max_context_tokens = max_context_tokens

    def answer(self, query: str, conversation_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Runs RAG vector search, constructs prompt, calls Claude, and returns validated citations."""
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
        messages = []
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

        # 4. Invoke Claude API
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=1500,
                system=self.SYSTEM_PROMPT,
                messages=messages
            )
        except Exception as e:
            raise RuntimeError(f"Anthropic API call failed: {e}")

        # 5. Extract token counts
        input_tokens = resp.usage.input_tokens
        output_tokens = resp.usage.output_tokens
        
        # Calculate cost in USD based on standard models pricing
        # Claude 3.5 Haiku: $0.80 / MTok input, $4.00 / MTok output
        # Claude 3.5 Sonnet: $3.00 / MTok input, $15.00 / MTok output
        is_sonnet = "sonnet" in self._model.lower()
        is_opus = "opus" in self._model.lower()
        
        if is_sonnet:
            cost = (input_tokens * 3.0 / 1e6) + (output_tokens * 15.0 / 1e6)
        elif is_opus:
            cost = (input_tokens * 15.0 / 1e6) + (output_tokens * 75.0 / 1e6)
        else: # Default Haiku
            cost = (input_tokens * 0.8 / 1e6) + (output_tokens * 4.0 / 1e6)
            
        tokens_used = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "model": self._model
        }

        # 6. Extract text response
        answer_text = ""
        for content_block in resp.content:
            if hasattr(content_block, "text"):
                answer_text += content_block.text

        # 7. Validate and clean citations
        citations = []
        # Find any citation matching "[Source-X]"
        citation_pattern = re.compile(r"\[Source-(\d+)\]")
        raw_citations = citation_pattern.findall(answer_text)
        
        valid_indices = set()
        for idx_str in raw_citations:
            idx = int(idx_str)
            # If citation index falls in range of retrieved sources
            if 1 <= idx <= len(matches):
                valid_indices.add(idx)
                
        # Clean response text from invalid/hallucinated citations
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
