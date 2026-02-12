import React, { useState, useEffect } from 'react';
import { useCartographyStore, TmapLayoutResult, TmapNode } from '../../store/cartographyStore';
import { invoke } from '@tauri-apps/api/core';

interface TmapCanvasProps {
  layout: TmapLayoutResult | null;
  onSelectNode?: (node: TmapNode) => void;
}

function HoverTooltip({ node }: { node: TmapNode }) {
  const [svg, setSvg] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    invoke<string>('depict_compound', { smiles: node.smiles, width: 120, height: 90 })
      .then((res) => {
        if (active) setSvg(res);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [node.smiles]);

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '16px',
        right: '16px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '8px',
        padding: '10px',
        boxShadow: '0 4px 14px rgba(0,0,0,0.15)',
        zIndex: 10,
        pointerEvents: 'none',
        maxWidth: '220px',
      }}
    >
      <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-800)', marginBottom: '4px' }}>
        Node #{node.idx}
      </div>
      {svg && <div dangerouslySetInnerHTML={{ __html: svg }} style={{ display: 'flex', justifyContent: 'center' }} />}
      <div style={{ fontSize: '10px', fontFamily: 'monospace', color: 'var(--color-text-500)', wordBreak: 'break-all', marginTop: '4px' }}>
        {node.smiles}
      </div>
    </div>
  );
}

export const TmapCanvas: React.FC<TmapCanvasProps> = ({ layout, onSelectNode }) => {
  const selectedNodeIdx = useCartographyStore((s) => s.selectedNodeIdx);
  const hoveredNodeIdx = useCartographyStore((s) => s.hoveredNodeIdx);
  const setSelectedNodeIdx = useCartographyStore((s) => s.setSelectedNodeIdx);
  const setHoveredNodeIdx = useCartographyStore((s) => s.setHoveredNodeIdx);

  if (!layout || !layout.ok || layout.nodes.length === 0) {
    return (
      <div
        style={{
          width: '100%',
          height: '420px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--color-bg-base)',
          borderRadius: '8px',
          border: '0.5px solid var(--color-border)',
          color: 'var(--color-text-400)',
          fontSize: '13px',
        }}
      >
        No chemical-space cartography tree rendered. Click "Compute TMAP Layout" to construct the LSH MST tree.
      </div>
    );
  }

  const { nodes, edges } = layout;
  const hoveredNode = hoveredNodeIdx !== null ? nodes.find((n) => n.idx === hoveredNodeIdx) : null;

  // Viewport mapping bounds
  const xVals = nodes.map((n) => n.x);
  const yVals = nodes.map((n) => n.y);
  const minX = Math.min(...xVals);
  const maxX = Math.max(...xVals);
  const minY = Math.min(...yVals);
  const maxY = Math.max(...yVals);

  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;

  const width = 800;
  const height = 460;
  const padding = 40;

  const toCanvasCoords = (x: number, y: number) => {
    const cx = padding + ((x - minX) / rangeX) * (width - 2 * padding);
    const cy = padding + ((y - minY) / rangeY) * (height - 2 * padding);
    return { cx, cy };
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        background: 'var(--color-bg-base)',
        border: '0.5px solid var(--color-border)',
        borderRadius: '8px',
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '8px 12px', background: 'var(--color-surface)', borderBottom: '0.5px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--color-text-600)' }}>
        <span>TMAP Minimum Spanning Tree Layout ({layout.method})</span>
        <span>{nodes.length} Nodes &bull; {edges.length} Branches</span>
      </div>

      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block', background: 'transparent' }}>
        {/* Render MST branch lines */}
        {edges.map((edge, i) => {
          const n1 = nodes[edge.source];
          const n2 = nodes[edge.target];
          if (!n1 || !n2) return null;

          const p1 = toCanvasCoords(n1.x, n1.y);
          const p2 = toCanvasCoords(n2.x, n2.y);

          return (
            <line
              key={i}
              x1={p1.cx}
              y1={p1.cy}
              x2={p2.cx}
              y2={p2.cy}
              stroke="var(--color-border)"
              strokeWidth="1"
              strokeOpacity="0.6"
            />
          );
        })}

        {/* Render Nodes */}
        {nodes.map((node) => {
          const { cx, cy } = toCanvasCoords(node.x, node.y);
          const isSelected = selectedNodeIdx === node.idx;
          const isHovered = hoveredNodeIdx === node.idx;

          return (
            <circle
              key={node.idx}
              cx={cx}
              cy={cy}
              r={isSelected ? 7 : isHovered ? 6 : 4}
              fill={isSelected ? '#3b82f6' : isHovered ? '#10b981' : 'var(--color-brand-600)'}
              stroke={isSelected || isHovered ? 'white' : 'transparent'}
              strokeWidth="2"
              style={{ cursor: 'pointer', transition: 'all 0.1s' }}
              onMouseEnter={() => setHoveredNodeIdx(node.idx)}
              onMouseLeave={() => setHoveredNodeIdx(null)}
              onClick={() => {
                setSelectedNodeIdx(node.idx);
                if (onSelectNode) onSelectNode(node);
              }}
            />
          );
        })}
      </svg>

      {hoveredNode && <HoverTooltip node={hoveredNode} />}
    </div>
  );
};
