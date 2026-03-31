import { useState } from "react";

interface Props {
  userId: number | null;
}

export default function Settings({ userId }: Props) {
  const [name, setName] = useState("");
  const [city, setCity] = useState("Санкт-Петербург");
  const [timezone, setTimezone] = useState("Europe/Moscow");
  const [family, setFamily] = useState("");
  const [auto, setAuto] = useState("");
  const [sport, setSport] = useState("");
  const [quietFrom, setQuietFrom] = useState("23:00");
  const [quietTo, setQuietTo] = useState("07:00");
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    // TODO: Call API to save settings
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div>
      <h2 className="section-title">⚙️ Настройки</h2>

      <div className="card">
        <div className="card-title">Профиль</div>

        <div className="form-group">
          <label className="form-label">Имя</label>
          <input
            className="form-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Сергей"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Город</label>
          <input
            className="form-input"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Часовой пояс</label>
          <select
            className="form-input"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
          >
            <option value="Europe/Moscow">Москва (UTC+3)</option>
            <option value="Europe/Samara">Самара (UTC+4)</option>
            <option value="Asia/Yekaterinburg">Екатеринбург (UTC+5)</option>
            <option value="Europe/Kaliningrad">Калининград (UTC+2)</option>
          </select>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Предпочтения</div>

        <div className="form-group">
          <label className="form-label">Семья</label>
          <input
            className="form-input"
            value={family}
            onChange={(e) => setFamily(e.target.value)}
            placeholder="Супруга, дети..."
          />
        </div>

        <div className="form-group">
          <label className="form-label">Автомобиль</label>
          <input
            className="form-input"
            value={auto}
            onChange={(e) => setAuto(e.target.value)}
            placeholder="Марка, модель, год"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Спорт</label>
          <input
            className="form-input"
            value={sport}
            onChange={(e) => setSport(e.target.value)}
            placeholder="Вид спорта, команда"
          />
        </div>
      </div>

      <div className="card">
        <div className="card-title">Тихие часы</div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <label className="form-label">С</label>
            <input
              type="time"
              className="form-input"
              value={quietFrom}
              onChange={(e) => setQuietFrom(e.target.value)}
            />
          </div>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <label className="form-label">До</label>
            <input
              type="time"
              className="form-input"
              value={quietTo}
              onChange={(e) => setQuietTo(e.target.value)}
            />
          </div>
        </div>
      </div>

      <button className="btn btn-primary" onClick={handleSave} style={{ width: "100%" }}>
        {saved ? "✓ Сохранено" : "Сохранить"}
      </button>

      {userId && (
        <p style={{ textAlign: "center", marginTop: 12, fontSize: 12, color: "#666" }}>
          ID: {userId}
        </p>
      )}
    </div>
  );
}
