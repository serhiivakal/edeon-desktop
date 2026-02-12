import { useState } from 'react';
import { useCompoundStore } from '../../store/compoundStore';

interface AddCompoundDialogProps {
  projectId: string;
  onComplete: () => void;
  onClose: () => void;
}

export function AddCompoundDialog({ projectId, onComplete, onClose }: AddCompoundDialogProps) {
  const addCompound = useCompoundStore((s) => s.addCompound);
  const [name, setName] = useState('');
  const [smiles, setSmiles] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    const trimmedName = name.trim();
    const trimmedSmiles = smiles.trim();

    if (!trimmedSmiles) {
      setError('SMILES string is required.');
      return;
    }
    if (!trimmedName) {
      setError('Compound name is required.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      await addCompound(projectId, trimmedName, trimmedSmiles);
      onComplete();
    } catch (e) {
      setError(String(e));
      setSaving(false);
    }
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
    if (e.key === 'Escape') onClose();
  };

  return (
    <div className="dialog-overlay" onClick={handleOverlayClick}>
      <div className="dialog">
        <div className="dialog-header">
          <h3>Add Compound</h3>
          <button className="dialog-close" onClick={onClose}>×</button>
        </div>

        <div className="dialog-body">
          <div className="dialog-field">
            <label className="dialog-label">Name</label>
            <input
              className="dialog-input"
              type="text"
              placeholder="e.g., GLY-247"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
            />
          </div>
          <div className="dialog-field">
            <label className="dialog-label">SMILES</label>
            <input
              className="dialog-input mono"
              type="text"
              placeholder="e.g., OC(=O)CN(F)CP(=O)(O)O"
              value={smiles}
              onChange={(e) => setSmiles(e.target.value)}
              onKeyDown={handleKeyDown}
            />
          </div>

          {error && (
            <div className="dialog-error">{error}</div>
          )}
        </div>

        <div className="dialog-footer">
          <button className="library-btn" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            className="library-btn-primary"
            onClick={handleSubmit}
            disabled={saving}
          >
            {saving ? 'Adding...' : 'Add Compound'}
          </button>
        </div>
      </div>
    </div>
  );
}
