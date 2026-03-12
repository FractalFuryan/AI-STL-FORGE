const PRESETS = [
  {
    id: "fast",
    name: "Fast Draft",
    description: "Quick reconstruction using TripoSR fallback path.",
  },
  {
    id: "balanced",
    name: "Balanced",
    description: "Recommended quality and speed using SF3D.",
  },
  {
    id: "high",
    name: "High Quality",
    description: "Highest detail profile, slower completion.",
  },
];

export default function PresetSelector({ value, onChange }) {
  return (
    <div className="preset-selector">
      <div className="param-label">
        <span className="param-name">Reconstruction Profile</span>
      </div>
      <div className="preset-grid">
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={`preset-card ${value === preset.id ? "selected" : ""}`}
            onClick={() => onChange(preset.id)}
          >
            <span className="preset-name">{preset.name}</span>
            <span className="preset-description">{preset.description}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
