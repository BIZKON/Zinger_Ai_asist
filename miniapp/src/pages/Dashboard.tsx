import { useState, useEffect } from "react";
import { api, type Stats } from "../api";

interface Props {
  userId: number | null;
}

export default function Dashboard({ userId }: Props) {
  const [stats, setStats] = useState<Stats>({
    messages: 0,
    tasks_done: 0,
    calls: 0,
    files: 0,
    tokens_used: 0,
  });
  const [period, setPeriod] = useState<"week" | "month">("month");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .getStats(period)
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [userId, period]);

  const statCards = [
    { label: "Сообщений", value: stats.messages, icon: "💬" },
    { label: "Задач выполнено", value: stats.tasks_done, icon: "✅" },
    { label: "Звонков", value: stats.calls, icon: "📞" },
    { label: "Файлов", value: stats.files, icon: "📄" },
  ];

  return (
    <div>
      <h2 className="section-title">📊 Аналитика</h2>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button
          className={`btn btn-sm ${period === "week" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setPeriod("week")}
        >
          Неделя
        </button>
        <button
          className={`btn btn-sm ${period === "month" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setPeriod("month")}
        >
          Месяц
        </button>
      </div>

      {loading ? (
        <div className="loading">Загрузка...</div>
      ) : (
        <div className="stats-grid">
          {statCards.map((s) => (
            <div key={s.label} className="stat-card">
              <div style={{ fontSize: 24, marginBottom: 4 }}>{s.icon}</div>
              <div className="stat-value">{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title">Использование токенов</div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <span className="card-subtitle">Использовано</span>
          <span style={{ fontWeight: 600 }}>
            {(stats.tokens_used / 1000).toFixed(0)}K
          </span>
        </div>
        <div
          style={{
            background: "#2a2a4a",
            borderRadius: 6,
            height: 8,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              background: "#e94560",
              height: "100%",
              width: `${Math.min(100, (stats.tokens_used / 500000) * 100)}%`,
              borderRadius: 6,
              transition: "width 0.3s",
            }}
          />
        </div>
        <div className="card-subtitle" style={{ marginTop: 4 }}>
          из 500K (тариф Pro)
        </div>
      </div>

      <div className="card">
        <div className="card-title">Тариф</div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 18 }}>Pro</div>
            <div className="card-subtitle">Звонки, файлы, исследования</div>
          </div>
          <button className="btn btn-sm btn-secondary">Изменить</button>
        </div>
      </div>
    </div>
  );
}
