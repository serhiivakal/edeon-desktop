/* ==========================================================
   Edeon Desktop — Agrochemical Knowledge Store
   Zustand store synced with Tauri backend for local and
   API-enriched pesticide search.
   ========================================================== */

import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';
import type { KnowledgeRecord } from '../types';

// Module-level generation counter to detect stale responses
let _searchGen = 0;

interface ConversationSummary {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  starred: number;
}

interface MessageRecord {
  message_id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Array<{
    label: string;
    entity_id: string;
    entity_type: string;
    text: string;
    source_url: string | null;
  }>;
  retrieved_sources: Array<{
    entity_id: string;
    entity_type: string;
    text: string;
    source_url: string | null;
  }>;
  tokens_used: {
    input_tokens?: number;
    output_tokens?: number;
    cost_usd?: number;
    model?: string;
  };
  timestamp: string;
}

interface ConversationDetails {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  starred: number;
  messages: MessageRecord[];
}

interface KnowledgeState {
  searchQuery: string;
  selectedDatabases: string[]; // e.g. ['PPDB', 'ECOTOX', 'OpenFoodTox', 'ChEMBL']
  results: KnowledgeRecord[];
  selectedResultId: string | null;
  loading: boolean;
  error: string | null;

  // AI Chat State
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  activeConversation: ConversationDetails | null;
  chatLoading: boolean;
  chatError: string | null;
  reindexing: boolean;
  reindexSuccess: boolean;
  reindexError: string | null;

  // Actions
  setSearchQuery: (query: string) => void;
  toggleDatabaseFilter: (db: string) => void;
  setSelectedResultId: (id: string | null) => void;
  triggerSearch: () => Promise<void>;
  resetSearch: () => void;

  // AI Chat Actions
  listConversations: () => Promise<void>;
  loadConversation: (id: string) => Promise<void>;
  setActiveConversationId: (id: string | null) => void;
  askQuestion: (query: string) => Promise<void>;
  starConversation: (id: string, starred: boolean) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  reindexKnowledgeHub: (force?: boolean) => Promise<void>;
  clearActiveConversation: () => void;
}

