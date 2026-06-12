import { NewsSegment } from "../components/NewsSegment";

export function NewsPage() {
  return (
    <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      <NewsSegment category="politics" label="Politics" icon="🏛" />
      <div className="border-t border-gray-800/60" />
      <NewsSegment category="transportation" label="Transportation" icon="🚆" />
    </main>
  );
}
