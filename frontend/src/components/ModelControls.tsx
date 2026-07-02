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
    <div className="border border-poll-amber-border bg-poll-amber-bg/60 backdrop-blur-lg rounded-2xl shadow-[0_4px_16px_rgba(74,61,112,0.08)] p-3 space-y-2.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-poll-amber uppercase tracking-wider">
          Model controls {loading && <span className="text-ink-muted">· recomputing…</span>}
        </span>
        {dirty && (
          <button onClick={onReset} className="text-[10px] text-ink-muted hover:text-ink">
            reset defaults
          </button>
        )}
      </div>
      {MODEL_KNOB_META.map(m => (
        <label key={m.key} className="block" title={m.help}>
          <div className="flex items-center justify-between text-[10px] text-ink-muted">
            <span>{m.label}</span>
            <span className="font-mono text-ink">{knobs[m.key]}</span>
          </div>
          <input
            type="range"
            min={m.min}
            max={m.max}
            step={m.step}
            value={knobs[m.key]}
            onChange={e => onChange({ ...knobs, [m.key]: Number(e.target.value) })}
            className="w-full h-1 accent-poll-amber cursor-pointer"
          />
        </label>
      ))}
      <p className="text-[9px] text-ink-muted">
        Live re-runs the simulation. Widen τ / δ to see the probabilities relax toward 50%.
      </p>
    </div>
  );
}
