import { useState, useRef, useEffect } from 'react';

/**
 * Reusable React hook to manage resizable columns in a table.
 * Uses percentage widths so that the table remains perfectly responsive.
 * When a column is resized, space is dynamically traded with its neighbor.
 */
export function useResizableColumns(initialWidths: number[]) {
  const [widths, setWidths] = useState<number[]>(initialWidths);
  const widthsRef = useRef<number[]>(initialWidths);
  const tableRef = useRef<HTMLTableElement>(null);

  // Sync state values with ref to avoid stale closures in mouse event handlers
  useEffect(() => {
    widthsRef.current = widths;
  }, [widths]);

  const handleMouseDown = (index: number, e: React.MouseEvent) => {
    // Prevent standard text selections during dragging
    e.preventDefault();
    e.stopPropagation();

    const startX = e.clientX;
    const startWidths = [...widthsRef.current];
    const totalWidth = tableRef.current?.getBoundingClientRect().width || 1;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaX = moveEvent.clientX - startX;
      // Convert pixel offsets to percentage of total table width
      const pctDelta = (deltaX / totalWidth) * 100;
      const newWidths = [...startWidths];

      // Trade space dynamically with the adjacent column to maintain 100% total sum
      if (index < newWidths.length - 1) {
        const sum = startWidths[index] + startWidths[index + 1];
        // Enforce a minimum column percentage of 4%
        const val1 = Math.max(4, startWidths[index] + pctDelta);
        const val2 = Math.max(4, sum - val1);
        newWidths[index] = val1;
        newWidths[index + 1] = val2;
      } else if (index > 0) {
        const sum = startWidths[index - 1] + startWidths[index];
        const val2 = Math.max(4, startWidths[index] - pctDelta);
        const val1 = Math.max(4, sum - val2);
        newWidths[index - 1] = val1;
        newWidths[index] = val2;
      }

      setWidths(newWidths);
    };

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  return { widths, tableRef, handleMouseDown };
}
