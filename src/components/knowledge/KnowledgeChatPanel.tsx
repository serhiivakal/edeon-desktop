import React, { useState, useEffect, useRef } from 'react';
import { useKnowledgeStore } from '../../store/knowledgeStore';
import { EmptyState } from '../shared/EmptyState';
import { Bot } from 'lucide-react';

import { useSettingsStore } from '../../store/settingsStore';

export function KnowledgeChatPanel() {
  const { ollamaStatus, ollamaProgress } = useSettingsStore();
  const {
    conversations,
    activeConversationId,
    activeConversation,
    chatLoading,
    chatError,
    reindexing,
    reindexSuccess,
    reindexError,
    listConversations,
    setActiveConversationId,
    clearActiveConversation,
    askQuestion,
    starConversation,
    deleteConversation,
    reindexKnowledgeHub,
  } = useKnowledgeStore();

  const [inputVal, setInputVal] = useState('');
  const [selectedCitation, setSelectedCitation] = useState<any | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Fetch conversations on load
  useEffect(() => {
    listConversations();
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages, chatLoading]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim() || chatLoading) return;
    askQuestion(inputVal);
    setInputVal('');
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  // Simple Markdown & Citation Parsing for Assistant Messages
  const renderMessageContent = (content: string, citations: any[]) => {
    if (!content) return null;

    // Split text by citations e.g. [Source-1]
    const parts = content.split(/(\[Source-\d+\])/g);
    
    // Parse formatting like **bold** and `code` inline
    const formatText = (text: string) => {
      const boldParts = text.split(/(\*\*.*?\*\*)/g);
      return boldParts.map((bp, i) => {
        if (bp.startsWith('**') && bp.endsWith('**')) {
          return <strong key={i}>{bp.slice(2, -2)}</strong>;
        }
        
        const codeParts = bp.split(/(`.*?`)/g);
        return codeParts.map((cp, j) => {
          if (cp.startsWith('`') && cp.endsWith('`')) {
            return <code key={j} className="inline-code">{cp.slice(1, -1)}</code>;
          }
          return cp;
        });
      });
    };

    return (
      <div className="message-text-wrapper">
        {parts.map((part, index) => {
          const isCitation = part.match(/^\[Source-(\d+)\]$/);
          if (isCitation) {
            const citeLabel = part;
            const citationObj = citations?.find((c) => c.label === citeLabel);
            return (
              <button
                key={index}
                type="button"
                className={`citation-badge ${selectedCitation?.label === citeLabel ? 'active' : ''}`}
                onClick={() => {
                  if (citationObj) {
                    setSelectedCitation(citationObj);
                  }
                }}
                title={citationObj ? `Click to inspect: ${citationObj.entity_id}` : 'Inspect source'}
              >
                {citeLabel}
              </button>
            );
          }
          
          // Split by list items or newlines
          const lines = part.split('\n');
          return lines.map((line, lineIdx) => {
            const isBullet = line.trim().startsWith('- ');
            if (isBullet) {
              return (
                <ul key={`${index}-${lineIdx}`} className="chat-bullet-list">
                  <li>{formatText(line.trim().slice(2))}</li>
                </ul>
              );
            }
            return (
              <span key={`${index}-${lineIdx}`}>
                {formatText(line)}
                {lineIdx < lines.length - 1 && <br />}
              </span>
            );
          });
        })}
      </div>
    );
  };

  return (
    <div className="knowledge-chat-container">
      {/* Dynamic Embedded CSS to maintain premium styling with absolute safety */}
      <style>{`
        .knowledge-chat-container {
          display: flex;
          height: calc(100vh - 200px);
          border: 1px solid var(--color-border);
          border-radius: 8px;
          background-color: var(--color-surface);
          overflow: hidden;
          font-family: var(--font-family);
        }
        .chat-sidebar {
          width: 260px;
          background-color: var(--color-sidebar);
          border-right: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          flex-shrink: 0;
        }
        .sidebar-header {
          padding: 12px 16px;
          border-bottom: 1px solid var(--color-border);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .sidebar-header h2 {
          font-size: 13px;
          font-weight: 700;
          color: var(--color-brand-900);
          margin: 0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .new-chat-btn {
          background-color: var(--color-brand-700);
          color: var(--color-brand-100);
          border: none;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 600;
          cursor: pointer;
          transition: background-color 0.2s;
        }
        .new-chat-btn:hover {
          background-color: var(--color-brand-600);
        }
        .conversations-list {
          flex: 1;
          overflow-y: auto;
          padding: 8px;
        }
        .conversation-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 12px;
          border-radius: 6px;
          margin-bottom: 4px;
          cursor: pointer;
          font-size: 12px;
          transition: background-color 0.15s;
        }
        .conversation-item:hover {
          background-color: rgba(0, 0, 0, 0.04);
        }
        .conversation-item.active {
          background-color: var(--color-brand-100);
          color: var(--color-brand-900);
          font-weight: 600;
        }
        .conv-title {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          flex: 1;
          padding-right: 8px;
        }
        .conv-actions {
          display: flex;
          gap: 6px;
          opacity: 0.4;
          transition: opacity 0.2s;
        }
        .conversation-item:hover .conv-actions,
        .conversation-item.active .conv-actions {
          opacity: 1;
        }
        .action-icon-btn {
          background: none;
          border: none;
          cursor: pointer;
          padding: 2px;
          font-size: 11px;
          color: var(--color-text-600);
          transition: color 0.15s;
        }
        .action-icon-btn:hover {
          color: var(--color-brand-900);
        }
        .action-icon-btn.star-active {
          color: var(--color-amber-700);
        }
        .action-icon-btn.delete-btn:hover {
          color: var(--color-red-700);
        }
        .chat-main {
          flex: 1;
          display: flex;
          flex-direction: column;
          background-color: var(--color-bg);
          position: relative;
        }
        .chat-header {
          padding: 12px 20px;
          background-color: var(--color-surface);
          border-bottom: 1px solid var(--color-border);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .chat-header h3 {
          margin: 0;
          font-size: 14px;
          font-weight: 600;
          color: var(--color-text-900);
        }
        .reindex-panel {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .reindex-btn {
          background-color: transparent;
          color: var(--color-brand-700);
          border: 1px solid var(--color-brand-50);
          padding: 4px 10px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }
        .reindex-btn:hover {
          background-color: var(--color-brand-100);
          border-color: var(--color-brand-600);
        }
        .reindex-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .chat-messages {
          flex: 1;
          overflow-y: auto;
          padding: 20px;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .chat-empty {
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          text-align: center;
          color: var(--color-text-600);
          padding: 40px;
        }
        .chat-empty-icon {
          font-size: 40px;
          margin-bottom: 16px;
        }
        .chat-empty h4 {
          margin: 0 0 8px 0;
          font-size: 15px;
          font-weight: 600;
          color: var(--color-brand-900);
        }
        .chat-empty p {
          font-size: 12px;
          max-width: 320px;
          margin: 0;
        }
        .message-bubble {
          max-width: 75%;
          padding: 12px 16px;
          border-radius: 12px;
          font-size: 12.5px;
          line-height: 1.5;
        }
        .message-bubble.user {
          align-self: flex-end;
          background-color: var(--color-brand-100);
          color: var(--color-brand-900);
          border-bottom-right-radius: 2px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }
        .message-bubble.assistant {
          align-self: flex-start;
          background-color: var(--color-surface);
          color: var(--color-text-900);
          border: 1px solid var(--color-border);
          border-bottom-left-radius: 2px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }
        .message-footer {
          margin-top: 8px;
          font-size: 10px;
          color: var(--color-text-400);
          display: flex;
          justify-content: space-between;
        }
        .inline-code {
          background-color: rgba(0,0,0,0.06);
          color: var(--color-red-700);
          padding: 2px 4px;
          border-radius: 3px;
          font-family: var(--font-mono);
          font-size: 11px;
        }
        .chat-bullet-list {
          margin: 4px 0;
          padding-left: 20px;
        }
        .citation-badge {
          background-color: var(--color-blue-100);
          color: var(--color-blue-700);
          border: 1px solid var(--color-blue-50);
          border-radius: 3px;
          font-size: 10px;
          font-weight: 700;
          padding: 1px 4px;
          margin: 0 2px;
          cursor: pointer;
          display: inline-block;
          vertical-align: middle;
          transition: all 0.15s;
        }
        .citation-badge:hover, .citation-badge.active {
          background-color: var(--color-blue-700);
          color: white;
          border-color: var(--color-blue-700);
        }
        .chat-input-area {
          padding: 16px 20px;
          background-color: var(--color-surface);
          border-top: 1px solid var(--color-border);
        }
        .chat-form {
          display: flex;
          gap: 12px;
        }
        .chat-textarea {
          flex: 1;
          height: 40px;
          border: 1px solid var(--color-border);
          border-radius: 6px;
          padding: 10px 12px;
          font-size: 12.5px;
          resize: none;
          outline: none;
          transition: border-color 0.2s;
        }
        .chat-textarea:focus {
          border-color: var(--color-brand-600);
        }
        .send-chat-btn {
          background-color: var(--color-brand-700);
          color: var(--color-brand-100);
          border: none;
          padding: 0 16px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: background-color 0.2s;
        }
        .send-chat-btn:hover {
          background-color: var(--color-brand-600);
        }
        .send-chat-btn:disabled {
          background-color: var(--color-text-400);
          cursor: not-allowed;
        }
        .chat-status-bar {
          margin-top: 8px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 10px;
          color: var(--color-text-600);
        }
        .chat-drawer {
          width: 300px;
          background-color: var(--color-surface);
          border-left: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          flex-shrink: 0;
        }
        .drawer-header {
          padding: 12px 16px;
          border-bottom: 1px solid var(--color-border);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .drawer-header h4 {
          margin: 0;
          font-size: 12px;
          font-weight: 700;
          color: var(--color-brand-900);
          text-transform: uppercase;
        }
        .close-drawer-btn {
          background: none;
          border: none;
          cursor: pointer;
          font-size: 13px;
          color: var(--color-text-600);
        }
        .drawer-content {
          flex: 1;
          overflow-y: auto;
          padding: 16px;
          font-size: 12px;
          line-height: 1.5;
        }
        .drawer-source-meta {
          background-color: var(--color-sidebar);
          padding: 8px;
          border-radius: 4px;
          margin-bottom: 12px;
          border: 1px solid var(--color-border);
        }
        .drawer-source-text {
          white-space: pre-wrap;
          color: var(--color-text-900);
          background-color: #fafafa;
          padding: 10px;
          border-radius: 4px;
          border: 1px dashed var(--color-border);
        }
        .chat-warning-card {
          margin: 20px;
          padding: 16px;
          border: 1px solid var(--color-amber-50);
          background-color: var(--color-amber-100);
          border-radius: 6px;
          color: var(--color-amber-700);
          font-size: 12px;
          line-height: 1.4;
        }
        .chat-warning-card strong {
          color: #7A4F01;
        }
        .loading-dots span {
          animation: blink 1.4s infinite both;
          font-weight: bold;
        }
        .loading-dots span:nth-child(2) { animation-delay: .2s; }
        .loading-dots span:nth-child(3) { animation-delay: .4s; }
        @keyframes blink {
          0% { opacity: .2; }
          20% { opacity: 1; }
          100% { opacity: .2; }
        }
      `}</style>

      {/* 1. Conversations Sidebar */}
      <div className="chat-sidebar">
        <div className="sidebar-header">
          <h2>Conversations</h2>
          <button
            type="button"
            className="new-chat-btn"
            onClick={() => {
              clearActiveConversation();
              setSelectedCitation(null);
            }}
          >
            + New
          </button>
        </div>
        <div className="conversations-list">
          {conversations.length === 0 ? (
            <div style={{ padding: '16px', textAlign: 'center', fontSize: '11px', color: 'var(--color-text-400)' }}>
              No chat history.
            </div>
          ) : (
            conversations.map((c) => (
              <div
                key={c.conversation_id}
                className={`conversation-item ${activeConversationId === c.conversation_id ? 'active' : ''}`}
                onClick={() => {
                  setActiveConversationId(c.conversation_id);
                  setSelectedCitation(null);
                }}
              >
                <span className="conv-title" title={c.title}>
                  {c.starred === 1 ? '★ ' : ''}{c.title}
                </span>
                <div className="conv-actions">
                  <button
                    type="button"
                    className={`action-icon-btn ${c.starred === 1 ? 'star-active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      starConversation(c.conversation_id, c.starred === 0);
                    }}
                    title={c.starred === 1 ? 'Unstar' : 'Star'}
                  >
                    ★
                  </button>
                  <button
                    type="button"
                    className="action-icon-btn delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm('Are you sure you want to delete this conversation?')) {
                        deleteConversation(c.conversation_id);
                      }
                    }}
                    title="Delete"
                  >
                    🗑
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 2. Main Chat Thread */}
      <div className="chat-main">
        {['downloading', 'starting', 'pulling'].includes(ollamaStatus) && (
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'var(--color-surface)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10,
            padding: '24px',
            textAlign: 'center'
          }}>
            <div className="loading-spinner-small" style={{ width: '40px', height: '40px', border: '3px solid var(--color-border)', borderTopColor: 'var(--color-brand-600)', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: '16px' }} />
            <h4 style={{ margin: '0 0 8px 0', fontSize: '14px', fontWeight: 600, color: 'var(--color-brand-900)' }}>
              {ollamaStatus === 'downloading' && 'Downloading Local Ollama Sidecar...'}
              {ollamaStatus === 'starting' && 'Starting Local Ollama Server...'}
              {ollamaStatus === 'pulling' && 'Downloading Grounded Qwen Model...'}
            </h4>
            <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: 'var(--color-text-500)', maxWidth: '320px', lineHeight: 1.4 }}>
              {ollamaStatus === 'pulling' 
                ? 'This download is ~2GB and only occurs once. Thank you for your patience!'
                : 'Edeon is setting up a fully self-contained local AI assistant inside WSL.'}
            </p>
            <div style={{ width: '200px', height: '6px', background: 'var(--color-border)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${ollamaProgress}%`, background: 'var(--color-brand-600)', transition: 'width 0.2s ease' }} />
            </div>
            <span style={{ fontSize: '11px', color: 'var(--color-text-600)', marginTop: '8px', fontWeight: 600 }}>{ollamaProgress}%</span>
          </div>
        )}
        <div className="chat-header">
          <h3>
            {activeConversation ? activeConversation.title : 'AI Research Assistant'}
          </h3>
          <div className="reindex-panel">
            {reindexing && <span style={{ fontSize: '11px', color: 'var(--color-text-600)' }}>Embedding Knowledge Hub...</span>}
            {reindexSuccess && <span style={{ fontSize: '11px', color: 'var(--color-brand-600)' }}>✓ Index updated</span>}
            {reindexError && <span style={{ fontSize: '11px', color: 'var(--color-red-700)' }}>⚠ Reindex failed: {reindexError.slice(0, 30)}</span>}
            <button
              type="button"
              className="reindex-btn"
              disabled={reindexing}
              onClick={() => reindexKnowledgeHub(false)}
            >
              {reindexing ? 'Reindexing...' : 'Sync Index'}
            </button>
          </div>
        </div>

        {chatError && (
          <div className="chat-warning-card">
            <strong>Warning:</strong> {chatError}
          </div>
        )}

        <div className="chat-messages">
          {!activeConversation || activeConversation.messages.length === 0 ? (
            <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center' }}>
              <EmptyState
                icon={<Bot size={20} />}
                title="AI Research Assistant"
                description="Ask questions about system rules, Tice pesticide thresholds, or reference models. Answers are grounded exclusively in Edeon's local documentation."
                primaryAction={{
                  label: "What is the Persistence (DT50) of Imidacloprid?",
                  onClick: () => {
                    setInputVal("What is the Persistence (DT50) of Imidacloprid?");
                  }
                }}
                secondaryAction={{
                  label: "Explain Briggs Rules",
                  onClick: () => {
                    setInputVal("Explain Briggs Rules for pesticide systemicity");
                  }
                }}
              />
            </div>
          ) : (
            activeConversation.messages.map((m) => (
              <div key={m.message_id} className={`message-bubble ${m.role}`}>
                {m.role === 'assistant' ? (
                  renderMessageContent(m.content, m.citations)
                ) : (
                  <span>{m.content}</span>
                )}
                <div className="message-footer">
                  <span>
                    {m.role === 'assistant'
                      ? (m.tokens_used as any)?.model || (m.tokens_used?.cost_usd === 0 ? 'Local LLM' : 'Claude')
                      : 'User'}
                  </span>
                  {m.role === 'assistant' && m.tokens_used?.cost_usd !== undefined && (
                    <span>Cost: ${m.tokens_used.cost_usd.toFixed(5)}</span>
                  )}
                </div>
              </div>
            ))
          )}
          {chatLoading && (
            <div className="message-bubble assistant">
              <span className="loading-dots">
                Thinking and fetching citations<span>.</span><span>.</span><span>.</span>
              </span>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="chat-input-area">
          <form onSubmit={handleSend} className="chat-form">
            <textarea
              className="chat-textarea"
              placeholder="Ask a question grounded in the Knowledge Hub (e.g., 'What is the Tice threshold for herbicides?')..."
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              onKeyDown={handleKeyPress}
              disabled={chatLoading}
            />
            <button
              type="submit"
              className="send-chat-btn"
              disabled={chatLoading || !inputVal.trim()}
            >
              Send
            </button>
          </form>
          <div className="chat-status-bar">
            <span>💡 Press Enter to send, Shift+Enter for new line.</span>
            {activeConversation?.messages && activeConversation.messages.length > 0 && (
              <span>
                Total cost (conv): $
                {activeConversation.messages
                  .reduce((acc, curr) => acc + (curr.tokens_used?.cost_usd || 0), 0)
                  .toFixed(5)}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 3. Citations Slide Drawer (Optional, expands if citation is selected) */}
      {selectedCitation && (
        <div className="chat-drawer">
          <div className="drawer-header">
            <h4>Citation Details</h4>
            <button
              type="button"
              className="close-drawer-btn"
              onClick={() => setSelectedCitation(null)}
            >
              ×
            </button>
          </div>
          <div className="drawer-content">
            <div className="drawer-source-meta">
              <div><strong>Label:</strong> {selectedCitation.label}</div>
              <div style={{ marginTop: '4px' }}><strong>Source ID:</strong> {selectedCitation.entity_id}</div>
              <div style={{ marginTop: '4px' }}><strong>Type:</strong> <span style={{ textTransform: 'capitalize' }}>{selectedCitation.entity_type.replace('_', ' ')}</span></div>
              {selectedCitation.source_url && (
                <div style={{ marginTop: '4px', fontSize: '10px', color: 'var(--color-text-400)' }}>
                  <strong>Path:</strong> {selectedCitation.source_url}
                </div>
              )}
            </div>
            <div>
              <div style={{ fontWeight: 600, marginBottom: '6px' }}>Ground-Truth Chunk:</div>
              <div className="drawer-source-text">
                {selectedCitation.text}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
