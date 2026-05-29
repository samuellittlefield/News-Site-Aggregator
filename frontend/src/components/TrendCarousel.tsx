import { Trend } from "../api/client";
import { ClusterStack } from "./ClusterStack";
import { TrendCard } from "./TrendCard";

interface ClusterData {
  id: number;
  name: string;
  category: string | null;
  trends: Trend[];
}

type CarouselItem =
  | { type: "cluster"; data: ClusterData }
  | { type: "trend"; data: Trend };

function buildCarouselItems(trends: Trend[]): CarouselItem[] {
  // Group by cluster
  const clusterMap = new Map<number, ClusterData>();
  const ungrouped: Trend[] = [];

  for (const trend of trends) {
    if (trend.cluster_id && trend.cluster_name) {
      if (!clusterMap.has(trend.cluster_id)) {
        clusterMap.set(trend.cluster_id, {
          id: trend.cluster_id,
          name: trend.cluster_name,
          category: trend.category,
          trends: [],
        });
      }
      clusterMap.get(trend.cluster_id)!.trends.push(trend);
    } else {
      ungrouped.push(trend);
    }
  }

  // Clusters first (largest first), then ungrouped
  const clusters = Array.from(clusterMap.values())
    .sort((a, b) => b.trends.length - a.trends.length);

  return [
    ...clusters.map((c) => ({ type: "cluster" as const, data: c })),
    ...ungrouped.map((t) => ({ type: "trend" as const, data: t })),
  ];
}

interface Props {
  trends: Trend[];
  onSelect: (id: number) => void;
  count: number;
}

export function TrendCarousel({ trends, onSelect, count }: Props) {
  const items = buildCarouselItems(trends);

  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <p className="text-xs text-gray-600">{count} trending topics</p>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-4 scrollbar-none -mx-4 px-4">
        {items.map((item) =>
          item.type === "cluster" ? (
            <ClusterStack
              key={`cluster-${item.data.id}`}
              cluster={item.data}
              onSelect={onSelect}
            />
          ) : (
            // Wrap TrendCard to fix width in carousel context
            <div key={item.data.id} className="flex-shrink-0 w-64">
              <TrendCard trend={item.data} onClick={() => onSelect(item.data.id)} />
            </div>
          )
        )}
      </div>
    </section>
  );
}
