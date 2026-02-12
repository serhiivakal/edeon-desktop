import { useState } from 'react';
import { Shield, Check } from 'lucide-react';
import { useUIStore } from '../../store/uiStore';

export interface VerificationBadgeProps {
  endpoint: string;
  verified: boolean;
  variant?: 'compact' | 'expanded';
}

interface EndpointVerifyData {
  coverage: number;
  testSize: number;
  targetRange: string;
  taskKind: string;
  status: string;
}

const VERIFICATION_DATA: Record<string, EndpointVerifyData> = {
  bee_acute_oral_ld50: { coverage: 1.0000, testSize: 39, targetRange: '[0.90, 1.00]', taskKind: 'classification', status: 'PASS' },
  bee_acute_contact_ld50: { coverage: 0.9647, testSize: 85, targetRange: '[0.90, 0.98]', taskKind: 'classification', status: 'PASS' },
  fish_acute_lc50: { coverage: 0.9394, testSize: 66, targetRange: '[0.90, 0.97]', taskKind: 'classification', status: 'PASS' },
  daphnia_acute_ec50: { coverage: 1.0000, testSize: 38, targetRange: '[0.90, 1.00]', taskKind: 'regression', status: 'PASS' },
  algae_growth_ec50: { coverage: 0.9333, testSize: 15, targetRange: '[0.90, 0.97]', taskKind: 'classification', status: 'PASS' },
  earthworm_acute_lc50: { coverage: 1.0000, testSize: 1, targetRange: '[0.90, 1.00]', taskKind: 'regression', status: 'PASS' },
  bird_acute_oral_ld50: { coverage: 0.9865, testSize: 74, targetRange: '[0.85, 1.00]', taskKind: 'classification', status: 'PASS' },
  soil_koc: { coverage: 0.8738, testSize: 103, targetRange: '[0.85, 0.97]', taskKind: 'regression', status: 'PASS' },
  soil_dt50: { coverage: 0.8529, testSize: 34, targetRange: '[0.83, 0.98]', taskKind: 'regression_heteroscedastic', status: 'PASS' },
};

export function VerificationBadge({ endpoint, verified, variant = 'compact' }: VerificationBadgeProps) {
  const [hovered, setHovered] = useState(false);
  const setActiveView = useUIStore((s) => s.setActiveView);
  
  const uiStore = useUIStore() as any;

  if (!verified) return null;

  const data = VERIFICATION_DATA[endpoint];
  const isGus = endpoint === 'gus_index';

  const handleViewReport = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (uiStore.setSelectedVerificationEndpoint) {
      uiStore.setSelectedVerificationEndpoint(isGus ? 'soil_dt50' : endpoint);
    }
    setActiveView('verification_report');
  };

  const getTooltipContent = () => {
    if (isGus) {
      return (
        <>
          <div style={{ fontWeight: 700, marginBottom: '4px', color: '#ffffff' }}>Verified Composite Index</div>
          <p style={{ margin: '0 0 6px 0', fontSize: '9px', opacity: 0.9 }}>
            GUS Leaching Index is calculated directly from verified Soil Koc and Soil DT50 models.
          </p>
          <div style={{ borderTop: '0.5px solid rgba(255,255,255,0.15)', paddingTop: '6px', textAlign: 'center' }}>
            <span 
              onClick={handleViewReport}
              style={{ color: '#60a5fa', cursor: 'pointer', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '2px' }}
            >
              View Verification Reports →
            </span>
          </div>
        </>
      );
    }

    if (!data) {
      return (
        <>
          <div style={{ fontWeight: 700, marginBottom: '2px', color: '#ffffff' }}>Verified Model</div>
          <div style={{ fontStyle: 'italic', fontSize: '9px', opacity: 0.8 }}>Model outputs are validated.</div>
        </>
      );
    }

    return (
      <>
        <div style={{ fontWeight: 700, marginBottom: '4px', color: '#ffffff', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
          <Shield size={10} style={{ color: '#4ade80' }} /> Verified Tier-1 Model
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', margin: '4px 0 8px 0', textAlign: 'left', fontSize: '9.5px' }}>
          <div><strong>95% CI Coverage:</strong> {(data.coverage * 100).toFixed(1)}%</div>
          <div><strong>Held-out Test Set:</strong> {data.testSize} compounds</div>
          <div><strong>Target Bounds:</strong> {data.targetRange}</div>
          <div><strong>Status:</strong> <span style={{ color: '#4ade80', fontWeight: 700 }}>✅ PASSING</span></div>
        </div>
        <div style={{ borderTop: '0.5px solid rgba(255,255,255,0.15)', paddingTop: '6px', textAlign: 'center' }}>
          <span 
            onClick={handleViewReport}
            style={{ color: '#60a5fa', cursor: 'pointer', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '2px' }}
          >
            View Calibration Report →
          </span>
        </div>
      </>
    );
  };

  const badgeBg = 'var(--color-status-good-bg, rgba(74, 222, 128, 0.1))';
  const badgeColor = 'var(--color-status-good, #16a34a)';
  const badgeBorder = '0.5px solid var(--color-status-good, rgba(22, 163, 74, 0.4))';

  return (
    <div
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '4px',
          height: variant === 'compact' ? '20px' : '22px',
          padding: variant === 'compact' ? '0 6px' : '0 10px',
          borderRadius: '11px',
          fontSize: '9px',
          fontWeight: 600,
          background: badgeBg,
          color: badgeColor,
          border: badgeBorder,
          cursor: 'help',
          userSelect: 'none',
          transition: 'all 150ms ease-in-out',
          boxShadow: hovered ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
        }}
      >
        <Shield size={10} />
        {variant === 'expanded' ? 'Verified Tier-1' : 'Verified'}
        <Check size={8} style={{ strokeWidth: 3 }} />
      </span>

      {hovered && (
        <div
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 6px)',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '210px',
            padding: '10px 12px',
            background: '#18181b', // Slate-900 surface overlay
            border: '0.5px solid #3f3f46',
            color: '#e4e4e7', // zinc-200
            fontSize: '10px',
            lineHeight: '1.4',
            borderRadius: '8px',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -4px rgba(0, 0, 0, 0.3)',
            zIndex: 1000,
            pointerEvents: 'auto',
            textAlign: 'center',
            animation: 'fadeInVerifyBadge 150ms ease-out',
          }}
        >
          {getTooltipContent()}
          {/* Tooltip arrow */}
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              borderWidth: '5px',
              borderStyle: 'solid',
              borderColor: '#18181b transparent transparent transparent',
            }}
          />
        </div>
      )}
      
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes fadeInVerifyBadge {
          from { opacity: 0; transform: translate(-50%, 4px); }
          to { opacity: 1; transform: translate(-50%, 0); }
        }
      `}} />
    </div>
  );
}
