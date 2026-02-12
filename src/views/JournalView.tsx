import React, { useEffect } from 'react';
import { useJournalStore, JournalEntry } from '../store/journalStore';
import { useProjectStore } from '../store/projectStore';
import { DecisionEntryCard } from '../components/journal/DecisionEntryCard';
import { OverrideAnalyticsPanel } from '../components/journal/OverrideAnalyticsPanel';
import { JournalExportButton } from '../components/journal/JournalExportButton';
import { BookOpen, Filter, ChevronLeft, ChevronRight } from 'lucide-react';

export function JournalView() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId) || 'default';
  const fetchList = useJournalStore((s) => s.fetchList);
  const entries = useJournalStore((s) => s.entries);
  const total = useJournalStore((s) => s.total);
  const limit = useJournalStore((s) => s.limit);
  const offset = useJournalStore((s) => s.offset);
  const isLoading = useJournalStore((s) => s.isLoading);
  const filterKind = useJournalStore((s) => s.filterKind);
  const setFilters = useJournalStore((s) => s.setFilters);
  const setPage = useJournalStore((s) => s.setPage);

  const addNote = useJournalStore((s) => s.addNote);
  const recordOverride = useJournalStore((s) => s.recordOverride);

  useEffect(() => {
    fetchList(activeProjectId);
  }, [activeProjectId, offset, filterKind, fetchList]);

  const currentPage = Math.floor(offset / limit);
  const totalPages = Math.ceil(total / limit);

  const handleRecordOverride = (entry: JournalEntry) => {
    const actionTaken = prompt(`Enter action taken (overriding ${entry.decision_kind}):`);
    if (!actionTaken) return;
    const note = prompt('Optional user note / rationale:');

    recordOverride({
      projectId: activeProjectId,
      overrideOf: entry.entry_id,
      subjectType: entry.subject_type,
      subjectId: entry.subject_id,
      actionTaken,
      systemRecommendation: entry.summary,
      userNote: note || undefined,
    });
  };

  return (
    <div className="main-content flex flex-col h-full overflow-hidden p-6 space-y-6 bg-slate-950 text-slate-100">
      {/* Top Header */}
      <div className="flex justify-between items-center border-b border-slate-800 pb-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-indigo-500/10 border border-indigo-500/30 rounded-lg text-indigo-400">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold uppercase tracking-wider text-slate-100">
              Decision Journal & Audit Trail
            </h1>
            <p className="text-xs text-slate-400 font-mono">
              Immutable, append-only record of all consequential discovery decisions (Phase M)
            </p>
          </div>
        </div>

        <JournalExportButton projectId={activeProjectId} />
      </div>

      {/* Override Analytics Card */}
      <OverrideAnalyticsPanel projectId={activeProjectId} />

      {/* Filter Bar & Controls */}
      <div className="flex justify-between items-center bg-slate-900/60 p-3 rounded-lg border border-slate-800 text-xs">
        <div className="flex items-center space-x-3">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="font-semibold text-slate-300">Filter by Decision Kind:</span>
          <select
            value={filterKind || ''}
            onChange={(e) => setFilters({ decisionKind: e.target.value || null })}
            className="bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-slate-200 focus:outline-none"
          >
            <option value="">All Decision Types</option>
            <option value="workflow_verdict">Workflow Verdict</option>
            <option value="compound_promoted">Compound Promoted</option>
            <option value="compound_rejected">Compound Rejected</option>
            <option value="model_deployed">Model Deployed</option>
            <option value="model_selected">Arena Winner</option>
            <option value="bottleneck_identified">Bottleneck Identified</option>
            <option value="analog_registered">Analog Registered</option>
            <option value="tp_liability_flagged">TP Liability Flagged</option>
            <option value="manual_override">User Override</option>
          </select>
        </div>

        <div className="flex items-center space-x-3 font-mono text-slate-400">
          <span>
            Showing {entries.length} of {total} entries
          </span>
          <div className="flex items-center space-x-1">
            <button
              disabled={currentPage === 0}
              onClick={() => setPage(currentPage - 1)}
              className="p-1 rounded border border-slate-800 disabled:opacity-30 hover:bg-slate-800"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span>
              Page {currentPage + 1} of {Math.max(totalPages, 1)}
            </span>
            <button
              disabled={currentPage + 1 >= totalPages}
              onClick={() => setPage(currentPage + 1)}
              className="p-1 rounded border border-slate-800 disabled:opacity-30 hover:bg-slate-800"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Journal Entries List */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {isLoading ? (
          <div className="p-12 text-center text-xs font-mono text-slate-500">
            Loading decision journal entries...
          </div>
        ) : entries.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-500 bg-slate-900/40 rounded-xl border border-slate-800">
            No decision journal entries match the filter criteria.
          </div>
        ) : (
          entries.map((entry) => (
            <DecisionEntryCard
              key={entry.entry_id}
              entry={entry}
              onAddNote={addNote}
              onRecordOverride={handleRecordOverride}
            />
          ))
        )}
      </div>
    </div>
  );
}
