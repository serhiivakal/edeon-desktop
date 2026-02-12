import { useState, useMemo } from 'react';
import { useUIStore } from '../store/uiStore';
import { X, Search } from 'lucide-react';
import shortcutsData from '../content/help/shortcuts.json';

export function KeyboardShortcutsOverlay() {
  const show = useUIStore((s) => s.showShortcutsHelp);
  const setShow = useUIStore((s) => s.setShowShortcutsHelp);
  const [query, setQuery] = useState('');

  const filteredShortcuts = useMemo(() => {
    if (!query.trim()) return shortcutsData;

    const lowerQuery = query.toLowerCase();
    const result: Record<string, Array<{ keys: string; description: string }>> = {};

    Object.entries(shortcutsData).forEach(([category, list]) => {
      const filtered = list.filter(
        (item) =>
          item.keys.toLowerCase().includes(lowerQuery) ||
          item.description.toLowerCase().includes(lowerQuery)
      );
      if (filtered.length > 0) {
        result[category] = filtered;
      }
    });

    return result;
  }, [query]);

  if (!show) return null;

  return (
    <div
      onClick={() => setShow(false)}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999, // --z-modal overlay level
        padding: '20px',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '700px',
          background: 'var(--color-surface, #ffffff)',
          border: '1px solid var(--color-border, #e5e5e0)',
          borderRadius: '12px',
          boxShadow: 'var(--shadow-overlay, 0 25px 50px -12px rgba(0, 0, 0, 0.25))',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '80vh',
          overflow: 'hidden',
          animation: 'shortcutsModalFadeIn 150ms ease-out',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--color-border, #e5e5e0)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '18px' }}>⌨</span>
            <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-text-900, #1a1a1a)' }}>
              Keyboard Shortcuts Cheat-Sheet
            </span>
          </div>

          <button
            onClick={() => setShow(false)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--color-text-400, #a0a0a0)',
              cursor: 'pointer',
              padding: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              outline: 'none',
              transition: 'color 120ms ease',
            }}
            onMouseEnter={(e) => e.currentTarget.style.color = 'var(--color-text-700, #3f3f46)'}
            onMouseLeave={(e) => e.currentTarget.style.color = 'var(--color-text-400, #a0a0a0)'}
          >
            <X size={16} />
          </button>
        </div>

        {/* Search Filter Bar */}
        <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--color-border-subtle, #f0f0f0)', background: 'var(--color-bg, #fcfcf9)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Search size={14} style={{ color: 'var(--color-text-tertiary, #a1a1aa)' }} />
          <input
            type="text"
            placeholder="Search shortcuts..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              flex: 1,
              border: 'none',
              background: 'transparent',
              fontSize: '12px',
              color: 'var(--color-text-primary, #18181b)',
              outline: 'none',
            }}
            autoFocus
          />
        </div>

        {/* Categories Grid Content */}
        <div style={{ padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {Object.keys(filteredShortcuts).length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', fontSize: '12px', color: 'var(--color-text-tertiary, #a1a1aa)' }}>
              No matching shortcuts found.
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px 24px' }}>
              {Object.entries(filteredShortcuts).map(([category, list]) => (
                <div key={category} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <h4
                    style={{
                      fontSize: '10px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      color: 'var(--color-text-tertiary, #71717a)',
                      borderBottom: '1px solid var(--color-border-subtle, #e4e4e7)',
                      paddingBottom: '4px',
                      margin: 0,
                      letterSpacing: '0.04em',
                    }}
                  >
                    {category}
                  </h4>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {list.map((item, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '12px',
                          fontSize: '11.5px',
                        }}
                      >
                        <span style={{ color: 'var(--color-text-secondary, #52525b)', fontWeight: 500 }}>
                          {item.description}
                        </span>
                        
                        <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
                          {item.keys.split(' / ').map((keyGroup, kIdx) => (
                            <span key={kIdx} style={{ display: 'flex', alignItems: 'center' }}>
                              {kIdx > 0 && <span style={{ fontSize: '9px', color: 'var(--color-text-tertiary, #a1a1aa)', margin: '0 4px' }}>or</span>}
                              <kbd
                                style={{
                                  background: 'var(--color-surface-raised, #fafafa)',
                                  border: '1.5px solid var(--color-border-default, #d4d4d8)',
                                  borderBottomWidth: '2.5px',
                                  borderRadius: '4px',
                                  padding: '1px 5px',
                                  fontFamily: 'var(--font-family-mono, monospace)',
                                  fontSize: '9.5px',
                                  fontWeight: 600,
                                  color: 'var(--color-text-primary, #18181b)',
                                  boxShadow: '0 1px 0 rgba(0,0,0,0.05)',
                                }}
                              >
                                {keyGroup}
                              </kbd>
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes shortcutsModalFadeIn {
          from { opacity: 0; transform: scale(0.97); }
          to { opacity: 1; transform: scale(1); }
        }
      ` }} />
    </div>
  );
}
