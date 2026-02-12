import { useEffect, useState, useMemo } from 'react';
import { invoke } from '@tauri-apps/api/core';
import type { TPNode, TPGraph } from '../../store/fateStore';

// Subcomponent to fetch and render a 2D molecule depiction from Tauri
function MoleculeDepict({ smiles, size = 120 }: { smiles: string; size?: number }) {
  const [svg, setSvg] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    invoke<string>('depict_compound', { smiles, width: size, height: size - 20 })
      .then((res) => {
        if (active) setSvg(res);
      })
      .catch((err) => {
        console.error('Failed to depict TP compound:', err);
      });
    return () => {
      active = false;
    };
  }, [smiles, size]);

  if (!svg) {
    return (
      <div style={{ 
        width: size, 
        height: size - 20, 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.02)',
        borderRadius: '4px',
        fontSize: '10px',
        color: 'var(--color-text-400)'
      }}>
        Loading...
      </div>
    );
  }

  return (
    <div 
      style={{ width: size, height: size - 20, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      dangerouslySetInnerHTML={{ __html: svg }} 
    />
  );
}

interface PathwayTreeProps {
  graph: TPGraph;
  selectedNodeId: string | null;
  onSelectNode: (node: TPNode) => void;
}

export function PathwayTree({ graph, selectedNodeId, onSelectNode }: PathwayTreeProps) {
  const { nodes, edges } = graph;

  // 1. Group nodes by generation/level using BFS
  const layout = useMemo(() => {
    const levels: Record<string, number> = {};
    const parentNode = nodes.find(n => n.rule === 'parent') || nodes[0];
    if (!parentNode) return { coords: {}, width: 800, height: 600, levels: {} };

    const queue: { id: string; level: number }[] = [{ id: parentNode.id, level: 0 }];
    const visited = new Set<string>();

    while (queue.length > 0) {
      const { id, level } = queue.shift()!;
      if (visited.has(id)) continue;
      visited.add(id);

      levels[id] = Math.max(levels[id] || 0, level);

      // Find children
      const children = edges.filter(e => e.source === id).map(e => e.target);
      for (const childId of children) {
        queue.push({ id: childId, level: level + 1 });
      }
    }

    // Handle any orphaned nodes
    nodes.forEach(n => {
      if (levels[n.id] === undefined) {
        levels[n.id] = 1;
      }
    });

    // Group nodes by level
    const nodesByLevel: Record<number, string[]> = {};
    Object.entries(levels).forEach(([id, lvl]) => {
      if (!nodesByLevel[lvl]) nodesByLevel[lvl] = [];
      nodesByLevel[lvl].push(id);
    });

    // Compute layout constants
    const Y_SPACING = 260;
    const X_SPACING = 220;
    const NODE_WIDTH = 180;

    const maxLevel = Math.max(...Object.values(levels), 0);
    const maxNodesInAnyLevel = Math.max(...Object.values(nodesByLevel).map(arr => arr.length), 1);
    
    const totalWidth = maxNodesInAnyLevel * X_SPACING + 100;
    const totalHeight = (maxLevel + 1) * Y_SPACING + 100;
    const centerX = totalWidth / 2;

    const coords: Record<string, { x: number; y: number }> = {};
    Object.entries(nodesByLevel).forEach(([lvlStr, ids]) => {
      const lvl = parseInt(lvlStr);
      const N = ids.length;
      ids.forEach((id, idx) => {
        const offsetFromCenter = (idx - (N - 1) / 2) * X_SPACING;
        coords[id] = {
          x: centerX + offsetFromCenter - NODE_WIDTH / 2,
          y: lvl * Y_SPACING + 50
        };
      });
    });

    return { coords, width: totalWidth, height: totalHeight, levels };
  }, [nodes, edges]);

  // Center node connection points for drawing lines
  const getConnectionPoints = (nodeId: string) => {
    const coord = layout.coords[nodeId];
    if (!coord) return { topX: 0, topY: 0, bottomX: 0, bottomY: 0 };
    return {
      topX: coord.x + 90,
      topY: coord.y,
      bottomX: coord.x + 90,
      bottomY: coord.y + 200
    };
  };

  return (
    <div style={{ 
      width: '100%', 
      overflowX: 'auto', 
      overflowY: 'auto', 
      border: '0.5px solid var(--color-border)', 
      borderRadius: '8px', 
      background: 'var(--color-bg-base)', 
      minHeight: '400px',
      position: 'relative'
    }}>
      <svg 
        width={layout.width} 
        height={layout.height} 
        style={{ display: 'block', background: 'transparent' }}
      >
        {/* Draw curved Bezier edges */}
        {edges.map((edge, idx) => {
          const start = getConnectionPoints(edge.source);
          const end = getConnectionPoints(edge.target);
          if (!start || !end) return null;

          // Compute Bezier curve path
          const pathD = `M ${start.bottomX} ${start.bottomY} C ${start.bottomX} ${(start.bottomY + end.topY) / 2}, ${end.topX} ${(start.bottomY + end.topY) / 2}, ${end.topX} ${end.topY}`;

          return (
            <g key={idx}>
              <path
                d={pathD}
                fill="none"
                stroke="var(--color-border)"
                strokeWidth="1.5"
                strokeDasharray="4 2"
              />
              {/* Arrow marker at destination */}
              <polygon
                points={`${end.topX},${end.topY} ${end.topX - 4},${end.topY - 6} ${end.topX + 4},${end.topY - 6}`}
                fill="var(--color-text-400)"
              />
            </g>
          );
        })}

        {/* Draw nodes */}
        {nodes.map((node) => {
          const coord = layout.coords[node.id];
          if (!coord) return null;
          const isSelected = selectedNodeId === node.id;
          const isParent = node.rule === 'parent';

          return (
            <foreignObject
              key={node.id}
              x={coord.x}
              y={coord.y}
              width={180}
              height={210}
            >
              <div 
                onClick={() => onSelectNode(node)}
                style={{
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  background: 'var(--color-surface)',
                  border: isSelected 
                    ? '2px solid var(--color-brand-600)' 
                    : '1px solid var(--color-border)',
                  borderRadius: '8px',
                  boxShadow: isSelected 
                    ? '0 4px 12px rgba(37, 99, 235, 0.15)' 
                    : '0 2px 4px rgba(0,0,0,0.02)',
                  cursor: 'pointer',
                  overflow: 'hidden',
                  boxSizing: 'border-box',
                  padding: '8px',
                  transition: 'all 0.15s ease'
                }}
                className={`pathway-node-card ${isSelected ? 'selected' : ''}`}
              >
                {/* Rule title / Type */}
                <div style={{ 
                  fontSize: '9px', 
                  fontWeight: 700, 
                  color: isParent ? 'var(--color-brand-700)' : 'var(--color-text-500)',
                  textTransform: 'uppercase',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  textAlign: 'center',
                  marginBottom: '4px'
                }}>
                  {isParent ? 'Parent Molecule' : node.rule.replace(/_/g, ' ')}
                </div>

                {/* Structure Depiction */}
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <MoleculeDepict smiles={node.smiles} size={160} />
                </div>

                {/* Prob / Score / Liability */}
                <div style={{ 
                  display: 'flex', 
                  flexDirection: 'column',
                  gap: '2px',
                  marginTop: '4px',
                  fontSize: '9px',
                  color: 'var(--color-text-500)'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>P = {node.probability.toFixed(3)}</span>
                    {node.source && (
                      <span style={{ fontSize: '8px', padding: '1px 4px', borderRadius: '3px', background: 'rgba(59, 130, 246, 0.1)', color: '#2563eb', fontWeight: 600 }}>
                        {node.source}
                      </span>
                    )}
                  </div>

                  {(node.liability_flag || node.risk_flag) && (
                    <span style={{ 
                      fontSize: '8px', 
                      background: 'rgba(239, 68, 68, 0.15)', 
                      color: '#ef4444',
                      padding: '1px 4px',
                      borderRadius: '3px',
                      fontWeight: 700,
                      textAlign: 'center'
                    }}>
                      ⚠️ LIABILITY (HIGH RISK)
                    </span>
                  )}
                </div>
              </div>
            </foreignObject>
          );
        })}
      </svg>
    </div>
  );
}
