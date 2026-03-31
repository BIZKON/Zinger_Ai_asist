import { useState, useEffect } from "react";
import CharacterShop from "./pages/CharacterShop";
import Settings from "./pages/Settings";
import Dashboard from "./pages/Dashboard";
import MediaArchive from "./pages/MediaArchive";
import "./styles.css";

type Page = "characters" | "settings" | "dashboard" | "media";

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        initDataUnsafe: { user?: { id: number; first_name: string } };
        ready: () => void;
        expand: () => void;
        themeParams: Record<string, string>;
      };
    };
  }
}

function App() {
  const [page, setPage] = useState<Page>("characters");
  const [userId, setUserId] = useState<number | null>(null);
  const [userName, setUserName] = useState("");

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      const user = tg.initDataUnsafe?.user;
      if (user) {
        setUserId(user.id);
        setUserName(user.first_name);
      }
    }
  }, []);

  const navItems: { key: Page; label: string; icon: string }[] = [
    { key: "characters", label: "Персонажи", icon: "🎭" },
    { key: "settings", label: "Настройки", icon: "⚙️" },
    { key: "dashboard", label: "Аналитика", icon: "📊" },
    { key: "media", label: "Архив", icon: "📁" },
  ];

  return (
    <div className="app">
      <header className="header">
        <h1>PersonalAI Sergiy</h1>
        {userName && <span className="user-name">{userName}</span>}
      </header>

      <main className="content">
        {page === "characters" && <CharacterShop />}
        {page === "settings" && <Settings userId={userId} />}
        {page === "dashboard" && <Dashboard userId={userId} />}
        {page === "media" && <MediaArchive userId={userId} />}
      </main>

      <nav className="bottom-nav">
        {navItems.map((item) => (
          <button
            key={item.key}
            className={`nav-btn ${page === item.key ? "active" : ""}`}
            onClick={() => setPage(item.key)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}

export default App;
