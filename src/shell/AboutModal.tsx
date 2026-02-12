import React, { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useUIStore } from '../store/uiStore';
import styles from './AboutModal.module.css';

interface DeployedModelInfo {
  endpoint: string;
  model_version: string;
  training_date: string;
  verified: boolean;
  n_training_compounds: number;
  references: string[];
}

interface LicenseEntry {
  name: string;
  license: string;
  url?: string;
}

interface SystemInfo {
  app_version: string;
  build_commit: string;
  build_date: string;
  platform: string;
  python_version: string;
  deployed_models: DeployedModelInfo[];
  external_integrations: Record<string, string | null>;
  citation_block: string;
  licenses: LicenseEntry[];
}

export const AboutModal: React.FC = () => {
  const showAboutModal = useUIStore((state) => state.showAboutModal);
  const setShowAboutModal = useUIStore((state) => state.setShowAboutModal);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [copyStatus, setCopyStatus] = useState<string>('Copy Citation');

  useEffect(() => {
    if (!showAboutModal) return;

    // Fetch system info when modal opens
    invoke<SystemInfo>('app_meta_get_system_info')
      .then((info) => {
        setSystemInfo(info);
      })
      .catch((err) => {
        console.error('Failed to load system info:', err);
      });
  }, [showAboutModal]);

  const handleCopyCitation = async (format: 'plain' | 'bibtex' | 'ris' | 'markdown') => {
    try {
      const res = await invoke<string>('citation_generate', {
        citationTarget: 'edeon_app',
        targetMetadata: {},
        outputFormat: format,
      });

      await navigator.clipboard.writeText(res);
      setCopyStatus(`Copied ${format.toUpperCase()}!`);
      setTimeout(() => {
        setCopyStatus('Copy Citation');
      }, 2000);
    } catch (e) {
      console.error('Failed to generate or copy citation:', e);
    }
  };

  if (!showAboutModal) return null;

  return (
    <div className={styles.overlay} onClick={() => setShowAboutModal(false)}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <button className={styles.closeButton} onClick={() => setShowAboutModal(false)}>
          ✕
        </button>

        <div className={styles.header}>
          <h2 className={styles.title}>Edeon</h2>
          <p className={styles.subtitle}>Desktop Agchem Optimization Platform</p>
        </div>

        {systemInfo ? (
          <>
            {/* Build Info */}
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>Application Build Info</h3>
              <table className={styles.table}>
                <tbody>
                  <tr>
                    <td>Version</td>
                    <td>{systemInfo.app_version}</td>
                  </tr>
                  <tr>
                    <td>Platform</td>
                    <td>{systemInfo.platform}</td>
                  </tr>
                  <tr>
                    <td>Build Commit</td>
                    <td><code>{systemInfo.build_commit}</code></td>
                  </tr>
                  <tr>
                    <td>Build Date</td>
                    <td>{new Date(systemInfo.build_date).toLocaleDateString()}</td>
                  </tr>
                  <tr>
                    <td>Python Sidecar</td>
                    <td>{systemInfo.python_version}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Deployed Models */}
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>Deployed Prediction Models (Tier-1)</h3>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Endpoint</th>
                    <th>Version</th>
                    <th>Compounds</th>
                    <th>Verification</th>
                  </tr>
                </thead>
                <tbody>
                  {systemInfo.deployed_models.map((model) => (
                    <tr key={model.endpoint}>
                      <td>{model.endpoint}</td>
                      <td>{model.model_version}</td>
                      <td>{model.n_training_compounds}</td>
                      <td>{model.verified ? '🟢 Verified' : '🟡 Pending'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* External Integrations */}
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>Core Integrations</h3>
              <table className={styles.table}>
                <tbody>
                  {Object.entries(systemInfo.external_integrations).map(([name, version]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{version || 'Not connected'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Citation Block */}
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>Citation Reference</h3>
              <div className={styles.citationBlock}>
                {systemInfo.citation_block}
              </div>
              <div className={styles.citationActions}>
                <button
                  className={`${styles.btn} ${styles.btnPrimary}`}
                  onClick={() => handleCopyCitation('plain')}
                >
                  {copyStatus}
                </button>
                <button className={styles.btn} onClick={() => handleCopyCitation('bibtex')}>
                  Copy BibTeX
                </button>
                <button className={styles.btn} onClick={() => handleCopyCitation('ris')}>
                  Copy RIS
                </button>
                <button className={styles.btn} onClick={() => handleCopyCitation('markdown')}>
                  Copy Markdown
                </button>
              </div>
            </div>

            {/* Third-Party Licenses */}
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>Open Source Licenses</h3>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Component</th>
                    <th>License</th>
                  </tr>
                </thead>
                <tbody>
                  {systemInfo.licenses.map((lic) => (
                    <tr key={lic.name}>
                      <td>{lic.name}</td>
                      <td>{lic.license}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            Loading System and Model Metadata...
          </div>
        )}
      </div>
    </div>
  );
};
