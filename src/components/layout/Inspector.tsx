import { useUIStore } from '../../store/uiStore';
import { useCompoundStore } from '../../store/compoundStore';
import { useWorkflowStore } from '../../store/workflowStore';

export function Inspector() {
  const activeView = useUIStore((s) => s.activeView);
  const selectedCompoundId = useUIStore((s) => s.selectedCompoundId);
  const libraryCompounds = useCompoundStore((s) => s.compounds);
  const workflowResults = useWorkflowStore((s) => s.results);

  // In workflow view, show selected compound from workflow results
  if (activeView === 'workflows') {
    const compound = workflowResults.find((c) => c.id === selectedCompoundId);

    if (!compound) {
      return (
        <aside className="inspector">
          <div className="inspector-empty">
            <div className="inspector-empty-icon">🔬</div>
            <p>Select a compound from the results table</p>
          </div>
        </aside>
      );
    }

    return (
      <aside className="inspector">
        {/* Header */}
        <div>
          <div className="section-label">SELECTED COMPOUND</div>
          <div className="inspector-compound-name">{compound.name}</div>
          <div className="inspector-compound-smiles selectable">{compound.smiles}</div>
        </div>

        {/* Structure placeholder */}
        <div className="inspector-structure">
          <div className="inspector-structure-placeholder">
            <span>2D structure</span>
            <span className="inspector-structure-sub">Available in Phase 4</span>
          </div>
        </div>

        {/* Key Properties */}
        <div>
          <div className="section-label">COMPUTED PROPERTIES</div>
          <div className="inspector-props">
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">MW</span>
              <span className="inspector-prop-value">
                {compound.mol_weight != null ? `${compound.mol_weight.toFixed(2)} g/mol` : '—'}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">LogP</span>
              <span className="inspector-prop-value">
                {compound.logp != null ? compound.logp.toFixed(2) : '—'}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">TPSA</span>
              <span className="inspector-prop-value">
                {compound.tpsa != null ? `${compound.tpsa.toFixed(1)} Å²` : '—'}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">H-bond donors</span>
              <span className="inspector-prop-value">
                {compound.hbd != null ? compound.hbd : '—'}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">H-bond acceptors</span>
              <span className="inspector-prop-value">
                {compound.hba != null ? compound.hba : '—'}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Rotatable bonds</span>
              <span className="inspector-prop-value">
                {compound.rotatable_bonds != null ? compound.rotatable_bonds : '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Pesticide-likeness */}
        <div>
          <div className="section-label">PESTICIDE-LIKENESS</div>
          <div className="inspector-props">
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Tice rules</span>
              <span className="inspector-prop-value" style={{
                color: compound.pesticide_likeness === 'High'
                  ? 'var(--color-brand-700)'
                  : compound.pesticide_likeness === 'Med'
                    ? 'var(--color-amber-700)'
                    : 'var(--color-red-700)',
                fontWeight: 500,
              }}>
                {compound.pesticide_likeness ?? '—'}
              </span>
            </div>
            {compound.violations && (
              <div className="inspector-prop-row">
                <span className="inspector-prop-label">Violations</span>
                <span className="inspector-prop-value" style={{ fontSize: '10px' }}>
                  {compound.violations || 'None'}
                </span>
              </div>
            )}
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Score</span>
              <span className="inspector-prop-value" style={{ fontWeight: 600 }}>
                {compound.score != null ? compound.score.toFixed(1) : '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="inspector-actions">
          <button className="inspector-btn-primary">
            Add to candidates list →
          </button>
        </div>
      </aside>
    );
  }

  // In library view, show selected compound from DB
  if (activeView === 'library') {
    const compound = libraryCompounds.find((c) => c.id === selectedCompoundId);

    if (!compound) {
      return (
        <aside className="inspector">
          <div className="inspector-empty">
            <div className="inspector-empty-icon">🔬</div>
            <p>Select a compound to view details</p>
          </div>
        </aside>
      );
    }

    return (
      <aside className="inspector">
        <div>
          <div className="section-label">SELECTED COMPOUND</div>
          <div className="inspector-compound-name">{compound.name}</div>
          <div className="inspector-compound-smiles selectable">{compound.smiles}</div>
        </div>

        <div className="inspector-structure">
          <div className="inspector-structure-placeholder">
            <span>2D structure</span>
            <span className="inspector-structure-sub">Available in Phase 4</span>
          </div>
        </div>

        <div>
          <div className="section-label">PROPERTIES</div>
          <div className="inspector-props">
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">MW</span>
              <span className="inspector-prop-value">
                {compound.mol_weight != null ? `${compound.mol_weight.toFixed(2)} g/mol` : '—'}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">LogP</span>
              <span className="inspector-prop-value">
                {compound.logp != null ? compound.logp.toFixed(2) : '—'}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">TPSA</span>
              <span className="inspector-prop-value">
                {compound.tpsa != null ? `${compound.tpsa.toFixed(1)} Å²` : '—'}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">H-bond donors</span>
              <span className="inspector-prop-value">
                {compound.hbd != null ? compound.hbd : '—'}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">H-bond acceptors</span>
              <span className="inspector-prop-value">
                {compound.hba != null ? compound.hba : '—'}
              </span>
            </div>
            <div className="inspector-prop-row">
              <span className="inspector-prop-label">Rotatable bonds</span>
              <span className="inspector-prop-value">
                {compound.rotatable_bonds != null ? compound.rotatable_bonds : '—'}
              </span>
            </div>
          </div>
        </div>

        <div className="inspector-notice">
          <span className="inspector-notice-icon">ℹ</span>
          Run a workflow to compute properties.
        </div>

        <div className="inspector-actions">
          <button className="inspector-btn-primary">
            Run workflow on compound →
          </button>
        </div>
      </aside>
    );
  }

  // Default: placeholder
  return (
    <aside className="inspector">
      <div className="inspector-empty">
        <div className="inspector-empty-icon">📋</div>
        <p>Inspector panel</p>
        <p style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>
          Select an item to view details
        </p>
      </div>
    </aside>
  );
}
