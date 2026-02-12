import { useState, useRef, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Quote, FileText, Check, Copy } from 'lucide-react';

export interface CitationExportButtonProps {
  target: 'edeon_app' | 'prediction' | 'workflow' | 'report';
  metadata: Record<string, any>;
  variant?: 'button' | 'icon';
}

export function CitationExportButton({ target, metadata, variant = 'button' }: CitationExportButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copiedFormat, setCopiedFormat] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const handleExport = async (format: 'plain' | 'bibtex' | 'ris' | 'markdown') => {
    setLoading(true);
    try {
      const citation = await invoke<string>('citation_generate', {
        citationTarget: target,
        targetMetadata: metadata,
        outputFormat: format,
      });

      await navigator.clipboard.writeText(citation);
      setCopiedFormat(format);
      setTimeout(() => setCopiedFormat(null), 2000);
    } catch (err) {
      console.error('Failed to export citation:', err);
      alert('Failed to generate citation: ' + String(err));
    } finally {
      setLoading(false);
      setIsOpen(false);
    }
  };

  return (
    <div ref={dropdownRef} style={{ position: 'relative', display: 'inline-block' }}>
      {variant === 'icon' ? (
        <button
          onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
          style={{
            background: 'none',
            border: 'none',
            padding: '2px',
            color: 'var(--color-text-secondary, #52525b)',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            outline: 'none',
            transition: 'color 120ms ease',
          }}
          title="Export citation"
        >
          <Quote size={11} />
        </button>
      ) : (
        <button
          onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            borderRadius: '6px',
            border: '1px solid var(--color-border-default, #d4d4d8)',
            background: 'var(--color-surface, #ffffff)',
            color: 'var(--color-text-secondary, #52525b)',
            fontSize: '11px',
            fontWeight: 600,
            cursor: 'pointer',
            outline: 'none',
            transition: 'all 120ms ease',
          }}
        >
          <Quote size={12} />
          {copiedFormat ? 'Citation Copied!' : 'Cite work'}
        </button>
      )}

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 4px)',
            right: 0,
            width: '160px',
            background: 'var(--color-surface, #ffffff)',
            border: '1px solid var(--color-border, #e5e5e0)',
            borderRadius: '8px',
            boxShadow: 'var(--shadow-md, 0 4px 6px -1px rgba(0,0,0,0.1))',
            padding: '4px',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
          }}
        >
          {[
            { id: 'plain', label: 'Plain Text', icon: <FileText size={11} /> },
            { id: 'bibtex', label: 'BibTeX (.bib)', icon: <Copy size={11} /> },
            { id: 'ris', label: 'EndNote / RIS', icon: <Copy size={11} /> },
            { id: 'markdown', label: 'Markdown', icon: <FileText size={11} /> },
          ].map((f) => (
            <button
              key={f.id}
              onClick={(e) => {
                e.stopPropagation();
                if (!loading) handleExport(f.id as any);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '8px',
                padding: '6px 10px',
                borderRadius: '6px',
                border: 'none',
                background: 'transparent',
                color: 'var(--color-text-secondary, #52525b)',
                fontSize: '11px',
                fontWeight: 500,
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'background 120ms ease',
                outline: 'none',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-action-secondary, #f4f4f5)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {f.icon}
                <span>{f.label}</span>
              </div>
              {copiedFormat === f.id && <Check size={11} style={{ color: 'var(--color-status-good, #16a34a)' }} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
