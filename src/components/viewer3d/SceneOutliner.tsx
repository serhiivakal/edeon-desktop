import React from 'react';
import { 
  Eye, 
  EyeOff, 
  ChevronRight, 
  ChevronDown,
  Dna, 
  Pill, 
  Droplet, 
  Atom, 
  Sparkles, 
  Trash2 
} from 'lucide-react';
import type { SceneEntry, SceneSubEntry, SubEntryType, ReprStyle } from '../../types';

const SUB_ICON: Record<SubEntryType, React.ReactNode> = {
  chain:        <Dna size={11} />,
  ligand:       <Pill size={11} />,
  cofactor:     <Sparkles size={11} />,
  ion:          <Atom size={11} />,
  water:        <Droplet size={11} />,
  pharmacophore:<Sparkles size={11} />,
};

const REPR_OPTIONS: { value: ReprStyle; label: string }[] = [
  { value: 'cartoon', label: 'Cartoon' },
  { value: 'ball+stick', label: 'Ball & Stick' },
  { value: 'licorice', label: 'Licorice (Sticks)' },
  { value: 'spacefill', label: 'Spacefill (CPK)' },
  { value: 'surface', label: 'Electrostatic Surf' },
  { value: 'ribbon', label: 'Ribbon' },
  { value: 'line', label: 'Wireframe Line' },
  { value: 'hidden', label: 'Hidden' }
];

interface Props {
  scene: SceneEntry[];
  onToggleEntry: (id: string) => void;
  onToggleSub:   (entryId: string, subId: string) => void;
  onExpand:      (id: string) => void;
  onSetRepr:     (entryId: string, subId: string, repr: ReprStyle) => void;
  onSetColor:    (entryId: string, subId: string, color: string) => void;
  onRemoveEntry: (id: string) => void;
  onFocusSub:    (entryId: string, subId: string) => void;
}

export function SceneOutliner({
  scene, onToggleEntry, onToggleSub, onExpand,
  onSetRepr, onSetColor, onRemoveEntry, onFocusSub,
}: Props) {
  if (scene.length === 0) {
    return (
      <div className="outliner-empty">
        Load a receptor or dock a ligand to populate the scene outline.
      </div>
    );
  }

  return (
    <div className="scene-outliner">
      {scene.map(entry => (
        <div key={entry.id} className="outliner-entry">
          <div className="outliner-entry-row">
            <button 
              className="outliner-chevron"
              onClick={() => onExpand(entry.id)}
            >
              {entry.expanded ? <ChevronDown size={11}/> : <ChevronRight size={11}/>}
            </button>
            <button 
              className="outliner-eye"
              onClick={() => onToggleEntry(entry.id)}
              title={entry.visible ? 'Hide entry' : 'Show entry'}
            >
              {entry.visible ? <Eye size={12}/> : <EyeOff size={12}/>}
            </button>
            <span className={`outliner-entry-name ${!entry.visible ? 'dimmed' : ''}`}>
              {entry.name}
              {entry.pdbId && <span className="outliner-tag">{entry.pdbId}</span>}
              <span className="outliner-stage-badge">Stage {entry.stageId}</span>
            </span>
            <button 
              className="outliner-remove"
              onClick={() => onRemoveEntry(entry.id)}
              title="Remove from scene"
            >
              <Trash2 size={11}/>
            </button>
          </div>

          {entry.expanded && entry.children.map(sub => (
            <SubRow 
              key={sub.id} 
              entry={entry} 
              sub={sub}
              onToggleSub={onToggleSub}
              onSetRepr={onSetRepr}
              onSetColor={onSetColor}
              onFocusSub={onFocusSub}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function SubRow({
  entry, sub, onToggleSub, onSetRepr, onSetColor, onFocusSub,
}: {
  entry: SceneEntry; sub: SceneSubEntry;
  onToggleSub: Props['onToggleSub'];
  onSetRepr:   Props['onSetRepr'];
  onSetColor:  Props['onSetColor'];
  onFocusSub:  Props['onFocusSub'];
}) {
  const dim = !entry.visible || !sub.visible;
  return (
    <div 
      className={`outliner-sub-row ${dim ? 'dimmed' : ''}`}
      onDoubleClick={() => onFocusSub(entry.id, sub.id)}
      title="Double-click to center camera view on this element"
    >
      <span className="outliner-sub-indent" />
      <button 
        className="outliner-eye"
        onClick={() => onToggleSub(entry.id, sub.id)}
      >
        {sub.visible ? <Eye size={11}/> : <EyeOff size={11}/>}
      </button>
      <span className="outliner-sub-icon">{SUB_ICON[sub.type]}</span>
      <span className="outliner-sub-name" title={sub.selection}>
        {sub.name}
      </span>

      <select 
        className="outliner-repr"
        value={sub.repr}
        onChange={e => onSetRepr(entry.id, sub.id, e.target.value as ReprStyle)}
      >
        {REPR_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>

      {sub.color !== '__chainid' && sub.color !== '__element' ? (
        <input 
          type="color"
          className="outliner-color"
          value={sub.color}
          onChange={e => onSetColor(entry.id, sub.id, e.target.value)}
        />
      ) : (
        <div 
          className="outliner-color-placeholder" 
          title={sub.color === '__chainid' ? 'Chains coloring scheme' : 'Atom element coloring scheme'}
        />
      )}
    </div>
  );
}
