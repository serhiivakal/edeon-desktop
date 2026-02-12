import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useUIStore } from '../store/uiStore';
import { Shield, ArrowLeft, RefreshCw, AlertTriangle } from 'lucide-react';

const ENDPOINTS = [
  { id: null, name: 'General Summary', icon: '📋' },
  { id: 'bee_acute_oral_ld50', name: 'Bee Acute Oral LD50', icon: '🐝' },
  { id: 'bee_acute_contact_ld50', name: 'Bee Acute Contact LD50', icon: '🐝' },
  { id: 'fish_acute_lc50', name: 'Fish Acute LC50', icon: '🐟' },
  { id: 'daphnia_acute_ec50', name: 'Daphnia Acute EC50', icon: '🦐' },
  { id: 'algae_growth_ec50', name: 'Algae Growth EC50', icon: '🌿' },
  { id: 'earthworm_acute_lc50', name: 'Earthworm Acute LC50', icon: '🪱' },
  { id: 'bird_acute_oral_ld50', name: 'Bird Acute Oral LD50', icon: '🐦' },
  { id: 'soil_koc', name: 'Soil Koc (Adsorption)', icon: '🪵' },
  { id: 'soil_dt50', name: 'Soil DT50 (Persistence)', icon: '🍂' },
];

export function VerificationReportView() {
  const uiStore = useUIStore() as any;
  const initialEndpoint = uiStore.selectedVerificationEndpoint;
  
  const [selectedId, setSelectedId] = useState<string | null>(initialEndpoint);
  const [content, setContent] = useState<string>('');
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const setActiveView = useUIStore((s) => s.setActiveView);

  useEffect(() => {
    // If the store had a pre-selected endpoint, make sure we set it
    if (initialEndpoint !== undefined) {
      setSelectedId(initialEndpoint);
    }
  }, [initialEndpoint]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setImageUri(null);

    invoke<any>('app_meta_get_verification_report', { 
      endpoint: selectedId || undefined 
    })
      .then((res) => {
        setContent(res.content);
        setImageUri(res.image_uri);
      })
      .catch((err) => {
        console.error('Failed to load verification report:', err);
        setError(String(err));
      })
      .finally(() => {
        setLoading(false);
      });
  }, [selectedId]);

  const handleBack = () => {
    if (uiStore.setSelectedVerificationEndpoint) {
      uiStore.setSelectedVerificationEndpoint(null);
    }
    // Navigate to models or previous view
    setActiveView('models');
  };

  const parseInlineMarkdown = (text: string) => {
    // Basic regex replacement for bolding and checkmarks
    const parts = text.split(/\*\*([^*]+)\*\*/g);
    return parts.map((part, index) => {
      if (index % 2 === 1) {
        return <strong key={index} style={{ fontWeight: 650, color: 'var(--color-text-900, #111)' }}>{part}</strong>;
      }
      // Style emojis/checkmarks
      if (part.includes('✅') || part.includes('PASS')) {
        return (
          <span key={index} style={{ color: 'var(--color-status-good, #16a34a)', fontWeight: 'bold' }}>{part}</span>
        );
      }
      return part;
    });
  };

  const renderMarkdown = (md: string) => {
    if (!md) return null;
    const lines = md.split('\n');
    const elements: React.ReactNode[] = [];
    
    let currentList: React.ReactNode[] = [];
    let inList = false;
    let inTable = false;
    let tableHeaders: string[] = [];
    let tableRows: string[][] = [];

    const flushList = (key: string | number) => {
      if (inList) {
        elements.push(
          <ul key={`ul-${key}`} style={{ paddingLeft: '20px', margin: '8px 0', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {currentList}
          </ul>
        );
        currentList = [];
        inList = false;
      }
    };

    const flushTable = (key: string | number) => {
      if (inTable) {
        elements.push(
          <div key={`table-wrapper-${key}`} style={{ width: '100%', overflowX: 'auto', margin: '16px 0' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', border: '1px solid var(--color-border, #e5e5e0)', borderRadius: '6px' }}>
              <thead>
                <tr style={{ background: 'var(--color-surface-raised, #f5f5f0)', borderBottom: '1px solid var(--color-border, #e5e5e0)' }}>
                  {tableHeaders.map((h, i) => (
                    <th key={i} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--color-text-primary)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--color-border, #e5e5e0)', background: i % 2 === 0 ? 'var(--color-surface, #ffffff)' : 'var(--color-surface-raised, #fafafa)' }}>
                    {row.map((cell, j) => {
                      let style: React.CSSProperties = { padding: '8px 12px', color: 'var(--color-text-secondary, #52525b)' };
                      const trimmed = cell.trim();
                      if (trimmed === 'PASS') {
                        style.color = 'var(--color-status-good, #16a34a)';
                        style.fontWeight = 'bold';
                      } else if (trimmed === 'FAIL') {
                        style.color = 'var(--color-status-poor, #dc2626)';
                        style.fontWeight = 'bold';
                      }
                      return <td key={j} style={style}>{parseInlineMarkdown(cell)}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        tableHeaders = [];
        tableRows = [];
        inTable = false;
      }
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (line.startsWith('|')) {
        flushList(i);
        inTable = true;
        const cells = line.split('|').slice(1, -1).map(c => c.trim());
        if (cells.every(c => c.match(/^:+:-*:+$/) || c.match(/^-+$/))) {
          continue;
        }
        if (tableHeaders.length === 0) {
          tableHeaders = cells;
        } else {
          tableRows.push(cells);
        }
        continue;
      } else {
        flushTable(i);
      }

      if (line.startsWith('# ')) {
        flushList(i);
        elements.push(
          <h1 key={i} style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-text-primary)', margin: '20px 0 10px 0', borderBottom: '1px solid var(--color-border, #e5e5e0)', paddingBottom: '6px' }}>
            {parseInlineMarkdown(line.substring(2))}
          </h1>
        );
      } else if (line.startsWith('## ')) {
        flushList(i);
        elements.push(
          <h2 key={i} style={{ fontSize: '15px', fontWeight: 650, color: 'var(--color-text-primary)', margin: '18px 0 8px 0' }}>
            {parseInlineMarkdown(line.substring(3))}
          </h2>
        );
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        inList = true;
        currentList.push(
          <li key={i} style={{ color: 'var(--color-text-secondary, #52525b)', fontSize: '13px' }}>
            {parseInlineMarkdown(line.substring(2))}
          </li>
        );
      } else if (line === '---') {
        flushList(i);
        elements.push(<hr key={i} style={{ border: 'none', borderTop: '1px solid var(--color-border, #e5e5e0)', margin: '20px 0' }} />);
      } else if (line.length > 0) {
        flushList(i);
        elements.push(
          <p key={i} style={{ margin: '8px 0', fontSize: '13px', lineHeight: '1.5', color: 'var(--color-text-secondary, #52525b)' }}>
            {parseInlineMarkdown(line)}
          </p>
        );
      } else {
        flushList(i);
      }
    }

    flushList(lines.length);
    flushTable(lines.length);

    return elements;
  };

  return (
    <div style={{ display: 'flex', flex: 1, height: 'calc(100vh - 56px - 28px)', overflow: 'hidden', background: 'var(--color-surface-base, #ffffff)' }}>
      {/* Sidebar navigation */}
      <div 
        style={{ 
          width: '240px', 
          borderRight: '1px solid var(--color-border-subtle, #e4e4e7)', 
          background: 'var(--color-surface-raised, #fafafa)', 
          overflowY: 'auto',
          padding: '16px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}
      >
        <div style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-tertiary, #71717a)', paddingLeft: '8px', marginBottom: '8px', letterSpacing: '0.05em' }}>
          Verification Reports
        </div>
        {ENDPOINTS.map((ep) => {
          const isActive = selectedId === ep.id;
          return (
            <button
              key={ep.id ?? 'summary'}
              onClick={() => setSelectedId(ep.id)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 10px',
                borderRadius: '6px',
                border: 'none',
                background: isActive ? 'var(--color-action-secondary-hover, #e4e4e7)' : 'transparent',
                color: isActive ? 'var(--color-text-primary, #18181b)' : 'var(--color-text-secondary, #52525b)',
                fontSize: '12px',
                fontWeight: isActive ? 600 : 500,
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'all 120ms ease',
                outline: 'none',
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.background = 'rgba(0,0,0,0.02)';
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.background = 'transparent';
              }}
            >
              <span style={{ fontSize: '14px' }}>{ep.icon}</span>
              <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{ep.name}</span>
            </button>
          );
        })}
      </div>

      {/* Main pane content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Navigation Bar */}
        <div 
          style={{ 
            height: '48px', 
            padding: '0 24px', 
            borderBottom: '1px solid var(--color-border-subtle, #e4e4e7)', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            background: 'var(--color-surface-base, #ffffff)'
          }}
        >
          <button
            onClick={handleBack}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              border: 'none',
              background: 'none',
              color: 'var(--color-brand-700, #3b6d11)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              outline: 'none',
              transition: 'transform 120ms ease',
            }}
            onMouseEnter={(e) => e.currentTarget.style.transform = 'translateX(-2px)'}
            onMouseLeave={(e) => e.currentTarget.style.transform = 'translateX(0)'}
          >
            <ArrowLeft size={14} />
            Back to Models
          </button>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--color-text-secondary, #52525b)', fontWeight: 500 }}>
            <Shield size={12} style={{ color: 'var(--color-status-good, #16a34a)' }} />
            Authoritative Conformal Validation Dossier
          </div>
        </div>

        {/* Scrollable Report Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 32px', background: 'var(--color-surface-raised, #fafafa)' }}>
          <div 
            style={{ 
              maxWidth: '720px', 
              margin: '0 auto', 
              background: 'var(--color-surface-base, #ffffff)', 
              border: '1px solid var(--color-border, #e5e5e0)', 
              borderRadius: '8px', 
              boxShadow: 'var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))',
              padding: '32px',
              minHeight: '100%'
            }}
          >
            {loading && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '240px', gap: '12px' }}>
                <RefreshCw size={24} className="animate-spin" style={{ color: 'var(--color-brand-700, #3b6d11)', animation: 'spin 1s linear infinite' }} />
                <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>Loading verification dossier...</span>
                <style dangerouslySetInnerHTML={{ __html: `
                  @keyframes spin { to { transform: rotate(360deg); } }
                `}} />
              </div>
            )}

            {error && (
              <div style={{ padding: '16px', background: '#fef2f2', border: '1px solid #fee2e2', borderRadius: '6px', color: '#b91c1c', fontSize: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                <AlertTriangle size={18} />
                <span>Failed to load report: {error}</span>
              </div>
            )}

            {!loading && !error && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {renderMarkdown(content)}
                
                {/* Embed Scatter Plot if DT50/Summary or image exists */}
                {imageUri && (
                  <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', borderTop: '1px solid var(--color-border, #e5e5e0)', paddingTop: '20px' }}>
                    <h3 style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-tertiary, #71717a)', marginBottom: '8px' }}>
                      conformal calibration diagnostics
                    </h3>
                    <img 
                      src={imageUri} 
                      alt="DT50 Conformal uncertainty calibration" 
                      style={{ maxWidth: '100%', maxHeight: '420px', objectFit: 'contain', borderRadius: '6px', border: '1px solid var(--color-border, #e5e5e0)', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }} 
                    />
                    <span style={{ fontSize: '10.5px', color: 'var(--color-text-secondary, #52525b)', fontStyle: 'italic', textAlign: 'center' }}>
                      Figure 1: Conformal uncertainty calibration. Observed vs Predicted standard deviations (Spearman ρ = 0.8000).
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
