import { useState, useEffect } from "react";
import { api, type MediaItem } from "../api";

interface Props {
  userId: number | null;
}

const TYPE_ICONS: Record<string, string> = {
  document: "📄",
  photo: "🖼️",
  vision: "🖼️",
  audio: "🎤",
  video: "🎬",
  table: "📊",
};

export default function MediaArchive({ userId }: Props) {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  const fetchMedia = () => {
    setLoading(true);
    api
      .getMedia(search, filter)
      .then((data) => setItems(data.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchMedia();
  }, [userId, filter]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(fetchMedia, 400);
    return () => clearTimeout(timer);
  }, [search]);

  const filterOptions = [
    { key: "all", label: "Все" },
    { key: "document", label: "📄" },
    { key: "photo", label: "🖼️" },
    { key: "audio", label: "🎤" },
    { key: "table", label: "📊" },
  ];

  return (
    <div>
      <h2 className="section-title">📁 Архив документов</h2>

      <div className="search-bar">
        <input
          className="form-input"
          placeholder="Поиск по содержимому..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
        {filterOptions.map((f) => (
          <button
            key={f.key}
            className={`btn btn-sm ${filter === f.key ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading">Загрузка...</div>
      ) : items.length === 0 ? (
        <div className="empty">
          <div className="empty-icon">📭</div>
          <p>Документов не найдено</p>
        </div>
      ) : (
        <div className="media-list">
          {items.map((item) => (
            <div key={item.id} className="media-item">
              <div className="media-icon">
                {TYPE_ICONS[item.file_type || ""] || "📎"}
              </div>
              <div className="media-info">
                <div className="media-name">{item.original_filename || "Без имени"}</div>
                <div className="media-date">
                  {item.created_at?.slice(0, 10)} · {item.extracted_text?.slice(0, 50)}...
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
