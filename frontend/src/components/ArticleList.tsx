import { Article } from "../api/client";

interface Props {
  articles: Article[];
}

export function ArticleList({ articles }: Props) {
  if (articles.length === 0) {
    return <p className="text-sm text-gray-500 italic">No articles found for this topic.</p>;
  }

  return (
    <ul className="flex flex-col divide-y divide-gray-800">
      {articles.map((article) => (
        <li key={article.id} className="py-4">
          <a
            href={article.url ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex flex-col gap-1"
          >
            <span className="font-medium text-white group-hover:text-blue-400 transition-colors leading-snug">
              {article.headline ?? "Untitled"}
            </span>
            {article.description && (
              <span className="text-sm text-gray-400 line-clamp-2">{article.description}</span>
            )}
            <div className="flex items-center gap-2 text-xs text-gray-600 mt-1">
              {article.source && <span className="font-medium text-gray-500">{article.source}</span>}
              {article.source && article.published_at && <span>·</span>}
              {article.published_at && (
                <span>
                  {new Date(article.published_at).toLocaleDateString([], {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
              )}
            </div>
          </a>
        </li>
      ))}
    </ul>
  );
}
