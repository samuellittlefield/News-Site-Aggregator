import { useAstronomy } from "../api/client";

const PLANET_ICONS: Record<string, string> = {
  Mercury: "☿", Venus: "♀", Mars: "♂", Jupiter: "♃", Saturn: "♄",
};

export function AstronomySection() {
  const { sky, loading } = useAstronomy();

  if (loading || !sky) return null;

  const visiblePlanets = sky.planets.filter(p => p.visible);

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-base">🔭</span>
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Tonight's Sky</h2>
        <span className="text-xs text-gray-600 normal-case font-normal">{sky.location}</span>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none -mx-4 px-4">

        {/* Moon card */}
        <div className="flex-shrink-0 w-52 bg-gray-900 border border-indigo-900/60 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-indigo-400">Moon</span>
            {sky.moon.is_blue_moon && (
              <span className="text-xs bg-indigo-950 text-indigo-300 border border-indigo-800 rounded-full px-2 py-0.5">
                Blue Moon
              </span>
            )}
          </div>
          <div>
            <p className="text-lg font-bold text-white">{sky.moon.phase}</p>
            <p className="text-xs text-gray-500">{sky.moon.illumination}% illuminated</p>
          </div>
          <div className="text-xs text-gray-600 space-y-0.5">
            <p>Next full: <span className="text-gray-400">{sky.moon.next_full}</span></p>
            {sky.moon.rise && <p>Rises: <span className="text-gray-400">{sky.moon.rise}</span></p>}
          </div>
        </div>

        {/* Visible planet cards */}
        {visiblePlanets.map(p => (
          <div key={p.name} className="flex-shrink-0 w-44 bg-gray-900 border border-yellow-900/50 rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-1.5">
              <span className="text-base">{PLANET_ICONS[p.name] ?? "✦"}</span>
              <span className="text-xs font-semibold text-yellow-400">{p.name}</span>
            </div>
            <p className="text-xs text-gray-300 font-medium">Visible tonight</p>
            <div className="text-xs text-gray-600 space-y-0.5">
              <p>{p.altitude}° altitude</p>
              {p.rise && <p>Rises: <span className="text-gray-400">{p.rise}</span></p>}
              {p.set && <p>Sets: <span className="text-gray-400">{p.set}</span></p>}
            </div>
          </div>
        ))}

        {/* Event cards */}
        {sky.events.map((e, i) => (
          <div key={i} className="flex-shrink-0 w-52 bg-gray-900 border border-purple-900/50 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-purple-400">{e.date}</span>
              <span>{e.icon}</span>
            </div>
            <p className="text-sm font-bold text-white">{e.title}</p>
            <p className="text-xs text-gray-400 leading-relaxed line-clamp-3">{e.description}</p>
          </div>
        ))}

      </div>
    </section>
  );
}