export const useKnowledgeStore = create<KnowledgeState>((set, get) => ({
  searchQuery: '',
  selectedDatabases: ['PPDB', 'ECOTOX', 'OpenFoodTox', 'ChEMBL'],
  results: [],
  selectedResultId: null,
  loading: false,
  error: null,

  // AI Chat Initial State
  conversations: [],
  activeConversationId: null,
  activeConversation: null,
  chatLoading: false,
  chatError: null,
  reindexing: false,
  reindexSuccess: false,
  reindexError: null,

  setSearchQuery: (query: string) => {
    set({ searchQuery: query });
  },

  toggleDatabaseFilter: (db: string) => {
    const { selectedDatabases } = get();
    if (selectedDatabases.includes(db)) {
      set({ selectedDatabases: selectedDatabases.filter((d) => d !== db) });
    } else {
      set({ selectedDatabases: [...selectedDatabases, db] });
    }
    get().triggerSearch();
  },

  setSelectedResultId: (id: string | null) => {
    set({ selectedResultId: id });
  },

  triggerSearch: async () => {
    if (get().loading) return;

    const gen = ++_searchGen;
    const { searchQuery, selectedDatabases } = get();
    set({ loading: true, error: null });
    try {
      const results = await invoke<KnowledgeRecord[]>('search_knowledge', {
        query: searchQuery,
        databases: selectedDatabases,
      });

      if (gen !== _searchGen) return;
      
      const currentSelected = get().selectedResultId;
      let nextSelected = currentSelected;
      if (results.length > 0) {
        if (!currentSelected || !results.some((r) => r.id === currentSelected)) {
          nextSelected = results[0].id;
        }
      } else {
        nextSelected = null;
      }

      set({ 
        results, 
        selectedResultId: nextSelected,
        loading: false 
      });
    } catch (e) {
      if (gen !== _searchGen) return;
      set({ 
        error: String(e), 
        loading: false 
      });
    }
  },

  resetSearch: () => {
    set({
      searchQuery: '',
      results: [],
      selectedResultId: null,
      error: null,
      loading: false,
    });
  },

  // AI Chat Actions
  listConversations: async () => {
    try {
      const list = await invoke<ConversationSummary[]>('knowledge_qa_list_conversations');
      set({ conversations: list });
    } catch (e) {
      set({ chatError: `Failed to fetch conversations: ${e}` });
    }
  },

  loadConversation: async (id: string) => {
    set({ chatLoading: true, chatError: null });
    try {
      const details = await invoke<ConversationDetails>('knowledge_qa_load_conversation', {
        conversationId: id
      });
      set({
        activeConversation: details,
        activeConversationId: id,
        chatLoading: false
      });
    } catch (e) {
      set({
        chatError: `Failed to load conversation: ${e}`,
        chatLoading: false
      });
    }
  },

  setActiveConversationId: (id: string | null) => {
    if (id === null) {
      set({ activeConversationId: null, activeConversation: null });
    } else {
      get().loadConversation(id);
    }
  },

  clearActiveConversation: () => {
    set({ activeConversationId: null, activeConversation: null, chatError: null });
  },

  askQuestion: async (query: string) => {
    if (!query.trim()) return;

    set({ chatLoading: true, chatError: null });
    try {
      // 1. Fetch LLM settings from DB
      const provider = await invoke<string | null>('get_setting', { key: 'llm_provider' }) || 'local';
      const apiKey = await invoke<string | null>('get_setting', { key: 'anthropic_api_key' }) || '';
      const model = await invoke<string | null>('get_setting', { key: 'anthropic_model' }) || 'claude-3-5-haiku-20241022';
      
      const localEndpoint = await invoke<string | null>('get_setting', { key: 'local_llm_endpoint' }) || 'http://localhost:11434/v1';
      const localModel = await invoke<string | null>('get_setting', { key: 'local_llm_model' }) || 'qwen2.5:3b';
      const localApiKey = await invoke<string | null>('get_setting', { key: 'local_llm_api_key' }) || '';

      if (provider === 'anthropic' && (!apiKey || apiKey.trim() === '')) {
        set({
          chatError: 'Anthropic API key is not configured. Please enter it in the settings panel.',
          chatLoading: false
        });
        return;
      }

      if (provider === 'local' && (!localEndpoint || localEndpoint.trim() === '')) {
        set({
          chatError: 'Local LLM Endpoint is not configured. Please enter it in the settings panel.',
          chatLoading: false
        });
        return;
      }

      // 2. Trigger QA query
      const result = await invoke<any>('knowledge_qa_ask', {
        query,
        conversationId: get().activeConversationId,
        provider,
        apiKey,
        model,
        localEndpoint,
        localModel,
        localApiKey
      });

      // 4. Update states
      const newConvId = result.conversation_id;
      await get().loadConversation(newConvId);
      await get().listConversations();
    } catch (e) {
      set({
        chatError: String(e),
        chatLoading: false
      });
    }
  },

  starConversation: async (id: string, starred: boolean) => {
    try {
      await invoke('knowledge_qa_star_conversation', {
        conversationId: id,
        starred
      });
      // Refresh list
      await get().listConversations();
      // If active conversation, refresh details
      if (get().activeConversationId === id) {
        await get().loadConversation(id);
      }
    } catch (e) {
      set({ chatError: `Failed to star conversation: ${e}` });
    }
  },

  deleteConversation: async (id: string) => {
    try {
      await invoke('knowledge_qa_delete_conversation', {
        conversationId: id
      });
      // Clear active conversation if deleted
      if (get().activeConversationId === id) {
        set({ activeConversationId: null, activeConversation: null });
      }
      await get().listConversations();
    } catch (e) {
      set({ chatError: `Failed to delete conversation: ${e}` });
    }
  },

  reindexKnowledgeHub: async (force: boolean = false) => {
    set({ reindexing: true, reindexSuccess: false, reindexError: null });
    try {
      await invoke<any>('knowledge_qa_reindex', { force });
      set({
        reindexing: false,
        reindexSuccess: true
      });
      // Clear success indicator after 3 seconds
      setTimeout(() => {
        set({ reindexSuccess: false });
      }, 3000);
    } catch (e) {
      set({
        reindexing: false,
        reindexError: String(e)
      });
    }
  }
}));

