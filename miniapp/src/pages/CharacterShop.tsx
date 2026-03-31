import { useState } from "react";

interface Persona {
  key: string;
  name: string;
  description: string;
  avatar: string;
  voiceId: string;
}

const PERSONAS: Persona[] = [
  {
    key: "sergiy",
    name: "Сергий",
    description: "Ироничный, саркастичный, умный. Юмор как инструмент.",
    avatar: "🎩",
    voiceId: "Maxim",
  },
  {
    key: "serena",
    name: "Серена",
    description: "Мягкая, эмпатичная, заботливая. Поддержка и тепло.",
    avatar: "🌸",
    voiceId: "Elena",
  },
  {
    key: "viktor",
    name: "Виктор",
    description: "Строгий, военный стиль. Чёткие приказы и дисциплина.",
    avatar: "⚔️",
    voiceId: "Ivan",
  },
  {
    key: "max",
    name: "Макс",
    description: "Молодёжный, дружеский, позитивный. Энергия и драйв.",
    avatar: "🚀",
    voiceId: "Stanislav",
  },
];

export default function CharacterShop() {
  const [selected, setSelected] = useState("sergiy");
  const [saving, setSaving] = useState(false);

  const handleSelect = async (key: string) => {
    setSelected(key);
    setSaving(true);

    // TODO: Call API to save persona
    // await fetch(`/api/user/persona`, { method: 'POST', body: JSON.stringify({ persona: key }) });

    setTimeout(() => setSaving(false), 500);
  };

  return (
    <div>
      <h2 className="section-title">🎭 Выбери персонажа</h2>
      <p className="card-subtitle" style={{ marginBottom: 16 }}>
        Персонаж определяет характер и голос ассистента
      </p>

      <div className="persona-grid">
        {PERSONAS.map((p) => (
          <div
            key={p.key}
            className={`persona-card ${selected === p.key ? "selected" : ""}`}
            onClick={() => handleSelect(p.key)}
          >
            <div className="persona-avatar">{p.avatar}</div>
            <div className="persona-name">{p.name}</div>
            <div className="persona-desc">{p.description}</div>
            <div style={{ marginTop: 8, fontSize: 11, color: "#888" }}>
              🎤 {p.voiceId}
            </div>
            {selected === p.key && (
              <div style={{ marginTop: 8, color: "#e94560", fontWeight: 600 }}>
                ✓ Активен
              </div>
            )}
          </div>
        ))}
      </div>

      {saving && (
        <div style={{ textAlign: "center", marginTop: 16, color: "#e94560" }}>
          Сохраняю...
        </div>
      )}
    </div>
  );
}
