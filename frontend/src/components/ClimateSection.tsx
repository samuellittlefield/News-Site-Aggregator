import { useClimateEvents } from "../api/client";
import { ClimateCard } from "./ClimateCard";

export function ClimateSection() {
  const { events, loading } = useClimateEvents();

  if (loading) return null;
  if (events.length === 0) return null;

  return (
    <section className="mt-10 space-y-4">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
        </span>
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Climate &amp; Extreme Weather
        </h2>
        <span className="text-xs text-gray-600 normal-case font-normal">
          {events.length} active events
        </span>
      </div>

      {/* Horizontal scroll strip */}
      <div className="flex gap-3 overflow-x-auto pb-3 scrollbar-none">
        {events.map((event) => (
          <ClimateCard key={event.eonet_id} event={event} />
        ))}
      </div>
    </section>
  );
}
