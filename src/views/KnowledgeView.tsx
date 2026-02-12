import { useState, useEffect, useRef } from 'react';
import { useKnowledgeStore } from '../store/knowledgeStore';
import { useProjectStore } from '../store/projectStore';
import { useCompoundStore } from '../store/compoundStore';
import { KnowledgeChatPanel } from '../components/knowledge/KnowledgeChatPanel';

// standard benchmark crop protection agents for quick chips
const BENCHMARK_AGCHEMS = [
  'Glyphosate',
  'Imidacloprid',
  'Atrazine',
  'Chlorothalonil',
  'Tebuconazole',
  'Fipronil',
  'Paraquat',
  'Acetamiprid',
];

export function KnowledgeView() {
  const {
    searchQuery,
    selectedDatabases,
    results,
    selectedResultId,
    loading,
    error,
    setSearchQuery,
    toggleDatabaseFilter,
    setSelectedResultId,
    triggerSearch,
    resetSearch,
  } = useKnowledgeStore();

  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const addCompound = useCompoundStore((s) => s.addCompound);

  const [autocompleteVisible, setAutocompleteVisible] = useState(false);
  const [successImportId, setSuccessImportId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'registry' | 'chat'>('registry');
  const autocompleteRef = useRef<HTMLDivElement>(null);

  // NOTE: No automatic search on mount to avoid blocking the UI while the Python engine starts.
  // Users can click a benchmark chip or type a query to search.

  // Handle click outside autocomplete list to close it
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (autocompleteRef.current && !autocompleteRef.current.contains(event.target as Node)) {
        setAutocompleteVisible(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setAutocompleteVisible(false);
    triggerSearch();
  };

  const handleQuickSearch = (name: string) => {
    setSearchQuery(name);
    setAutocompleteVisible(false);
    setTimeout(() => {
      triggerSearch();
    }, 50);
  };

  const handleImportCompound = async (name: string, smiles: string, id: string) => {
    if (!activeProjectId) {
      alert('Please select or create a project first before importing.');
      return;
    }
    try {
      await addCompound(activeProjectId, name, smiles);
      setSuccessImportId(id);
      setTimeout(() => setSuccessImportId(null), 2500);
    } catch (e) {
      alert(`Import failed: ${e}`);
    }
  };

  const filteredBenchmarks = BENCHMARK_AGCHEMS.filter((name) =>
    name.toLowerCase().includes(searchQuery.toLowerCase()) &&
    name.toLowerCase() !== searchQuery.toLowerCase()
  );

  return (
    <div className="main-content">
      {/* Tab switching style */}
      <style>{`
        .view-tabs-header {
          display: flex;
          gap: 16px;
          border-bottom: 1px solid var(--color-border);
          margin-bottom: 16px;
          padding: 0 20px;
        }
        .view-tab-btn {
          background: none;
          border: none;
          border-bottom: 2px solid transparent;
          padding: 10px 16px;
          font-size: 13px;
          font-weight: 600;
          color: var(--color-text-600);
          cursor: pointer;
          transition: all 0.2s;
        }
        .view-tab-btn:hover {
          color: var(--color-brand-700);
        }
        .view-tab-btn.active {
          color: var(--color-brand-700);
          border-bottom-color: var(--color-brand-700);
        }
      `}</style>

      {/* Header section with green branding */}
      <div className="view-header" style={{ paddingBottom: '8px' }}>
        <div>
          <div className="view-title-row">
            <h1>Agrochemical Knowledge Hub</h1>
          </div>
          <p className="view-subtitle">
            Explore database registries offline &amp; online, or consult Edeon's AI Grounded Research Assistant.
          </p>
        </div>
      </div>

      {/* Tab Switcher Row */}
      <div className="view-tabs-header">
        <button
          type="button"
          className={`view-tab-btn ${activeTab === 'registry' ? 'active' : ''}`}
          onClick={() => setActiveTab('registry')}
        >
          🔍 Registry Search
        </button>
        <button
          type="button"
          className={`view-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          🤖 AI Research Assistant
        </button>
      </div>

      {activeTab === 'chat' ? (
        <div style={{ padding: '0 20px 20px 20px' }}>
          <KnowledgeChatPanel />
        </div>
      ) : (
        <div className="knowledge-browser-container">
          {/* Search form with autocomplete and quick chips */}
          <form onSubmit={handleSearchSubmit} className="knowledge-search-form">
            <div className="knowledge-search-bar" ref={autocompleteRef}>
              <input
                type="text"
                id="knowledge-search-input"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setAutocompleteVisible(true);
                }}
                onFocus={() => setAutocompleteVisible(true)}
                placeholder="Search by compound name, CAS number, formula, or pesticide class..."
                className="knowledge-search-input"
                autoComplete="off"
              />
              <button type="submit" className="knowledge-search-btn">
                Search
              </button>

              {/* Autocomplete Dropdown */}
              {autocompleteVisible && searchQuery && filteredBenchmarks.length > 0 && (
                <div className="knowledge-autocomplete-dropdown">
                  {filteredBenchmarks.map((name) => (
                    <div
                      key={name}
                      className="autocomplete-item"
                      onClick={() => handleQuickSearch(name)}
                    >
                      🔍 <span className="autocomplete-highlight">{name}</span> (Local Dossier)
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Quick-select benchmark active ingredients */}
            <div className="quick-search-chips">
              <span className="quick-search-label">Benchmark Active Ingredients:</span>
              <div className="chips-wrapper">
                {BENCHMARK_AGCHEMS.map((name) => (
                  <button
                    type="button"
                    key={name}
                    className={`chip-btn ${searchQuery.toLowerCase() === name.toLowerCase() ? 'active' : ''}`}
                    onClick={() => handleQuickSearch(name)}
                  >
                    {name}
                  </button>
                ))}
                {searchQuery && (
                  <button
                    type="button"
                    className="chip-btn-clear"
                    onClick={() => {
                      resetSearch();
                      setTimeout(() => triggerSearch(), 50);
                    }}
                  >
                    Clear search ×
                  </button>
                )}
              </div>
            </div>

            {/* Database Source Filter Row */}
            <div className="database-filter-row">
              <span className="filter-label">Active Registries:</span>
              {['PPDB', 'ECOTOX', 'OpenFoodTox', 'ChEMBL'].map((db) => {
                const isActive = selectedDatabases.includes(db);
                return (
                  <button
                    type="button"
                    key={db}
                    onClick={() => toggleDatabaseFilter(db)}
                    className={`db-filter-badge db-${db.toLowerCase()} ${isActive ? 'active' : 'inactive'}`}
                  >
                    <span className="db-indicator" />
                    {db}
                  </button>
                );
              })}
            </div>
          </form>

          {/* Loading & Error States */}
          {loading && (
            <div className="knowledge-status-state">
              <div className="loading-spinner-small" />
              <p>Querying online registries &amp; local database...</p>
            </div>
          )}

          {error && (
            <div className="knowledge-status-state status-error">
              <p>⚠ Search encountered an error: {error}</p>
            </div>
          )}

          {/* Results Matrix */}
          {!loading && !error && (
            <>
              {results.length === 0 ? (
                <div className="knowledge-empty-state">
                  <div className="empty-state-icon">🌾</div>
                  <h3>No pesticide records matched your query</h3>
                  <p>No results found in local database or online registries. Try searching for a standard agent like <strong>Imidacloprid</strong> or <strong>Chlorpyrifos</strong>, or verify that your active registries filters are checked.</p>
                </div>
              ) : (
                <div className="knowledge-results-grid">
                  {results.map((compound) => {
                    const isSelected = compound.id === selectedResultId;
                    const isOnline = compound.source && compound.source !== 'Local';
                    const isChEMBL = compound.id.startsWith('CHEMBL');
                    
                    // Determine regulatory status style
                    const statusText = compound.regulatory_status.eu_status;
                    let statusClass = 'status-unknown';
                    if (statusText.toLowerCase().includes('approved')) {
                      statusClass = 'status-approved';
                    } else if (statusText.toLowerCase().includes('banned') || statusText.toLowerCase().includes('expired')) {
                      statusClass = 'status-banned';
                    } else if (statusText.toLowerCase().includes('restricted') || statusText.toLowerCase().includes('prohibited')) {
                      statusClass = 'status-restricted';
                    }

                    // Determine bee safety hazard
                    const beeSafetyText = compound.ecotox_endpoints.honeybee_ld50;
                    let beeClass = 'bee-unknown';
                    if (beeSafetyText.toLowerCase().includes('high risk')) {
                      beeClass = 'bee-high';
                    } else if (beeSafetyText.toLowerCase().includes('medium risk')) {
                      beeClass = 'bee-med';
                    } else if (beeSafetyText.toLowerCase().includes('low risk')) {
                      beeClass = 'bee-low';
                    }

                    return (
                      <div
                        key={compound.id}
                        className={`knowledge-card ${isSelected ? 'selected' : ''}`}
                        onClick={() => setSelectedResultId(compound.id)}
                      >
                        <div className="card-header-row">
                          <div>
                            <div className="card-class-badge">{compound.class}</div>
                            <h3 className="card-compound-name">{compound.name}</h3>
                          </div>
                          <div className="card-badges-group">
                            {compound.source && (
                              <span className={`source-badge source-${(compound.source || 'local').toLowerCase()}`}>
                                {compound.source}
                              </span>
                            )}
                            <span className={`regulatory-badge-pill ${statusClass}`}>
                              {statusText}
                            </span>
                          </div>
                        </div>

                        <div className="card-meta-row">
                          <span><strong>CAS:</strong> {compound.cas_number}</span>
                          <span><strong>Formula:</strong> {compound.formula}</span>
                        </div>

                        <div className="card-smiles-block selectable" onClick={(e) => e.stopPropagation()}>
                          {compound.smiles}
                        </div>

                        <div className="card-moa-text">
                          <strong>MoA:</strong> {compound.moa}
                        </div>

                        {/* Brief hazard indices — only for records with real ecotox data */}
                        {!isChEMBL && !isOnline && (
                          <div className="card-hazard-summary">
                            <span className={`hazard-indicator ${beeClass}`}>
                              🐝 Bee: {beeSafetyText.split('(')[1]?.replace(')', '') || beeSafetyText}
                            </span>
                            <span className="hazard-indicator fish-indicator">
                              🐟 Fish LC50: {compound.ecotox_endpoints.fish_lc50.split('(')[0].trim()}
                            </span>
                          </div>
                        )}

                        {/* Action buttons */}
                        <div className="card-actions-row">
                          <button
                            type="button"
                            className="inspect-card-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedResultId(compound.id);
                            }}
                          >
                            Inspect Dossier →
                          </button>
                          <button
                            type="button"
                            className={`import-card-btn ${successImportId === compound.id ? 'imported' : ''}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleImportCompound(compound.name, compound.smiles, compound.id);
                            }}
                            disabled={successImportId === compound.id}
                          >
                            {successImportId === compound.id ? '✓ Imported to Lib' : '+ Import to Project'}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
