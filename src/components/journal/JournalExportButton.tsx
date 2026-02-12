import React, { useState } from 'react';
import { useJournalStore } from '../../store/journalStore';
import { Download, Check } from 'lucide-react';

interface JournalExportButtonProps {
  projectId: string;
}

export const JournalExportButton: React.FC<JournalExportButtonProps> = ({ projectId }) => {
  const exportJournal = useJournalStore((s) => s.exportJournal);
  const [downloaded, setDownloaded] = useState(false);

  const handleExport = async () => {
    try {
      const data = await exportJournal(projectId, 'json');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `decision_journal_${projectId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setDownloaded(true);
      setTimeout(() => setDownloaded(false), 2000);
    } catch (e) {
      console.error('Export failed', e);
    }
  };

  return (
    <button
      onClick={handleExport}
      className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-lg border border-slate-700 transition-colors font-medium"
    >
      {downloaded ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Download className="w-3.5 h-3.5" />}
      <span>{downloaded ? 'Exported!' : 'Export Audit Journal'}</span>
    </button>
  );
};
