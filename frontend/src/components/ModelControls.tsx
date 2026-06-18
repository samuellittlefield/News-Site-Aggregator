import { ModelKnobs, MODEL_KNOB_META } from "../api/client";

interface Props {
  knobs: ModelKnobs;
  onChange: (k: ModelKnobs) => void;
  onReset: () => void;
  dirty: boolean;
  loading: boolean;
}

export function ModelControls({ knobs, onChange, onReset, dirty, loading }: Props) {
  return (
    <div className="border border-amber-800/40 rounded-lg p-3 bg-amber-950/10 space-y-2.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-amber-300/90 uppercase tracking-wider">
          Model controls {loading && <span className="text-gray-600">· recomputing…</span>}
        </span>
        {dirty && (
          <button onClick={onReset} className="text-[10px] text-gray-500 hover:text-gray-300">
            reset defaults
          </button>
        )}
      </div>
      {MODEL_KNOB_META.map(m => (
        <label key={m.key} className="block" title={m.help}>
          <div className="flex items-center justify-between text-[10px] text-gray-500">
            <span>{m.label}</span>
            <span className="font-mono text-gray-400">{knobs[m.key]}</span>
          </div>
          <input
            type="range"
            min={m.min}
            max={m.max}
            step={m.step}
            value={knobs[m.key]}
            onChange={e => onChange({ ...knobs, [m.key]: Number(e.target.value) })}
            className="w-full h-1 accent-amber-500 cursor-pointer"
          />
        </label>
      ))}
      <p className="text-[9px] text-gray-600">
        Live re-runs the simulation. Widen τ / δ to see the probabilities relax toward 50%.
      </p>
    </div>
  );
}
