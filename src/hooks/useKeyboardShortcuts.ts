/* ==========================================================
   Edeon Desktop — Keyboard Shortcuts Hook
   Global keyboard navigation support for seamless local-first
   library, workflow, and knowledge base traversal.
   ========================================================== */

import { useEffect } from 'react';
import { useUIStore } from '../store/uiStore';
import { useCompoundStore } from '../store/compoundStore';
import { useWorkflowStore } from '../store/workflowStore';
import { useKnowledgeStore } from '../store/knowledgeStore';

export function useKeyboardShortcuts() {
  const activeView = useUIStore((s) => s.activeView);
  const selectedCompoundId = useUIStore((s) => s.selectedCompoundId);
  const setSelectedCompound = useUIStore((s) => s.setSelectedCompound);
  const clearMcs = useUIStore((s) => s.clearMcs);

  const libraryCompounds = useCompoundStore((s) => s.compounds);
  const workflowResults = useWorkflowStore((s) => s.results);

  const selectedResultId = useKnowledgeStore((s) => s.selectedResultId);
  const knowledgeResults = useKnowledgeStore((s) => s.results);
  const setSelectedResultId = useKnowledgeStore((s) => s.setSelectedResultId);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 1. Ignore shortcuts if the user is currently typing in an input, textarea, or contenteditable
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable;

      if (isInput) {
        if (e.key === 'Escape') {
          target.blur();
          e.preventDefault();
        }
        return;
      }

      // 2. Traverse rows/cards using 'j' (down/next) and 'k' (up/prev)
      switch (e.key.toLowerCase()) {
        case 'j': {
          e.preventDefault();
          if (activeView === 'library' && libraryCompounds.length > 0) {
            const idx = libraryCompounds.findIndex((c) => c.id === selectedCompoundId);
            const nextIdx = idx === -1 ? 0 : Math.min(libraryCompounds.length - 1, idx + 1);
            setSelectedCompound(libraryCompounds[nextIdx].id);
            // Attempt to scroll selected row into view
            scrollSelectedRowIntoView();
          } else if (activeView === 'workflows' && workflowResults.length > 0) {
            const idx = workflowResults.findIndex((c) => c.id === selectedCompoundId);
            const nextIdx = idx === -1 ? 0 : Math.min(workflowResults.length - 1, idx + 1);
            setSelectedCompound(workflowResults[nextIdx].id);
            scrollSelectedRowIntoView();
          } else if (activeView === 'knowledge' && knowledgeResults.length > 0) {
            const idx = knowledgeResults.findIndex((c) => c.id === selectedResultId);
            const nextIdx = idx === -1 ? 0 : Math.min(knowledgeResults.length - 1, idx + 1);
            setSelectedResultId(knowledgeResults[nextIdx].id);
            scrollSelectedCardIntoView();
          }
          break;
        }

        case 'k': {
          e.preventDefault();
          if (activeView === 'library' && libraryCompounds.length > 0) {
            const idx = libraryCompounds.findIndex((c) => c.id === selectedCompoundId);
            const prevIdx = idx === -1 ? 0 : Math.max(0, idx - 1);
            setSelectedCompound(libraryCompounds[prevIdx].id);
            scrollSelectedRowIntoView();
          } else if (activeView === 'workflows' && workflowResults.length > 0) {
            const idx = workflowResults.findIndex((c) => c.id === selectedCompoundId);
            const prevIdx = idx === -1 ? 0 : Math.max(0, idx - 1);
            setSelectedCompound(workflowResults[prevIdx].id);
            scrollSelectedRowIntoView();
          } else if (activeView === 'knowledge' && knowledgeResults.length > 0) {
            const idx = knowledgeResults.findIndex((c) => c.id === selectedResultId);
            const prevIdx = idx === -1 ? 0 : Math.max(0, idx - 1);
            setSelectedResultId(knowledgeResults[prevIdx].id);
            scrollSelectedCardIntoView();
          }
          break;
        }

        // '/' focuses search fields
        case '/': {
          e.preventDefault();
          if (activeView === 'knowledge') {
            const input = document.getElementById('knowledge-search-input') as HTMLInputElement | null;
            if (input) {
              input.focus();
              input.select();
            }
          } else if (activeView === 'library') {
            const input = document.querySelector('.library-search') as HTMLInputElement | null;
            if (input) {
              input.focus();
              input.select();
            }
          }
          break;
        }

        // 'Escape' clears overlays, deselects elements, and resets MCS
        case 'escape': {
          e.preventDefault();
          clearMcs();
          useUIStore.getState().setShowShortcutsHelp(false);
          if (activeView === 'library' || activeView === 'workflows') {
            setSelectedCompound(null);
          } else if (activeView === 'knowledge') {
            setSelectedResultId(null);
          }
          break;
        }

        // '?' toggles keyboard shortcuts helper overlay
        case '?': {
          e.preventDefault();
          const current = useUIStore.getState().showShortcutsHelp;
          useUIStore.getState().setShowShortcutsHelp(!current);
          break;
        }

        // 'Enter' can be used as inspect / select focus shortcut
        case 'enter': {
          // If we have selected compound, we can trigger focus to let user know it was accepted
          if (activeView === 'knowledge' && selectedResultId) {
            e.preventDefault();
            // Just pulse or log for custom UX interactions
            console.log('Enter pressed: Inspecting registry dossier', selectedResultId);
          } else if ((activeView === 'library' || activeView === 'workflows') && selectedCompoundId) {
            e.preventDefault();
            console.log('Enter pressed: Inspecting compound details', selectedCompoundId);
          }
          break;
        }

        default:
          break;
      }
    };

    // Helper to scroll selected rows smoothly
    const scrollSelectedRowIntoView = () => {
      // Small timeout to let React render selections
      setTimeout(() => {
        const rows = document.querySelectorAll('.results-table tbody tr');
        rows.forEach((row) => {
          // If row contains an element or click handler with selected style
          if (row.classList.contains('selected')) {
            row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
          }
        });
      }, 50);
    };

    // Helper to scroll selected cards in knowledge browser
    const scrollSelectedCardIntoView = () => {
      setTimeout(() => {
        const cards = document.querySelectorAll('.knowledge-card');
        cards.forEach((card) => {
          if (card.classList.contains('selected')) {
            card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
          }
        });
      }, 50);
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [
    activeView,
    selectedCompoundId,
    setSelectedCompound,
    clearMcs,
    libraryCompounds,
    workflowResults,
    selectedResultId,
    knowledgeResults,
    setSelectedResultId,
  ]);
}
