import { useNews } from "../../api/client";
import { Panel } from "./Panel";

export function NewsPanel({ onOpen }: { onOpen: () => void }) {
  const { articles: politics, loading } = useNews("politics");
  const { articles: transport } = useNews("transportation");

  const items = [
    ...politics.slice(0, 3).map(a => ({ ...a, icon: "🏛" })),
    ...transport.slice(0, 2).map(a => ({ ...a, icon: "🚆" })),
  ];

  return (
    <Panel title="News Wire" icon="📰" onOpen={onOpen}>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-6 bg-gray-800/50 rounded animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-gray-600">No articles yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((a) => (
            <li key={`${a.category}-${a.id}`} className="flex items-start gap-2 text-xs leading-snug">
              <span className="leading-none mt-0.5">{a.icon}</span>
              <span className="text-gray-300 line-clamp-1">{a.title}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
