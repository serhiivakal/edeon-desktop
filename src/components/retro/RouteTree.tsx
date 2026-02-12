import React from 'react';
import { RouteNode } from '../../store/retroStore';

interface RouteTreeProps {
  tree: RouteNode;
  buildingBlocks?: Array<{ smiles: string; in_stock: boolean }>;
}

export const RouteTree: React.FC<RouteTreeProps> = ({ tree, buildingBlocks = [] }) => {
  const renderNode = (node: RouteNode, depth: number = 0) => {
    if (!node) return null;

    if (node.type === 'rxn') {
      return (
        <div key={Math.random()} style={{ marginLeft: `${depth * 16}px`, marginTop: '8px', marginBottom: '8px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '6px',
              background: 'rgba(59, 130, 246, 0.1)',
              border: '0.5px solid rgba(59, 130, 246, 0.3)',
              fontSize: '11px',
              fontWeight: 600,
              color: 'var(--color-brand-600)',
            }}
          >
            <span>&#9881; Reaction: {node.reaction_name || 'Template Disconnection'}</span>
          </div>
          {node.children && node.children.map((c) => renderNode(c, depth + 1))}
        </div>
      );
    }

    return (
      <div key={Math.random()} style={{ marginLeft: `${depth * 16}px`, marginTop: '6px', marginBottom: '6px' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 12px',
            borderRadius: '6px',
            background: node.in_stock ? 'rgba(16, 185, 129, 0.08)' : 'var(--color-surface)',
            border: node.in_stock ? '0.5px solid rgba(16, 185, 129, 0.3)' : '0.5px solid var(--color-border)',
            fontSize: '12px',
          }}
        >
          <span style={{ fontFamily: 'monospace', fontSize: '11px', color: 'var(--color-text-800)' }}>
            {node.smiles}
          </span>
          {node.in_stock !== undefined && (
            <span
              style={{
                fontSize: '9px',
                fontWeight: 600,
                padding: '1px 5px',
                borderRadius: '4px',
                background: node.in_stock ? '#10b981' : '#6b7280',
                color: 'white',
              }}
            >
              {node.in_stock ? 'IN STOCK' : 'PRECURSOR'}
            </span>
          )}
        </div>
        {node.children && node.children.map((c) => renderNode(c, depth + 1))}
      </div>
    );
  };

  return (
    <div style={{ padding: '12px', background: 'rgba(0,0,0,0.02)', borderRadius: '8px', border: '0.5px solid var(--color-border)' }}>
      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-700)', marginBottom: '10px' }}>
        Retrosynthetic Reaction Tree
      </div>
      {renderNode(tree)}

      {buildingBlocks.length > 0 && (
        <div style={{ marginTop: '16px', borderTop: '0.5px solid var(--color-border)', paddingTop: '10px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase', marginBottom: '6px' }}>
            Building Block Reagents ({buildingBlocks.filter(b => b.in_stock).length}/{buildingBlocks.length} in stock)
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {buildingBlocks.map((bb, idx) => (
              <span
                key={idx}
                style={{
                  fontSize: '10px',
                  fontFamily: 'monospace',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: bb.in_stock ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: bb.in_stock ? '#10b981' : '#ef4444',
                  border: `0.5px solid ${bb.in_stock ? '#10b981' : '#ef4444'}`,
                }}
              >
                {bb.smiles}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
