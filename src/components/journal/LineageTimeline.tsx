import React, { useEffect } from 'react';
import { useJournalStore } from '../../store/journalStore';
import { DecisionEntryCard } from './DecisionEntryCard';
import { GitCommit, History, X } from 'lucide-react';

interface LineageTimelineProps {
  projectId: string;
  compoundId: string;
  compoundName?: string;
  onClose?: () => void;
}

export const LineageTimeline: React.FC<LineageTimelineProps> = ({
  projectId,
  compoundId,
  compoundName,
  onClose,
}) => {
  const fetchLineage = useJournalStore((s) => s.fetchLineage);
  const lineage = useJournalStore((s) => s.lineage);
  const isLoading = useJournalStore((s) => s.isLoading);
  const addNote = useJournalStore((s) => s.addNote);

  useEffect(() => {
    fetchLineage(projectId, compoundId);
  }, [projectId, compoundId, fetchLineage]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4 max-w-2xl w-full">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2">
          <History className="w-5 h-5 text-indigo-400" />
          <div>
            <h3 className="text-sm font-semibold text-slate-100 uppercase tracking-wide">
              Compound Decision Lineage
            </h3>
            <p className="text-xs text-slate-400 font-mono">
              {compoundName || compoundId} ({lineage?.n_entries || 0} decision points)
            </p>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="p-1 text-slate-500 hover:text-slate-300 rounded-lg hover:bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="p-8 text-center text-xs text-slate-500 font-mono">
          Assembling decision lineage chain...
        </div>
      ) : !lineage || lineage.entries.length === 0 ? (
        <div className="p-8 text-center text-xs text-slate-500">
          No decision journal entries recorded for this compound yet.
        </div>
      ) : (
        <div className="relative border-l-2 border-indigo-500/30 ml-3 pl-5 space-y-4 py-2">
          {lineage.entries.map((entry) => (
            <div key={entry.entry_id} className="relative">
              <div className="absolute -left-[27px] top-4 w-3.5 h-3.5 rounded-full bg-slate-900 border-2 border-indigo-500" />
              <DecisionEntryCard entry={entry} onAddNote={addNote} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
