import { useState, useEffect } from "react";

interface Props {
  userId: number | null;
}

interface MediaItem {
  id: string;
  file_type: string;
  original_filename: string;
  extracted_text: string;
  created_at: string;
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

  useEffect(() => {
    // TODO: Fetch from API
    // Placeholder data
    setItems([
      {
        id: "1",
        file_type: "document",
        original_filename: "Накладная_А-2847.pdf",
        extracted_text: "Расходная накладная №А-2847 от 15.03.2026...",
        created_at: "2026-03-15",
      },
      {
        id: "2",
        file_type: "photo",
        original_filename: "photo_scan.jpg",
        extracted_text: "Акт приёмки-передачи груза...",
        created_at: "2026-03-14",
      },
      {
        id: "3",
        file_type: "audio",
        original_filename: "meeting_recording.ogg",
        extracted_text: "Совещание по логистике: обсуждение маршрутов...",
        created_at: "2026-03-13",
      },
      {
        id: "4",
        file_type: "table",
        original_filename: "routes_march.xlsx",
        extracted_text: "Реестр маршрутов за март 2026...",
        created_at: "2026-03-10",
      },
    ]);
    setLoading(false);
  }, [userId]);

  const filtered = items.filter((item) => {
    if (filter !== "all" && item.file_type !== filter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        item.original_filename.toLowerCase().includes(q) ||
        item.extracted_text.toLowerCase().includes(q)
      );
    }
    return true;
  });

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
      ) : filtered.length === 0 ? (
        <div className="empty">
          <div className="empty-icon">📭</div>
          <p>Документов не найдено</p>
        </div>
      ) : (
        <div className="media-list">
          {filtered.map((item) => (
            <div key={item.id} className="media-item">
              <div className="media-icon">
                {TYPE_ICONS[item.file_type] || "📎"}
              </div>
              <div className="media-info">
                <div className="media-name">{item.original_filename}</div>
                <div className="media-date">
                  {item.created_at} · {item.extracted_text.slice(0, 50)}...
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
