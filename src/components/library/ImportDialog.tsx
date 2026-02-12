import { useState } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import { useCompoundStore } from '../../store/compoundStore';

interface ImportDialogProps {
  projectId: string;
  onComplete: (count: number) => void;
  onClose: () => void;
}

export function ImportDialog({ projectId, onComplete, onClose }: ImportDialogProps) {
  const importCSV = useCompoundStore((s) => s.importCSV);
  const [status, setStatus] = useState<'idle' | 'importing' | 'done' | 'error'>('idle');
  const [error, setError] = useState('');
  const [filePath, setFilePath] = useState('');

  const handlePickFile = async () => {
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'CSV Files', extensions: ['csv', 'tsv', 'txt'] }],
      });
      if (selected) {
        setFilePath(selected as string);
      }
    } catch (e) {
      console.error('File dialog error:', e);
    }
  };

  const handleImport = async () => {
    if (!filePath) return;
    setStatus('importing');
    setError('');
    try {
      const count = await importCSV(projectId, filePath);
      setStatus('done');
      onComplete(count);
    } catch (e) {
      setStatus('error');
      setError(String(e));
    }
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="dialog-overlay" onClick={handleOverlayClick}>
      <div className="dialog">
        <div className="dialog-header">
          <h3>Import Compounds from CSV</h3>
          <button className="dialog-close" onClick={onClose}>×</button>
        </div>

        <div className="dialog-body">
          <p className="dialog-hint">
            CSV file should contain columns: <code>name</code>, <code>smiles</code>.
            The SMILES column is required. If no name column is found, compounds will be auto-named.
          </p>

          <div className="dialog-file-picker">
            <input
              className="dialog-file-path"
              type="text"
              value={filePath}
              readOnly
              placeholder="No file selected..."
            />
            <button className="library-btn" onClick={handlePickFile} disabled={status === 'importing'}>
              Browse...
            </button>
          </div>

          {error && (
            <div className="dialog-error">{error}</div>
          )}
        </div>

        <div className="dialog-footer">
          <button className="library-btn" onClick={onClose} disabled={status === 'importing'}>
            Cancel
          </button>
          <button
            className="library-btn-primary"
            onClick={handleImport}
            disabled={!filePath || status === 'importing'}
          >
            {status === 'importing' ? 'Importing...' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  );
}
