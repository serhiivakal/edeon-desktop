import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { ShieldAlert, CheckCircle2 } from 'lucide-react';

export function TierPreferenceSelector() {
  const [endpoints, setEndpoints] = useState<string[]>([]);
  const [preferences, setPreferences] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [savingStatus, setSavingStatus] = useState<string | null>(null);

  // Endpoint name prettifier
  const formatEndpointName = (name: string): string => {
    const maps: Record<string, string> = {
      bee_acute_oral_ld50: 'Honeybee Acute Oral Toxicity (LD50)',
      bee_acute_contact_ld50: 'Honeybee Acute Contact Toxicity (LD50)',
      fish_acute_lc50: 'Fish Acute Toxicity (LC50)',
      daphnia_acute_ec50: 'Daphnia Acute Selectivity (EC50)',
      algae_growth_ec50: 'Algae Growth Inhibition (EC50)',
      earthworm_acute_lc50: 'Earthworm Acute Selectivity (LC50)',
      bird_acute_oral_ld50: 'Avian Acute Oral Toxicity (LD50)',
      rat_acute_oral_ld50: 'Mammalian (Rat) Acute Oral LD50',
      skin_sensitization: 'Dermal Sensitization Potential',
      eye_irritation: 'Ocular Irritation Category',
      soil_koc: 'Soil Organic Carbon Partition (Koc)',
      soil_dt50: 'Soil Half-Life Persistence (DT50)',
      gus_index: 'Groundwater Ubiquity Score (GUS)',
      bcf: 'Bioconcentration Factor (BCF)',
      photostability_class: 'Photostability Classification',
      pesticide_likeness_tice: 'Pesticide Likeness Index (Tice)',
    };
    return maps[name] || name.replace(/_/g, ' ').toUpperCase();
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        // 1. Fetch all canonical endpoints
        const list = await invoke<string[]>('model_list_endpoints');
        setEndpoints(list || []);

        // 2. Fetch preferences for each endpoint
        const prefs: Record<string, number> = {};
        for (const ep of list) {
          const pref = await invoke<number | null>('model_get_preference', { endpoint: ep });
          prefs[ep] = pref ?? 0; // 0 represents "Auto"
        }
        setPreferences(prefs);
      } catch (err) {
        console.error('Failed to load tier preferences:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const handlePreferenceChange = async (endpoint: string, tier: number) => {
    try {
      setSavingStatus(`Saving ${endpoint}...`);
      await invoke('model_set_preference', { endpoint, tier });
      setPreferences((prev) => ({
        ...prev,
        [endpoint]: tier,
      }));
      setSavingStatus('Preferences saved successfully!');
      setTimeout(() => setSavingStatus(null), 1500);
    } catch (err) {
      console.error('Failed to save tier preference:', err);
      setSavingStatus('Error saving preference!');
      setTimeout(() => setSavingStatus(null), 2000);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '16px', color: 'var(--color-text-400)' }}>
        <div style={spinnerStyle} />
        <span style={{ fontSize: '11px', fontWeight: 500 }}>Loading Tier Mappings...</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'between', alignItems: 'center', marginBottom: '4px' }}>
        <div>
          <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '2px' }}>
            Data Tier Mappings & Preferences
          </h3>
          <p style={{ fontSize: '11px', color: 'var(--color-text-400)' }}>
            Force predictions to pin a specific analytical tier (Reference, Screening, External, or Custom) or use Auto to resolve dynamically.
          </p>
        </div>
        {savingStatus && (
          <span style={{
            fontSize: '9px',
            fontWeight: 600,
            background: savingStatus.includes('Error') ? 'var(--color-red-100)' : 'var(--color-brand-100)',
            color: savingStatus.includes('Error') ? 'var(--color-red-700)' : 'var(--color-brand-700)',
            padding: '2px 8px',
            borderRadius: '4px',
            border: `0.5px solid ${savingStatus.includes('Error') ? 'var(--color-red-500)' : 'var(--color-brand-600)'}`,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            height: '20px',
            whiteSpace: 'nowrap'
          }}>
            {savingStatus.includes('Error') ? <ShieldAlert size={10} /> : <CheckCircle2 size={10} />}
            {savingStatus}
          </span>
        )}
      </div>

      {/* Grid List of Endpoints */}
      <div style={gridStyle}>
        {endpoints.map((ep) => (
          <div key={ep} style={itemCardStyle}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1, minWidth: 0 }}>
              <span style={endpointTitleStyle} title={ep}>
                {formatEndpointName(ep)}
              </span>
              <span style={endpointIdStyle}>
                endpoint: {ep}
              </span>
            </div>

            <select
              value={preferences[ep] ?? 0}
              onChange={(e) => handlePreferenceChange(ep, parseInt(e.target.value))}
              style={selectStyle(preferences[ep] ?? 0)}
            >
              <option value="0">Auto (Default)</option>
              <option value="1">Tier 1: Reference</option>
              <option value="2">Tier 2: Screening</option>
              <option value="3">Tier 3: External</option>
              <option value="4">Tier 4: Custom Studio</option>
            </select>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Component Internal Styles ──────────────────────────────────────

const spinnerStyle: React.CSSProperties = {
  width: '14px',
  height: '14px',
  border: '1.5px solid var(--color-border)',
  borderTopColor: 'var(--color-brand-600)',
  borderRadius: '50%',
  animation: 'spinTierPrefSelector 1s linear infinite'
};

const gridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
  gap: '10px',
};

const itemCardStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '12px',
  padding: '10px 12px',
  background: 'var(--color-bg)',
  border: '0.5px solid var(--color-border)',
  borderRadius: '8px',
  transition: 'border-color 150ms ease'
};

const endpointTitleStyle: React.CSSProperties = {
  fontSize: '11px',
  fontWeight: 600,
  color: 'var(--color-text-900)',
  textOverflow: 'ellipsis',
  overflow: 'hidden',
  whiteSpace: 'nowrap',
};

const endpointIdStyle: React.CSSProperties = {
  fontSize: '9px',
  color: 'var(--color-text-400)',
  fontFamily: 'var(--font-mono, monospace)'
};

const selectStyle = (tier: number): React.CSSProperties => {
  const getColors = () => {
    switch (tier) {
      case 1: // Reference - Green
        return {
          bg: 'var(--color-brand-100, #eaf3de)',
          color: 'var(--color-brand-700, #2d5016)',
          border: 'rgba(45, 80, 22, 0.3)'
        };
      case 2: // Screening - Yellow/Amber
        return {
          bg: 'var(--color-amber-100, #faeeda)',
          color: 'var(--color-amber-700, #854f0b)',
          border: 'rgba(133, 79, 11, 0.3)'
        };
      case 3: // External - Blue
        return {
          bg: 'var(--color-blue-100, #e6f1fb)',
          color: 'var(--color-blue-700, #0c447c)',
          border: 'rgba(12, 68, 124, 0.3)'
        };
      case 4: // Custom - Purple
        return {
          bg: '#f3e8ff',
          color: '#6b21a8',
          border: 'rgba(107, 33, 168, 0.3)'
        };
      case 0:
      default:
        return {
          bg: 'var(--color-surface, #ffffff)',
          color: 'var(--color-text-600, #5a5a5a)',
          border: 'var(--color-border, #e5e5e0)'
        };
    }
  };

  const colors = getColors();

  return {
    height: '24px',
    padding: '0 6px',
    borderRadius: '6px',
    border: `0.5px solid ${colors.border}`,
    background: colors.bg,
    color: colors.color,
    fontSize: '9px',
    fontWeight: 600,
    outline: 'none',
    cursor: 'pointer',
    transition: 'all 120ms ease',
    width: '120px'
  };
};
