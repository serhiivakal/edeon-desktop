/* ==========================================================
   Edeon Desktop — AnalogGrid Component
   Displays ranked analog suggestions from suggest_analogs with:
   - 2D structure SVGs
   - Delta arrows per endpoint
   - AD status badges
   - "Add to library" action
   ========================================================== */

import React from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useDesignStore, AnalogSuggestion } from '../../store/designStore';
import { useCompoundStore } from '../../store/compoundStore';
import { useProjectStore } from '../../store/projectStore';
import { useJournalStore } from '../../store/journalStore';
import { UqBadge, AdStatus } from '../uq/UqBadge';
import { FeasibilityBadge } from '../retro/FeasibilityBadge';

interface AnalogGridProps {
  parentSmiles: string;
  onAddToLibrary?: (smiles: string) => void;
}

interface StructureSvgProps {
  smiles: string;
}

function StructureSvg({ smiles }: StructureSvgProps) {
  const [svg, setSvg] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    invoke<string>('depict_compound', { smiles })
      .then((res) => {
        if (!cancelled) {
          setSvg(res);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSvg(null);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [smiles]);

  if (loading) {
    return <div className="w-32 h-24 bg-gray-100 dark:bg-gray-800 animate-pulse rounded" />;
  }

  if (!svg) {
    return <div className="w-32 h-24 flex items-center justify-center text-xs text-gray-400 border border-gray-300 dark:border-gray-700 rounded">No structure</div>;
  }

  return <div className="w-32 h-24" dangerouslySetInnerHTML={{ __html: svg }} />;
}

function DeltaArrow({ delta }: { delta: number }) {
  if (delta > 0) {
    return <span className="text-emerald-600 dark:text-emerald-400">↑ {delta.toFixed(2)}</span>;
  } else if (delta < 0) {
    return <span className="text-rose-600 dark:text-rose-400">↓ {Math.abs(delta).toFixed(2)}</span>;
  }
  return <span className="text-gray-500">—</span>;
}

export const AnalogGrid: React.FC<AnalogGridProps> = ({ parentSmiles, onAddToLibrary }) => {
  const { suggestions, loading, error, suggestAnalogs, clearSuggestions } = useDesignStore();
  const { addCompound } = useCompoundStore();
  const activeProjectId = useProjectStore((s) => s.activeProjectId);

  const result = suggestions[parentSmiles];

  React.useEffect(() => {
    if (!result && parentSmiles) {
      // Auto-trigger with a default "improve" target
      suggestAnalogs(parentSmiles, 'bee_margin').catch(() => {});
    }
  }, [parentSmiles]);

  if (loading) {
    return <div className="p-4 text-sm text-gray-500">Generating analog suggestions...</div>;
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-rose-600 dark:text-rose-400">
        Error: {error}
        <button className="ml-2 underline" onClick={() => clearSuggestions(parentSmiles)}>
          Retry
        </button>
      </div>
    );
  }

  if (!result || result.suggestions.length === 0) {
    return <div className="p-4 text-sm text-gray-500">No analogs suggested.</div>;
  }

  const handleAdd = async (suggestion: AnalogSuggestion) => {
    if (!activeProjectId) return;
    try {
      await addCompound(
        activeProjectId,
        `Analog of ${parentSmiles.slice(0, 12)}...`,
        suggestion.smiles
      );
      if (result && result.suggestions.length > 0 && result.suggestions[0].smiles !== suggestion.smiles) {
        useJournalStore.getState().recordOverride(
          activeProjectId,
          result.suggestions[0].smiles,
          'compound',
          suggestion.smiles,
          `Selected analog ${suggestion.smiles.slice(0, 15)}... over top-ranked analog ${result.suggestions[0].smiles.slice(0, 15)}...`,
          `System score for recommended top analog: ${result.suggestions[0].composite_score.toFixed(2)}`
        ).catch(() => {});
      }
      if (onAddToLibrary) onAddToLibrary(suggestion.smiles);
    } catch (e) {
      console.error('Failed to add analog:', e);
    }
  };

  return (
    <div className="analog-grid space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Suggested Analogs ({result.suggestions.length})
        </h3>
        <button
          className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-400"
          onClick={() => clearSuggestions(parentSmiles)}
        >
          Clear
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {result.suggestions.map((suggestion, idx) => (
          <div
            key={idx}
            className="glass-card p-3 border border-gray-200 dark:border-gray-700 rounded-lg hover:shadow-md transition-shadow"
          >
            <div className="flex items-start gap-3">
              <StructureSvg smiles={suggestion.smiles} />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-mono text-gray-600 dark:text-gray-400 truncate" title={suggestion.smiles}>
                  {suggestion.smiles}
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  Transform: <span className="font-medium">{suggestion.transform}</span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <UqBadge
                    status={suggestion.ad_status as AdStatus}
                    score={undefined}
                  />
                  <FeasibilityBadge smiles={suggestion.smiles} />
                </div>
              </div>
            </div>

            {/* Deltas */}
            <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
              <div className="text-xs text-gray-500 mb-1">Endpoint Deltas</div>
              <div className="flex flex-wrap gap-2 text-xs">
                {Object.entries(suggestion.deltas).map(([endpoint, delta]) => (
                  <div key={endpoint} className="flex items-center gap-1 px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">
                    <span className="text-gray-600 dark:text-gray-400">{endpoint}</span>
                    <DeltaArrow delta={delta} />
                  </div>
                ))}
              </div>
            </div>

            {/* Score + Action */}
            <div className="mt-3 flex items-center justify-between">
              <div className="text-xs text-gray-500">
                Score: <span className="font-semibold text-gray-700 dark:text-gray-300">{suggestion.composite_score.toFixed(2)}</span>
              </div>
              <button
                className="text-xs px-3 py-1 rounded bg-brand-600 hover:bg-brand-700 text-white transition-colors"
                onClick={() => handleAdd(suggestion)}
              >
                Add to library
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AnalogGrid;
