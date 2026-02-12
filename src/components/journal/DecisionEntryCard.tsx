import React, { useState } from 'react';
import { JournalEntry } from '../../store/journalStore';
import { Bot, User, ChevronDown, ChevronRight, CornerDownRight, FileText, ShieldAlert, Sparkles } from 'lucide-react';

interface DecisionEntryCardProps {
  entry: JournalEntry;
  onAddNote?: (entryId: string, note: string) => void;
  onRecordOverride?: (entry: JournalEntry) => void;
}

const KIND_BADGES: Record<string, { label: string; bg: string; text: string }> = {
  workflow_verdict: { label: 'Workflow Verdict', bg: 'bg-indigo-500/10 border-indigo-500/30', text: 'text-indigo-400' },
  compound_promoted: { label: 'Promoted', bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400' },
  compound_rejected: { label: 'Rejected', bg: 'bg-rose-500/10 border-rose-500/30', text: 'text-rose-400' },
  model_deployed: { label: 'Model Deployed', bg: 'bg-sky-500/10 border-sky-500/30', text: 'text-sky-400' },
  model_selected: { label: 'Arena Winner', bg: 'bg-purple-500/10 border-purple-500/30', text: 'text-purple-400' },
  bottleneck_identified: { label: 'Bottleneck Identified', bg: 'bg-amber-500/10 border-amber-500/30', text: 'text-amber-400' },
  analog_registered: { label: 'Analog Registered', bg: 'bg-teal-500/10 border-teal-500/30', text: 'text-teal-400' },
  tp_liability_flagged: { label: 'TP Liability', bg: 'bg-orange-500/10 border-orange-500/30', text: 'text-orange-400' },
  manual_override: { label: 'User Override', bg: 'bg-pink-500/10 border-pink-500/30', text: 'text-pink-400' },
};

export const DecisionEntryCard: React.FC<DecisionEntryCardProps> = ({ entry, onAddNote, onRecordOverride }) => {
  const [expanded, setExpanded] = useState(false);
  const [noteInput, setNoteInput] = useState('');
  const [isEditingNote, setIsEditingNote] = useState(false);

  const kindBadge = KIND_BADGES[entry.decision_kind] || {
    label: entry.decision_kind,
    bg: 'bg-slate-500/10 border-slate-500/30',
    text: 'text-slate-400',
  };

  const isUser = entry.actor === 'user';
  const rationale = entry.rationale_json ? JSON.parse(entry.rationale_json) : null;
  const alternatives = entry.alternatives_json ? JSON.parse(entry.alternatives_json) : null;
  const confidence = entry.confidence_json ? JSON.parse(entry.confidence_json) : null;

  const handleSaveNote = () => {
    if (noteInput.trim() && onAddNote) {
      onAddNote(entry.entry_id, noteInput.trim());
      setIsEditingNote(false);
    }
  };

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 transition-all hover:border-slate-700 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-2.5">
          <div className={`p-1.5 rounded-lg border ${isUser ? 'bg-pink-500/10 border-pink-500/30 text-pink-400' : 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400'}`}>
            {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className={`px-2 py-0.5 text-xs rounded border font-semibold ${kindBadge.bg} ${kindBadge.text}`}>
                {kindBadge.label}
              </span>
              <span className="text-xs font-mono text-slate-500">{entry.subject_type}:{entry.subject_id}</span>
            </div>
            <p className="text-sm font-medium text-slate-200 mt-1">{entry.summary}</p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs text-slate-500 font-mono">
          <span>{new Date(entry.created_at).toLocaleString()}</span>
        </div>
      </div>

      {/* Override / Supersedes indicators */}
      {(entry.override_of || entry.user_note) && (
        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-slate-800/50 text-xs">
          {entry.override_of && (
            <span className="flex items-center space-x-1 text-pink-400 bg-pink-500/10 px-2 py-0.5 rounded border border-pink-500/30 font-mono">
              <CornerDownRight className="w-3 h-3" />
              <span>Overrides: {entry.override_of.slice(0, 8)}...</span>
            </span>
          )}
          {entry.user_note && (
            <span className="flex items-center space-x-1 text-slate-300 bg-slate-800/60 px-2.5 py-0.5 rounded border border-slate-700">
              <FileText className="w-3 h-3 text-amber-400" />
              <span>Note: {entry.user_note}</span>
            </span>
          )}
        </div>
      )}

      {/* Expand Details Trigger */}
      <div className="flex items-center justify-between border-t border-slate-800/50 pt-2 text-xs">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center space-x-1 text-slate-400 hover:text-slate-200 font-medium"
        >
          {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          <span>{expanded ? 'Hide Details' : 'View Rationale & Alternatives'}</span>
        </button>

        <div className="flex items-center space-x-2">
          {!entry.user_note && onAddNote && (
            <button
              onClick={() => setIsEditingNote(!isEditingNote)}
              className="text-slate-500 hover:text-slate-300 font-medium"
            >
              + Add Note
            </button>
          )}
          {!isUser && onRecordOverride && (
            <button
              onClick={() => onRecordOverride(entry)}
              className="text-pink-400 hover:text-pink-300 font-medium"
            >
              Record Override
            </button>
          )}
        </div>
      </div>

      {/* Note Editing Form */}
      {isEditingNote && (
        <div className="flex items-center space-x-2 pt-2">
          <input
            type="text"
            value={noteInput}
            onChange={(e) => setNoteInput(e.target.value)}
            placeholder="Add context or rationale note..."
            className="flex-1 bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
          />
          <button
            onClick={handleSaveNote}
            className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-medium"
          >
            Save
          </button>
        </div>
      )}

      {/* Expanded Rationale & Alternatives */}
      {expanded && (
        <div className="space-y-3 pt-2 text-xs border-t border-slate-800/80">
          {rationale && (
            <div className="space-y-1">
              <span className="font-semibold uppercase tracking-wider text-slate-400">Rationale & Drivers</span>
              <pre className="p-2.5 bg-slate-950 rounded border border-slate-800/80 font-mono text-slate-300 overflow-x-auto">
                {JSON.stringify(rationale, null, 2)}
              </pre>
            </div>
          )}

          {alternatives && alternatives.length > 0 && (
            <div className="space-y-1">
              <span className="font-semibold uppercase tracking-wider text-slate-400">Rejected Alternatives</span>
              <div className="space-y-1">
                {alternatives.map((alt: any) => (
                  <div key={alt.id} className="p-2 bg-slate-950/60 rounded border border-slate-800 flex justify-between font-mono">
                    <span className="text-slate-200 font-medium">{alt.label}</span>
                    <span className="text-slate-400">{alt.why_not}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {confidence && (
            <div className="flex items-center space-x-3 text-slate-400 pt-1">
              <span>AD Status: <strong className="text-slate-200 font-mono">{confidence.ad_status || 'N/A'}</strong></span>
              <span>Reliability: <strong className="text-slate-200 font-mono">{confidence.reliability || 'N/A'}</strong></span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
