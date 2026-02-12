import React, { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';

interface Pose {
  pose_index: number;
  score_kcal_per_mol: number;
  rmsd_lb?: number;
  rmsd_ub?: number;
  pdbqt_block: string;
}

interface DockingResult {
  poses: Pose[];
  vina_version: string;
  command_line: string;
  elapsed_time_sec: number;
  warnings: string[];
}

interface Props {
  receptorPath: string;
  smiles: string;
  onDockingComplete?: (result: DockingResult) => void;
}

export const DockingDialog: React.FC<Props> = ({ receptorPath, smiles, onDockingComplete }) => {
  const [loading, setLoading] = useState(false);
  const [boxMode, setBoxMode] = useState<'auto' | 'manual'>('auto');
  const [center, setCenter] = useState<[number, number, number]>([12.0, 8.5, -3.2]);
  const [size] = useState<[number, number, number]>([22.0, 22.0, 22.0]);
  const [exhaustiveness, setExhaustiveness] = useState(8);
  const [numModes, setNumModes] = useState(9);
  const [result, setResult] = useState<DockingResult | null>(null);

  const handleRunDocking = async () => {
    setLoading(true);
    try {
      const res = await invoke<DockingResult>('docking_run', {
        receptorPath,
        smiles,
        boxConfig: { center, size },
        options: { exhaustiveness, numModes }
      });
      setResult(res);
      onDockingComplete?.(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 bg-white rounded-lg shadow-lg max-w-md mx-auto space-y-6 border">
      <div className="border-b pb-3">
        <h3 className="text-xl font-bold text-gray-900">3D AutoDock Vina Docking</h3>
        <p className="text-xs text-gray-500 mt-1">
          Perform actual molecular docking against the loaded receptor.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Binding Box Mode</label>
          <div className="flex space-x-2">
            <button
              onClick={() => setBoxMode('auto')}
              className={`flex-1 py-1.5 px-3 text-sm font-medium rounded border transition ${
                boxMode === 'auto'
                  ? 'bg-green-50 border-green-500 text-green-700'
                  : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              Auto-detect (Pocket/Cocrystal)
            </button>
            <button
              onClick={() => setBoxMode('manual')}
              className={`flex-1 py-1.5 px-3 text-sm font-medium rounded border transition ${
                boxMode === 'manual'
                  ? 'bg-green-50 border-green-500 text-green-700'
                  : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              Manual Box Config
            </button>
          </div>
        </div>

        {boxMode === 'manual' && (
          <div className="p-3 bg-gray-50 rounded border space-y-3">
            <div className="text-xs font-semibold text-gray-600">Manual Coordinates (Å)</div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-[10px] text-gray-500">Center X</label>
                <input
                  type="number"
                  value={center[0]}
                  onChange={(e) => setCenter([parseFloat(e.target.value) || 0, center[1], center[2]])}
                  className="w-full border rounded px-1.5 py-1 text-xs font-mono"
                />
              </div>
              <div>
                <label className="block text-[10px] text-gray-500">Center Y</label>
                <input
                  type="number"
                  value={center[1]}
                  onChange={(e) => setCenter([center[0], parseFloat(e.target.value) || 0, center[2]])}
                  className="w-full border rounded px-1.5 py-1 text-xs font-mono"
                />
              </div>
              <div>
                <label className="block text-[10px] text-gray-500">Center Z</label>
                <input
                  type="number"
                  value={center[2]}
                  onChange={(e) => setCenter([center[0], center[1], parseFloat(e.target.value) || 0])}
                  className="w-full border rounded px-1.5 py-1 text-xs font-mono"
                />
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Exhaustiveness</label>
            <select
              value={exhaustiveness}
              onChange={(e) => setExhaustiveness(parseInt(e.target.value))}
              className="w-full border rounded px-2 py-1.5 text-sm"
            >
              <option value={4}>Fast (4)</option>
              <option value={8}>Default (8)</option>
              <option value={32}>Premium (32)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Max Poses</label>
            <select
              value={numModes}
              onChange={(e) => setNumModes(parseInt(e.target.value))}
              className="w-full border rounded px-2 py-1.5 text-sm"
            >
              <option value={1}>1 Pose</option>
              <option value={5}>5 Poses</option>
              <option value={9}>9 Poses</option>
            </select>
          </div>
        </div>

        <button
          onClick={handleRunDocking}
          disabled={loading}
          className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-2 px-4 rounded transition disabled:opacity-50"
        >
          {loading ? 'Docking in Progress (Est. ~30s)...' : 'Run AutoDock Vina'}
        </button>
      </div>

      {result && (
        <div className="border-t pt-4 space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-sm font-bold text-gray-900">Docking Results</span>
            <span className="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-mono">
              {result.vina_version}
            </span>
          </div>

          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {result.poses.map((pose) => (
              <div
                key={pose.pose_index}
                className="flex justify-between items-center p-2 bg-gray-50 border rounded text-xs hover:border-green-500 transition cursor-pointer"
              >
                <span className="font-semibold text-gray-700">Pose #{pose.pose_index}</span>
                <span className="font-mono text-green-600 font-bold bg-green-50 px-2 py-0.5 rounded">
                  {pose.score_kcal_per_mol.toFixed(1)} kcal/mol
                </span>
              </div>
            ))}
          </div>

          <div className="text-[10px] text-gray-400 italic">
            * Vina scores are approximate binding free energy estimates. Always interpret cautiously.
          </div>
        </div>
      )}
    </div>
  );
};
