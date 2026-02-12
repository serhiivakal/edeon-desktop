/* ==========================================================
   Edeon Desktop — Settings & Preferences View
   Comprehensive settings view with database-persisted preferences.
   ========================================================== */

import { useState, useEffect } from 'react';
import { useSettingsStore } from '../store/settingsStore';
import { useUIStore } from '../store/uiStore';
import { open } from '@tauri-apps/plugin-dialog';
import { ModelTierBadge } from '../components/models/ModelTierBadge';
import { ADWarning } from '../components/models/ADWarning';
import { PredictionDisplay } from '../components/models/PredictionDisplay';
import { Prediction } from '../types';
import { ModelCardViewer } from '../components/models/ModelCardViewer';
import { TierPreferenceSelector } from '../components/models/TierPreferenceSelector';

type SettingsTab = 'general' | 'preferences' | 'workflows' | 'engine' | 'about';

export function SettingsView() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [isRestarting, setIsRestarting] = useState(false);
  const [showRestartNotice, setShowRestartNotice] = useState(false);
  const [activeModelCardId, setActiveModelCardId] = useState<string | null>(null);

  const {
    theme,
    density,
    splitRatio,
    defaultAlgorithm,
    defaultDescriptorSet,
    databaseDir,
    pythonStatus,
    pythonInfo,
    setDensity,
    setSplitRatio,
    setDefaultAlgorithm,
    setDefaultDescriptorSet,
    setDatabaseDir,
    fetchPythonDiagnostics,
    restartPython,
    llmProvider,
    anthropicApiKey,
    anthropicModel,
    localLlmEndpoint,
    localLlmModel,
    localLlmApiKey,
    setLlmProvider,
    setAnthropicApiKey,
    setAnthropicModel,
    setLocalLlmEndpoint,
    setLocalLlmModel,
    setLocalLlmApiKey,
    ollamaStatus,
    ollamaProgress,
    ollamaError,
    checkOllamaStatus,
    startOllamaSidecar,
  } = useSettingsStore();

  const toggleUITheme = useUIStore((s) => s.toggleTheme);

  // Sync general UI theme changes
  const handleThemeChange = (newTheme: 'light' | 'dark') => {
    if (theme !== newTheme) {
      toggleUITheme();
    }
  };

  const handleSelectFolder = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: 'Select Edeon Database Directory',
      });
      if (selected && typeof selected === 'string') {
        await setDatabaseDir(selected);
        setShowRestartNotice(true);
      }
    } catch (e) {
      console.error('Failed to select directory:', e);
    }
  };

  const handleRestartEngine = async () => {
    setIsRestarting(true);
    try {
      await restartPython();
    } catch (e) {
      console.error(e);
    } finally {
      setIsRestarting(false);
    }
  };

  // Refresh Python diagnostics when tab is focused
  useEffect(() => {
    if (activeTab === 'engine') {
      fetchPythonDiagnostics();
    }
  }, [activeTab, fetchPythonDiagnostics]);

  // Refresh Ollama status when general settings tab is focused
  useEffect(() => {
    if (activeTab === 'general') {
      checkOllamaStatus();
    }
  }, [activeTab, checkOllamaStatus]);

  return (
    <div className="main-content" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div className="workflow-header" style={{ margin: '16px 20px 8px 20px', flexShrink: 0 }}>
        <div className="workflow-header-info">
          <h2>Settings & Preferences</h2>
          <div className="workflow-header-meta">
            Configure system directories, default pipeline parameters, computational sidecar status, and theme interfaces.
          </div>
        </div>
      </div>

      {/* Main Settings Panel */}
      <div style={{
        display: 'flex',
        flex: 1,
        margin: '8px 20px 20px 20px',
        background: 'var(--color-surface)',
        border: '0.5px solid var(--color-border)',
        borderRadius: '8px',
        overflow: 'hidden',
      }}>
        {/* Left Sub-Sidebar */}
        <div style={{
          width: '200px',
          borderRight: '0.5px solid var(--color-border)',
          background: 'var(--color-bg)',
          padding: '16px 8px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}>
          {[
            { id: 'general', label: '🎨 General & Storage', desc: 'Theme & database path' },
            { id: 'preferences', label: '🎯 Model Preferences', desc: 'Tier preference pinning' },
            { id: 'workflows', label: '⚙ Workflows & ML', desc: 'QSAR training parameters' },
            { id: 'engine', label: '🐍 Computational Engine', desc: 'Python process diagnostics' },
            { id: 'about', label: 'ℹ About Edeon', desc: 'App license & changelog' }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as SettingsTab)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                width: '100%',
                padding: '8px 12px',
                border: 'none',
                borderRadius: '6px',
                background: activeTab === tab.id ? 'var(--color-brand-100)' : 'transparent',
                color: activeTab === tab.id ? 'var(--color-brand-900)' : 'var(--color-text-600)',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
              }}
              className="settings-tab-btn"
            >
              <span style={{ fontSize: '11px', fontWeight: 600 }}>{tab.label}</span>
              <span style={{ fontSize: '9px', color: 'var(--color-text-400)', marginTop: '2px' }}>{tab.desc}</span>
            </button>
          ))}
        </div>

        {/* Right Settings Canvas */}
        <div style={{
          flex: 1,
          padding: '24px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
        }}>
          {/* TAB 1: GENERAL */}
          {activeTab === 'general' && (
            <>
              {/* Theme Selector */}
              <div>
                <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>Global Interface Theme</h3>
                <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '12px' }}>Select Edeon's window rendering style.</p>

                <div style={{ display: 'flex', gap: '16px' }}>
                  {[
                    { id: 'light', label: 'Light Theme', emoji: '☀️', bg: '#ffffff', text: '#111827', border: '#e5e7eb' },
                    { id: 'dark', label: 'Dark Theme', emoji: '🌙', bg: '#0f172a', text: '#f8fafc', border: '#334155' }
                  ].map((t) => (
                    <button
                      key={t.id}
                      onClick={() => handleThemeChange(t.id as 'light' | 'dark')}
                      style={{
                        flex: 1,
                        maxWidth: '220px',
                        padding: '16px',
                        borderRadius: '8px',
                        border: theme === t.id ? '2px solid var(--color-brand-700)' : '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '8px',
                        transition: 'all 0.2s ease',
                      }}
                      className="theme-card-btn"
                    >
                      <span style={{ fontSize: '24px' }}>{t.emoji}</span>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-900)' }}>{t.label}</span>
                      <div style={{
                        width: '100%',
                        height: '24px',
                        borderRadius: '4px',
                        background: t.bg,
                        border: `1px solid ${t.border}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}>
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--color-brand-600)' }} />
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ height: '0.5px', background: 'var(--color-border)' }} />

              {/* Interface Density Selector */}
              <div>
                <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>Interface Density</h3>
                <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '12px' }}>Adjust spacing and sizing density of the user interface.</p>

                <div style={{ display: 'flex', gap: '16px' }}>
                  {[
                    { id: 'compact', label: 'Compact', desc: 'Tight margins & smaller text', padding: '10px 12px' },
                    { id: 'default', label: 'Default', desc: 'Balanced spacing', padding: '14px 16px' },
                    { id: 'comfortable', label: 'Comfortable', desc: 'Spacious padding', padding: '18px 20px' }
                  ].map((d) => (
                    <button
                      key={d.id}
                      onClick={() => setDensity(d.id as 'compact' | 'default' | 'comfortable')}
                      style={{
                        flex: 1,
                        maxWidth: '220px',
                        padding: '16px',
                        borderRadius: '8px',
                        border: density === d.id ? '2px solid var(--color-brand-700)' : '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '6px',
                        transition: 'all 0.2s ease',
                      }}
                      className="density-card-btn"
                    >
                      <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-900)' }}>{d.label}</span>
                      <span style={{ fontSize: '9px', color: 'var(--color-text-400)', textAlign: 'center' }}>{d.desc}</span>
                      <div style={{
                        width: '100%',
                        padding: d.padding,
                        background: 'var(--color-surface-raised, #f9fafb)',
                        border: '1px dashed var(--color-border-default)',
                        borderRadius: '4px',
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        fontSize: '9px',
                        fontWeight: 500,
                        color: 'var(--color-text-secondary)',
                        marginTop: '4px',
                      }}>
                        Row Preview
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ height: '0.5px', background: 'var(--color-border)' }} />

              {/* Data Directory Selector */}
              <div>
                <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>Database Storage Location</h3>
                <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '12px' }}>Choose the directory where `edeon.db` lives. Moving the file permits sharing library sets across devices.</p>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'stretch' }}>
                  <input
                    type="text"
                    value={databaseDir}
                    readOnly
                    style={{
                      flex: 1,
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: '0.5px solid var(--color-border)',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text-600)',
                      fontSize: '11px',
                      fontFamily: 'var(--font-mono)',
                    }}
                  />
                  <button
                    onClick={handleSelectFolder}
                    className="workflow-btn-configure"
                    style={{ height: 'auto', padding: '0 16px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  >
                    📂 Select Folder
                  </button>
                </div>

                {showRestartNotice && (
                  <div className="ad-warning ad-borderline" style={{ marginTop: '12px', background: 'var(--color-amber-50)', borderColor: 'var(--color-amber-500)', color: 'var(--color-amber-900)' }}>
                    <span className="ad-warning-icon">⚠</span>
                    <div className="ad-warning-content">
                      <div className="ad-warning-title">Application Restart Required</div>
                      <div className="ad-warning-details" style={{ fontSize: '10px', marginTop: '2px' }}>
                        The active database file path has been updated in configuration. Please restart Edeon Desktop to apply relocations.
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div style={{ height: '0.5px', background: 'var(--color-border)' }} />

              {/* AI Assistant Settings */}
              <div>
                <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>🤖 AI Assistant Settings</h3>
                <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '12px' }}>Configure Edeon's Grounded AI Research Assistant provider.</p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', background: 'var(--color-bg)', padding: '16px', borderRadius: '8px', border: '0.5px solid var(--color-border)' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)', marginBottom: '6px' }}>AI Assistant Provider</label>
                    <select
                      value={llmProvider}
                      onChange={(e) => setLlmProvider(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '0.5px solid var(--color-border)',
                        background: 'var(--color-surface)',
                        color: 'var(--color-text-800)',
                        fontSize: '11px',
                        outline: 'none',
                      }}
                    >
                      <option value="anthropic">Anthropic Claude API (Remote Cloud)</option>
                      <option value="local">Local OpenAI-Compatible API (Ollama, LM Studio)</option>
                    </select>
                  </div>

                  {llmProvider === 'anthropic' ? (
                    <>
                      <div>
                        <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)', marginBottom: '6px' }}>Anthropic API Key</label>
                        <input
                          type="password"
                          value={anthropicApiKey}
                          onChange={(e) => setAnthropicApiKey(e.target.value)}
                          placeholder="sk-ant-..."
                          style={{
                            width: '100%',
                            padding: '8px 12px',
                            borderRadius: '6px',
                            border: '0.5px solid var(--color-border)',
                            background: 'var(--color-surface)',
                            color: 'var(--color-text-800)',
                            fontSize: '11px',
                            fontFamily: 'var(--font-mono)',
                            outline: 'none',
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)', marginBottom: '6px' }}>Claude Model Name</label>
                        <input
                          type="text"
                          value={anthropicModel}
                          onChange={(e) => setAnthropicModel(e.target.value)}
                          placeholder="claude-3-5-haiku-20241022"
                          style={{
                            width: '100%',
                            padding: '8px 12px',
                            borderRadius: '6px',
                            border: '0.5px solid var(--color-border)',
                            background: 'var(--color-surface)',
                            color: 'var(--color-text-800)',
                            fontSize: '11px',
                            outline: 'none',
                          }}
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)', marginBottom: '6px' }}>Local API Endpoint</label>
                        <input
                          type="text"
                          value={localLlmEndpoint}
                          onChange={(e) => setLocalLlmEndpoint(e.target.value)}
                          placeholder="http://localhost:11434/v1"
                          style={{
                            width: '100%',
                            padding: '8px 12px',
                            borderRadius: '6px',
                            border: '0.5px solid var(--color-border)',
                            background: 'var(--color-surface)',
                            color: 'var(--color-text-800)',
                            fontSize: '11px',
                            outline: 'none',
                          }}
                        />
                        <span style={{ fontSize: '9px', color: 'var(--color-text-400)', marginTop: '4px', display: 'block' }}>
                          Ollama default: <code>http://localhost:11434/v1</code> | LM Studio default: <code>http://localhost:1234/v1</code>
                        </span>
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)', marginBottom: '6px' }}>Local Model Name</label>
                        <input
                          type="text"
                          value={localLlmModel}
                          onChange={(e) => setLocalLlmModel(e.target.value)}
                          placeholder="qwen2.5:3b"
                          style={{
                            width: '100%',
                            padding: '8px 12px',
                            borderRadius: '6px',
                            border: '0.5px solid var(--color-border)',
                            background: 'var(--color-surface)',
                            color: 'var(--color-text-800)',
                            fontSize: '11px',
                            outline: 'none',
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)', marginBottom: '6px' }}>Local API Key (Optional)</label>
                        <input
                          type="password"
                          value={localLlmApiKey}
                          onChange={(e) => setLocalLlmApiKey(e.target.value)}
                          placeholder="None"
                          style={{
                            width: '100%',
                            padding: '8px 12px',
                            borderRadius: '6px',
                            border: '0.5px solid var(--color-border)',
                            background: 'var(--color-surface)',
                            color: 'var(--color-text-800)',
                            fontSize: '11px',
                            fontFamily: 'var(--font-mono)',
                            outline: 'none',
                          }}
                        />
                      </div>

                      {/* Embedded Ollama Sidecar Installer */}
                      <div style={{
                        marginTop: '20px',
                        padding: '16px',
                        borderRadius: '8px',
                        border: '0.5px solid var(--color-border)',
                        background: 'var(--color-surface-raised, rgba(0,0,0,0.02))',
                      }}>
                        <h4 style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-text-800)', margin: '0 0 6px 0', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                          📦 Embedded local LLM sidecar
                        </h4>
                        <p style={{ fontSize: '11.5px', color: 'var(--color-text-500)', margin: '0 0 12px 0', lineHeight: 1.4 }}>
                          If you don't have Ollama installed on Windows, Edeon can automatically download, set up, and run a self-contained Ollama sidecar server inside WSL.
                        </p>

                        {ollamaStatus === 'ready' && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', background: 'rgba(16, 185, 129, 0.1)', color: '#047857', borderRadius: '6px', fontSize: '11px', fontWeight: 600 }}>
                            <span>✓</span>
                            <span>Local Ollama sidecar is active and ready (Model: {localLlmModel})</span>
                          </div>
                        )}

                        {ollamaStatus === 'idle' && (
                          <div>
                            <button
                              type="button"
                              onClick={() => startOllamaSidecar(localLlmModel)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '8px 14px',
                                background: 'var(--color-brand-700)',
                                color: 'white',
                                border: 'none',
                                borderRadius: '6px',
                                fontSize: '11px',
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'background-color 0.2s',
                              }}
                              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-brand-600)'}
                              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--color-brand-700)'}
                            >
                              📥 Embed & Start Local Ollama
                            </button>
                          </div>
                        )}

                        {ollamaStatus === 'downloading' && (
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--color-text-700)', marginBottom: '6px' }}>
                              <span>Downloading Ollama binary...</span>
                              <span style={{ fontWeight: 600 }}>{ollamaProgress}%</span>
                            </div>
                            <div style={{ height: '6px', background: 'var(--color-border)', borderRadius: '3px', overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${ollamaProgress}%`, background: 'var(--color-brand-600)', transition: 'width 0.2s ease' }} />
                            </div>
                          </div>
                        )}

                        {ollamaStatus === 'starting' && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-text-600)', fontSize: '11px' }}>
                            <div className="loading-spinner-small" style={{ width: '12px', height: '12px', border: '2px solid var(--color-border)', borderTopColor: 'var(--color-brand-600)', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                            <span>Starting Ollama daemon... {ollamaProgress}%</span>
                          </div>
                        )}

                        {ollamaStatus === 'pulling' && (
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--color-text-700)', marginBottom: '6px' }}>
                              <span>Downloading Qwen model ({localLlmModel})...</span>
                              <span style={{ fontWeight: 600 }}>{ollamaProgress}%</span>
                            </div>
                            <div style={{ height: '6px', background: 'var(--color-border)', borderRadius: '3px', overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${ollamaProgress}%`, background: 'var(--color-brand-600)', transition: 'width 0.2s ease' }} />
                            </div>
                            <span style={{ fontSize: '9px', color: 'var(--color-text-400)', marginTop: '4px', display: 'block' }}>
                              This download is ~2GB and only occurs once on the first launch.
                            </span>
                          </div>
                        )}

                        {ollamaStatus === 'failed' && (
                          <div>
                            <div style={{ padding: '10px 12px', background: 'rgba(239, 68, 68, 0.1)', color: '#b91c1c', borderRadius: '6px', fontSize: '11.5px', marginBottom: '10px', lineHeight: 1.4 }}>
                              <strong>Setup Failed:</strong> {ollamaError}
                            </div>
                            <button
                              type="button"
                              onClick={() => startOllamaSidecar(localLlmModel)}
                              style={{
                                padding: '6px 12px',
                                background: 'var(--color-brand-700)',
                                color: 'white',
                                border: 'none',
                                borderRadius: '6px',
                                fontSize: '11px',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              🔄 Retry Setup
                            </button>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {/* TAB 2: WORKFLOWS */}
          {activeTab === 'workflows' && (
            <>
              {/* Split Ratio Slider */}
              <div className="config-form-group">
                <label className="config-form-label" style={{ fontSize: '12px', fontWeight: 600 }}>Default Model Validation Split</label>
                <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '6px' }}>Configure the partition index for QSAR model training workflows.</p>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', background: 'var(--color-bg)', padding: '12px 16px', borderRadius: '8px', border: '0.5px solid var(--color-border)' }}>
                  <input
                    type="range"
                    min="0.1"
                    max="0.9"
                    step="0.05"
                    value={splitRatio}
                    onChange={(e) => setSplitRatio(parseFloat(e.target.value))}
                    style={{ flex: 1, accentColor: 'var(--color-brand-600)', cursor: 'pointer' }}
                  />
                  <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-900)', width: '130px', textAlign: 'right' }}>
                    {(splitRatio * 100).toFixed(0)}% Train / {((1 - splitRatio) * 100).toFixed(0)}% Test
                  </div>
                </div>
              </div>

              <div style={{ height: '0.5px', background: 'var(--color-border)' }} />

              {/* Default ML Estimator Algorithm */}
              <div className="config-form-group">
                <label className="config-form-label" style={{ fontSize: '12px', fontWeight: 600 }}>Default ML Estimator Algorithm</label>
                <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '6px' }}>Preferred estimator algorithm selected automatically in training panels.</p>

                <select
                  value={defaultAlgorithm}
                  onChange={(e) => setDefaultAlgorithm(e.target.value)}
                  className="config-select"
                  style={{ padding: '8px 12px', fontSize: '11px', width: '100%', maxWidth: '320px' }}
                >
                  <option value="Random Forest">Random Forest Classifier / Regressor</option>
                  <option value="Gradient Boosting">Gradient Boosting Machine (GBM)</option>
                  <option value="SVM">Support Vector Machine (SVM)</option>
                  <option value="Logistic Regression">Ridge / Logistic Regression</option>
                </select>
              </div>

              <div style={{ height: '0.5px', background: 'var(--color-border)' }} />

              {/* Default Descriptor Sets */}
              <div className="config-form-group">
                <label className="config-form-label" style={{ fontSize: '12px', fontWeight: 600 }}>Primary Cheminformatics Descriptor Set</label>
                <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '6px' }}>Mathematical representation format used for molecular structures.</p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '400px' }}>
                  {[
                    { id: 'MorganFingerprints', label: 'Morgan Fingerprints (Circular FP)', desc: 'High-density bit vector mapping topological structural neighborhoods (radius 2).' },
                    { id: 'RDKitDescriptors', label: 'RDKit Physical Descriptors', desc: 'Continuous scalar traits covering molecular weight, LogP, TPSA, HBD, HBA, and charge distribution.' },
                    { id: 'MACCSKeys', label: 'MACCS Structural Keys', desc: '166-bit dictionary keys validating explicit biological structural substructures.' }
                  ].map((desc) => (
                    <label
                      key={desc.id}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '10px',
                        padding: '12px',
                        borderRadius: '6px',
                        border: defaultDescriptorSet === desc.id ? '1px solid var(--color-brand-600)' : '1px solid var(--color-border)',
                        background: defaultDescriptorSet === desc.id ? 'var(--color-brand-50)' : 'var(--color-bg)',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                      className="descriptor-choice"
                    >
                      <input
                        type="radio"
                        name="descriptorSet"
                        checked={defaultDescriptorSet === desc.id}
                        onChange={() => setDefaultDescriptorSet(desc.id)}
                        style={{ marginTop: '2px', accentColor: 'var(--color-brand-600)' }}
                      />
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-900)' }}>{desc.label}</span>
                        <span style={{ fontSize: '9px', color: 'var(--color-text-400)', marginTop: '2px', lineHeight: '1.3' }}>{desc.desc}</span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* TAB: MODEL PREFERENCES */}
          {activeTab === 'preferences' && (
            <>
              <TierPreferenceSelector />
            </>
          )}


          {/* TAB 3: PYTHON COMPUTATIONAL ENGINE */}
          {activeTab === 'engine' && (
            <>
              {/* Process Diagnostics Panel */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <div>
                    <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>Computational Sidecar Status</h3>
                    <p style={{ fontSize: '11px', color: 'var(--color-text-400)' }}>Edeon runs an isolated RDKit-equipped Python runtime over JSON-RPC IPC.</p>
                  </div>
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 10px',
                    background: pythonStatus === 'active' ? 'var(--color-brand-100)' : pythonStatus === 'loading' ? 'var(--color-blue-100)' : 'var(--color-red-100)',
                    border: `0.5px solid ${pythonStatus === 'active' ? 'var(--color-brand-600)' : pythonStatus === 'loading' ? 'var(--color-blue-500)' : 'var(--color-red-500)'}`,
                    borderRadius: '4px',
                    fontSize: '10px',
                    fontWeight: 600,
                    color: pythonStatus === 'active' ? 'var(--color-brand-900)' : pythonStatus === 'loading' ? 'var(--color-blue-700)' : 'var(--color-red-700)',
                  }}>
                    <span style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: pythonStatus === 'active' ? 'var(--color-brand-600)' : pythonStatus === 'loading' ? 'var(--color-blue-500)' : 'var(--color-red-500)',
                      animation: pythonStatus === 'loading' ? 'pulse 1s infinite alternate' : 'none'
                    }} />
                    {pythonStatus === 'active' ? 'ACTIVE & CONNECTED' : pythonStatus === 'loading' ? 'LOADING...' : 'DISCONNECTED'}
                  </div>
                </div>

                {/* Diagnostics List */}
                <div style={{
                  background: 'var(--color-bg)',
                  border: '0.5px solid var(--color-border)',
                  borderRadius: '8px',
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}>
                  {[
                    { label: 'Edeon Engine Version', value: pythonInfo?.version ?? '—' },
                    { label: 'RDKit Version', value: pythonInfo?.rdkit_version ?? '—' },
                    { label: 'System Python Interpreter', value: pythonInfo?.python_version ?? '—' },
                    { label: 'Platform Platform Architecture', value: pythonInfo?.platform ?? '—' },
                    { label: 'IPC Communication Channel', value: 'JSON-RPC over Stdio (Stdin/Stdout)' }
                  ].map((diag) => (
                    <div key={diag.label} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '0.5px solid var(--color-border)', paddingBottom: '8px' }}>
                      <span style={{ fontSize: '11px', color: 'var(--color-text-400)' }}>{diag.label}</span>
                      <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-900)', fontFamily: 'var(--font-mono)' }}>{diag.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ height: '0.5px', background: 'var(--color-border)' }} />

              {/* Maintenance Actions */}
              <div>
                <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>Maintenance & Process Reboot</h3>
                <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '12px' }}>If the computational engine stops responding or library loading fails, restart the child process.</p>

                <button
                  disabled={isRestarting}
                  onClick={handleRestartEngine}
                  className={pythonStatus === 'active' ? 'workflow-btn-configure' : 'workflow-btn-stop'}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    height: '32px',
                    padding: '0 16px',
                    borderColor: pythonStatus === 'active' ? 'var(--color-border)' : 'var(--color-red-500)',
                    color: pythonStatus === 'active' ? 'var(--color-text-600)' : 'var(--color-red-700)',
                    fontWeight: 500
                  }}
                >
                  {isRestarting ? '🔄 Restarting Child Process...' : '⚡ Reboot Computational Engine'}
                </button>
              </div>
            </>
          )}

          {/* TAB 4: ABOUT EDEON */}
          {activeTab === 'about' && (
            <>
              {/* Product Badge */}
              <div style={{
                background: 'linear-gradient(135deg, var(--color-brand-100), var(--color-blue-100))',
                border: '0.5px solid var(--color-brand-600)',
                borderRadius: '8px',
                padding: '20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'between',
                gap: '16px'
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-brand-900)' }}>Edeon Desktop</h2>
                    <span style={{ fontSize: '11px', color: 'var(--color-brand-700)', fontWeight: 600, background: '#ffffff', padding: '1px 6px', borderRadius: '10px', border: '0.5px solid var(--color-brand-600)' }}>v0.1.0 (Beta)</span>
                  </div>
                  <p style={{ fontSize: '11px', color: 'var(--color-brand-900)', marginTop: '4px', lineHeight: '1.4' }}>
                    Commercial-grade offline-first Lead Optimization & Pesticide Cheminformatics Suite. Built for advanced agrochemical discovery without IP compromise.
                  </p>
                </div>
                <div style={{
                  padding: '8px 12px',
                  background: '#ffffff',
                  border: '0.5px solid var(--color-border)',
                  borderRadius: '6px',
                  textAlign: 'center',
                  minWidth: '150px'
                }}>
                  <div style={{ fontSize: '9px', color: 'var(--color-text-400)', fontWeight: 600, letterSpacing: '0.3px' }}>LICENSE TYPE</div>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-brand-900)', marginTop: '2px' }}>Enterprise Site</div>
                  <div style={{ fontSize: '10px', color: 'var(--color-brand-700)', fontWeight: 500, marginTop: '2px' }}>✓ ACTIVE</div>
                </div>
              </div>

              {/* Component Showcase Sandbox */}
              <div style={{
                border: '0.5px solid var(--color-border)',
                borderRadius: '8px',
                padding: '16px',
                background: 'var(--color-bg)',
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
              }}>
                <div>
                  <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>Model Predictability Tier Badges Showcase</h3>
                  <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '8px' }}>Interactive preview showcasing all four model predictability tiers with hover-activated tooltips.</p>
                  <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <ModelTierBadge tier={1} />
                    <ModelTierBadge tier={2} />
                    <ModelTierBadge tier={3} />
                    <ModelTierBadge tier={4} />
                  </div>
                </div>

                <div style={{ borderTop: '0.5px solid var(--color-border)', paddingTop: '12px' }}>
                  <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>Applicability Domain (AD) Warnings Showcase</h3>
                  <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '8px' }}>Interactive preview showcasing all four applicability domain warning states with detailed score tooltips.</p>
                  <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <ADWarning status="in" score={0.942} />
                    <ADWarning status="borderline" score={0.718} />
                    <ADWarning status="out" score={0.345} />
                    <ADWarning status="unknown" />
                  </div>
                </div>

                <div style={{ borderTop: '0.5px solid var(--color-border)', paddingTop: '12px' }}>
                  <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>PredictionDisplay Component Sandbox</h3>
                  <p style={{ fontSize: '11px', color: 'var(--color-text-400)', marginBottom: '8px' }}>High-fidelity presentation showing primary values, units, conformal intervals, tier pills, applicability badges, and regulatory warnings.</p>
                  <div style={{ maxWidth: '420px' }}>
                    <PredictionDisplay 
                      prediction={{
                        smiles: 'CCO',
                        endpoint: 'bee_acute_oral_ld50',
                        value: { kind: 'numeric', numeric: 4.812 },
                        ci_lower: 3.251,
                        ci_upper: 6.374,
                        ci_level: 0.95,
                        ad_status: 'in',
                        ad_score: 0.942,
                        units: 'μg/bee',
                        model_id: 'bee_model_123',
                        model_version: '1.0.4',
                        tier: 4,
                        timestamp: new Date().toISOString(),
                        provenance: {},
                        warnings: ['Standardized structure matches high-confidence Lipinski descriptor threshold guidelines.']
                      } as Prediction}
                      onClick={() => setActiveModelCardId('bee_acute_oral_ld50.t4.studio-test_model_123')}
                    />
                  </div>
                </div>
              </div>

              {/* Changelog */}
              <div>
                <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '8px' }}>Product Changelog</h3>
                <div style={{
                  height: '200px',
                  overflowY: 'auto',
                  border: '0.5px solid var(--color-border)',
                  background: 'var(--color-bg)',
                  borderRadius: '6px',
                  padding: '16px',
                  fontSize: '11px',
                  lineHeight: '1.6',
                  color: 'var(--color-text-600)'
                }} className="changelog-scroll">
                  <h4 style={{ fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>v0.1.0 — Initial Desktop Release (May 2026)</h4>
                  <ul style={{ paddingLeft: '16px', margin: '0 0 12px 0', listStyleType: 'disc' }}>
                    <li>Integrated 6-stage computational pipeline mapping local compounds directly to Tice pesticide-likeness and cross-species selectivity.</li>
                    <li>Designed premium offline Agrochemical Knowledge Browser querying high-fidelity dossiers (Glyphosate, Imidacloprid, etc.).</li>
                    <li>Developed custom scikit-learn models interface with performance metrics, R² plots, and dynamic training logs.</li>
                    <li>Added environmental PDF dossier and off-target selectivity chartbook print generators.</li>
                    <li>Implemented generic key-value SQLite settings and custom database selector directory panels.</li>
                  </ul>

                  <h4 style={{ fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>v0.0.8 — Early Alpha Prototyping (March 2026)</h4>
                  <ul style={{ paddingLeft: '16px', margin: '0', listStyleType: 'disc' }}>
                    <li>Added SQLite database schema creation for compounds and local workspace storage.</li>
                    <li>Developed basic stdio-based Python JSON-RPC computational sidecar.</li>
                  </ul>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      {activeModelCardId && (
        <ModelCardViewer 
          modelId={activeModelCardId} 
          onClose={() => setActiveModelCardId(null)} 
        />
      )}
    </div>
  );
}
