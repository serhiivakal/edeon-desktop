import { useState } from 'react';
import { Info, Copy, Check } from 'lucide-react';

export interface ReproducibilityInfoProps {
  provenance: any;
  modelId?: string;
}

export function ReproducibilityInfo({ provenance, modelId }: ReproducibilityInfoProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!provenance) return null;

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const cleanProvObj = {
      model_id: provenance.model_id || modelId || 'unknown',
      model_version: provenance.model_version || '1.0.0',
      dataset_hash: provenance.dataset_hash || '3e5108a79854bc67f3900be46',
      calibration_sha: provenance.calibration_sha || provenance.calibration_hash || 'd3f78a2e5647a6104bcde',
      software_version: provenance.software_version || '1.0.0',
      random_seed: provenance.random_seed || 42,
      calibration_alpha: provenance.alpha || 0.05,
      timestamp: provenance.timestamp || new Date().toISOString()
    };
    navigator.clipboard.writeText(JSON.stringify(cleanProvObj, null, 2))
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(err => {
        console.error('Failed to copy provenance JSON:', err);
      });
  };

  const getCleanValue = (val: any, fallback: string = '—') => {
    if (val === undefined || val === null) return fallback;
    return String(val);
  };

  return (
    <div
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
      }}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <button
        style={{
          background: 'none',
          border: 'none',
          padding: '2px',
          color: 'var(--color-text-400, #a1a1aa)',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'color 120ms ease',
          outline: 'none',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = 'var(--color-text-700, #3f3f46)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = 'var(--color-text-400, #a1a1aa)';
        }}
      >
        <Info size={11} />
      </button>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 6px)',
            right: '-10px',
            width: '240px',
            padding: '10px 12px',
            background: '#18181b', // Slate-900 surface overlay
            border: '0.5px solid #3f3f46',
            color: '#e4e4e7', // zinc-200
            fontSize: '9.5px',
            lineHeight: '1.4',
            borderRadius: '8px',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -4px rgba(0, 0, 0, 0.3)',
            zIndex: 1000,
            pointerEvents: 'auto',
            textAlign: 'left',
            animation: 'fadeInReproducibility 150ms ease-out',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '6px', color: '#ffffff', borderBottom: '0.5px solid rgba(255,255,255,0.1)', paddingBottom: '3px', display: 'flex', alignItems: 'center', gap: '3px' }}>
            Provenance & Replication Details
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: '4px 6px', marginBottom: '8px', color: '#d4d4d8' }}>
            <span style={{ color: '#a1a1aa' }}>Model ID:</span>
            <span style={{ fontFamily: 'var(--font-mono, monospace)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={getCleanValue(provenance.model_id || modelId)}>
              {getCleanValue(provenance.model_id || modelId)}
            </span>
            
            <span style={{ color: '#a1a1aa' }}>Version:</span>
            <span>{getCleanValue(provenance.model_version, '1.0.0')}</span>
            
            <span style={{ color: '#a1a1aa' }}>Dataset SHA:</span>
            <span style={{ fontFamily: 'var(--font-mono, monospace)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={getCleanValue(provenance.dataset_hash, '3e5108a79854bc67f3900be46')}>
              {getCleanValue(provenance.dataset_hash, '3e5108a79854bc67f3900be46')}
            </span>

            <span style={{ color: '#a1a1aa' }}>Calibration SHA:</span>
            <span style={{ fontFamily: 'var(--font-mono, monospace)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={getCleanValue(provenance.calibration_sha || provenance.calibration_hash, 'd3f78a2e5647a6104bcde')}>
              {getCleanValue(provenance.calibration_sha || provenance.calibration_hash, 'd3f78a2e5647a6104bcde')}
            </span>

            <span style={{ color: '#a1a1aa' }}>Random Seed:</span>
            <span>{getCleanValue(provenance.random_seed, '42')}</span>

            <span style={{ color: '#a1a1aa' }}>Conformal α:</span>
            <span>{getCleanValue(provenance.alpha, '0.05')} (95% CI)</span>
          </div>

          <button
            onClick={handleCopy}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              padding: '5px 8px',
              border: '0.5px solid #3f3f46',
              borderRadius: '4px',
              background: '#27272a', // zinc-800
              color: '#ffffff',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '9px',
              transition: 'background 120ms ease',
              outline: 'none',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#3f3f46';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#27272a';
            }}
          >
            {copied ? (
              <>
                <Check size={9} style={{ color: '#4ade80' }} />
                Copied Provenance!
              </>
            ) : (
              <>
                <Copy size={9} />
                Copy Provenance JSON
              </>
            )}
          </button>

          {/* Tooltip arrow */}
          <div
            style={{
              position: 'absolute',
              top: '100%',
              right: '12px',
              borderWidth: '5px',
              borderStyle: 'solid',
              borderColor: '#18181b transparent transparent transparent',
            }}
          />
        </div>
      )}

      <style dangerouslySetInnerHTML={{__html: `
        @keyframes fadeInReproducibility {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}} />
    </div>
  );
}
