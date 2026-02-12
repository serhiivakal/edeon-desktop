import { useWorkflowStore } from '../../store/workflowStore';
import { useUIStore } from '../../store/uiStore';
import { RiskBadge } from '../shared/RiskBadge';
import type { RiskLevel } from '../../types';

export function ResultsTable() {
  const results = useWorkflowStore((s) => s.results);
  const isRunning = useWorkflowStore((s) => s.isRunning);
  const activeWorkflow = useWorkflowStore((s) => s.activeWorkflow);
  const selectedId = useUIStore((s) => s.selectedCompoundId);
  const setSelected = useUIStore((s) => s.setSelectedCompound);

  if (!activeWorkflow && !isRunning) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: 'var(--color-text-400)' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px', opacity: 0.6 }}>🧪</div>
          <p style={{ fontSize: '12px' }}>Start a workflow to see results here</p>
        </div>
      </div>
    );
  }

  if (isRunning && results.length === 0) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: 'var(--color-text-400)' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px' }}>⏳</div>
          <p style={{ fontSize: '12px' }}>Workflow running... results will appear when complete</p>
        </div>
      </div>
    );
  }

  const toRisk = (level: string | null): RiskLevel => {
    if (level === 'High' || level === 'Med' || level === 'Low') return level;
    return 'Low';
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div className="results-header">
        <span className="results-title">
          RESULTS · {results.length} COMPOUNDS
        </span>
        <div className="results-actions">
          <button className="results-action">⌕ Filter</button>
          <button className="results-action">↓ Export</button>
        </div>
      </div>

      {/* Table */}
      <div className="results-table-wrap">
        <table className="results-table">
          <thead>
            <tr>
              <th style={{ width: '18%' }}>NAME</th>
              <th style={{ width: '26%' }}>SMILES</th>
              <th className="center" style={{ width: '10%' }}>MW</th>
              <th className="center" style={{ width: '10%' }}>LogP</th>
              <th className="center" style={{ width: '12%' }}>PEST-LIKE</th>
              <th className="center sortable" style={{ width: '12%' }}>SCORE ▾</th>
            </tr>
          </thead>
          <tbody>
            {results.map((compound) => (
              <tr
                key={compound.id}
                className={selectedId === compound.id ? 'selected' : ''}
                onClick={() => setSelected(compound.id)}
                style={{ cursor: 'pointer' }}
              >
                <td>
                  <div className="compound-name">{compound.name}</div>
                </td>
                <td>
                  <span className="compound-smiles selectable">
                    {compound.smiles}
                  </span>
                </td>
                <td className="center">
                  <span className="library-prop-value">
                    {compound.mol_weight != null ? compound.mol_weight.toFixed(1) : '—'}
                  </span>
                </td>
                <td className="center">
                  <span className="library-prop-value">
                    {compound.logp != null ? compound.logp.toFixed(2) : '—'}
                  </span>
                </td>
                <td className="center">
                  <RiskBadge
                    level={toRisk(compound.pesticide_likeness)}
                    context="good"
                  />
                </td>
                <td className="center">
                  <span
                    className="score-value"
                    style={{
                      color:
                        selectedId === compound.id
                          ? 'var(--color-brand-900)'
                          : 'var(--color-text-600)',
                    }}
                  >
                    {compound.score != null ? compound.score.toFixed(1) : '—'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Footer */}
        <div className="results-footer">
          <span>
            Showing {results.length} compounds · sorted by composite score
          </span>
        </div>
      </div>
    </div>
  );
}
