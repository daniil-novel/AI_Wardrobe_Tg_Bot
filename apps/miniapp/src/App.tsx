import { type ChangeEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { CloudRain, Heart, Loader2, Search, Sparkles, Upload } from "lucide-react";

import { deleteUpload, getUploadStatus, retryUpload, uploadPhoto } from "./api";
import { BottomNav, InteractiveGarmentTile, ScoreBadge, SectionHead, SmartCard } from "./components";
import { garments, quickScenarios, todayOutfit } from "./data";
import { getTelegramWebApp } from "./telegram";
import type { GarmentCard, OutfitCard, TabKey, UploadStatus } from "./types";
import "./styles.css";

type Notify = (message: string, tone?: "info" | "success" | "warning" | "error") => void;
type UploadMode = "item" | "look" | "auto";

const uploadModes: Array<{ key: UploadMode; label: string }> = [
  { key: "item", label: "Вещь" },
  { key: "look", label: "Лук" },
  { key: "auto", label: "Авто" },
];

function TodayScreen({ onNotify }: { onNotify: Notify }) {
  const [outfit, setOutfit] = useState<OutfitCard>(todayOutfit);
  const [selectedScenario, setSelectedScenario] = useState("Много метро");

  function chooseOutfit() {
    onNotify("Образ выбран и записан в историю носки.", "success");
  }

  function makeWarmer() {
    setOutfit({
      ...outfit,
      title: "Теплее: слой + ботинки",
      score: Math.min(outfit.score + 2, 98),
      reason: "Добавлен верхний слой для ветра и дождя, база осталась нейтральной.",
    });
    onNotify("Собрала более тёплый вариант.", "success");
  }

  function anotherOutfit() {
    setOutfit({
      ...outfit,
      title: "Альтернатива: smart casual",
      score: 88,
      reason: "Меньше денима, больше городского smart casual для вечера.",
    });
    onNotify("Показала другой вариант на сегодня.", "info");
  }

  return (
    <section className="screen-stack">
      <header className="topline">
        <div>
          <span className="eyebrow">AI Wardrobe</span>
          <h1>Привет, что наденем?</h1>
        </div>
        <button className="round-button" type="button" aria-label="AI" onClick={() => onNotify("AI-дизайнер готов.")}>
          <Sparkles size={22} />
        </button>
      </header>

      <article className="weather-card">
        <CloudRain size={22} />
        <div>
          <strong>{outfit.context}</strong>
          <span>Погодный коридор на весь день</span>
        </div>
      </article>

      <article className="hero-outfit">
        <div className="hero-head">
          <div>
            <span className="eyebrow">Лучший вариант</span>
            <h2>{outfit.title}</h2>
          </div>
          <ScoreBadge score={outfit.score} />
        </div>
        <div className="mini-grid">
          {garments.map((item) => (
            <div className="mini-item" key={item.title}>
              <div className={item.imageClass} />
            </div>
          ))}
        </div>
        <div className="reasoning">
          <strong>Почему работает</strong>
          <p>{outfit.reason}</p>
        </div>
        <div className="action-row three">
          <button className="primary" type="button" onClick={chooseOutfit}>
            Выбрать
          </button>
          <button type="button" onClick={makeWarmer}>
            Теплее
          </button>
          <button type="button" onClick={anotherOutfit}>
            Другой
          </button>
        </div>
      </article>

      <SectionHead title="Быстрые сценарии" action={selectedScenario} />
      <div className="scenario-grid">
        {quickScenarios.map(([title, text]) => (
          <button
            className={selectedScenario === title ? "scenario active" : "scenario"}
            key={title}
            type="button"
            onClick={() => {
              setSelectedScenario(title);
              onNotify(`Контекст дня: ${title.toLowerCase()}.`, "success");
            }}
          >
            <Sparkles size={18} />
            <strong>{title}</strong>
            <span>{text}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function WardrobeScreen({ onNotify }: { onNotify: Notify }) {
  const [activeChip, setActiveChip] = useState("Все");
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const chips = ["Все", "Верх", "Низ", "Обувь", "Демисезон", "База", "Проверить"];

  const visibleGarments = garments.filter((item) => {
    const byChip =
      activeChip === "Все" ||
      item.role.includes(activeChip) ||
      item.season.includes(activeChip) ||
      item.title.includes(activeChip);
    const bySearch = !query || item.title.toLowerCase().includes(query.toLowerCase());
    return byChip && bySearch;
  });

  function toggleItem(item: GarmentCard) {
    setSelectedItems((current) => {
      const next = new Set(current);
      if (next.has(item.title)) {
        next.delete(item.title);
      } else {
        next.add(item.title);
      }
      return next;
    });
  }

  return (
    <section className="screen-stack">
      <header className="compact-header">
        <h1>Гардероб</h1>
        <button
          className="round-button"
          type="button"
          aria-label="Поиск"
          onClick={() => {
            setSearchOpen((value) => !value);
            onNotify("Поиск по гардеробу открыт.");
          }}
        >
          <Search size={20} />
        </button>
      </header>
      {searchOpen ? (
        <input
          className="search-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Найти вещь"
          autoFocus
        />
      ) : null}
      <div className="chip-row">
        {chips.map((chip) => (
          <button
            className={activeChip === chip ? "active" : ""}
            type="button"
            key={chip}
            onClick={() => setActiveChip(chip)}
          >
            {chip}
          </button>
        ))}
      </div>
      <article className="health-card">
        <div>
          <span className="eyebrow">Wardrobe Health</span>
          <h2>62%</h2>
        </div>
        <p>Не хватает дождевой обуви и одного спокойного верхнего слоя.</p>
      </article>
      <div className="garment-grid">
        {visibleGarments.map((item) => (
          <InteractiveGarmentTile
            item={item}
            key={item.title}
            selectable
            selected={selectedItems.has(item.title)}
            onClick={() => toggleItem(item)}
          />
        ))}
      </div>
      <button
        className="wide-primary"
        type="button"
        disabled={selectedItems.size === 0}
        onClick={() => onNotify(`Собираю образ с вещами: ${Array.from(selectedItems).join(", ")}.`, "success")}
      >
        Собрать с выбранными
      </button>
    </section>
  );
}

function statusText(status?: string): string {
  const labels: Record<string, string> = {
    queued: "В очереди",
    processing: "AI анализирует",
    completed: "Готово",
    failed: "Ошибка",
  };
  return labels[status ?? ""] ?? "Ожидание";
}

function AddScreen({ onNotify }: { onNotify: Notify }) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [mode, setMode] = useState<UploadMode>("auto");
  const [upload, setUpload] = useState<UploadStatus | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!upload || upload.status === "completed" || upload.status === "failed") {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void getUploadStatus(upload.id)
        .then((nextUpload) => {
          setUpload(nextUpload);
          if (nextUpload.status === "completed") {
            onNotify("Фото обработано, карточка готова.", "success");
          }
        })
        .catch((error: unknown) => {
          onNotify(error instanceof Error ? error.message : "Не удалось получить статус загрузки.", "error");
        });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [onNotify, upload]);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setBusy(true);
    try {
      const nextUpload = await uploadPhoto(file, mode);
      setUpload(nextUpload);
      onNotify("Фото принято и отправлено на обработку.", "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось загрузить фото.", "error");
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function handleRetry() {
    if (!upload) {
      return;
    }
    setBusy(true);
    try {
      const nextUpload = await retryUpload(upload.id);
      setUpload(nextUpload);
      onNotify("Повторная обработка запущена.", "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось повторить обработку.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!upload) {
      return;
    }
    setBusy(true);
    try {
      await deleteUpload(upload.id);
      setUpload(null);
      onNotify("Загрузка удалена.", "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось удалить загрузку.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="screen-stack">
      <header className="compact-header">
        <h1>Добавить</h1>
      </header>
      <article className="upload-card">
        {busy ? <Loader2 className="spin" size={30} /> : <Upload size={30} />}
        <h2>Фото вещи или лука</h2>
        <p>Я создам карточки и сохраню лук в избранное</p>
        <input ref={inputRef} className="file-input" type="file" accept="image/*" onChange={handleFileChange} />
        <button className="primary" type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
          {busy ? "Загружаю..." : "Выбрать фото"}
        </button>
      </article>
      <div className="mode-grid">
        {uploadModes.map((uploadMode) => (
          <button
            className={mode === uploadMode.key ? "active" : ""}
            type="button"
            key={uploadMode.key}
            onClick={() => setMode(uploadMode.key)}
          >
            {uploadMode.label}
          </button>
        ))}
      </div>
      <SectionHead title="Обработка" />
      {upload ? (
        <article className="processing-card">
          <div className="progress-head">
            <strong>{upload.filename ?? "Фото"}</strong>
            <span>{statusText(upload.status)}</span>
          </div>
          <div className="progress-track" aria-label="Статус обработки">
            <span style={{ width: `${Math.max(0, Math.min(upload.progress, 100))}%` }} />
          </div>
          <p>{upload.result_title ?? `Тип: ${upload.upload_type ?? mode} · task ${upload.task_id?.slice(0, 8)}`}</p>
          <div className="action-row two">
            <button type="button" onClick={handleRetry} disabled={busy}>
              Повторить
            </button>
            <button type="button" onClick={handleDelete} disabled={busy}>
              Удалить
            </button>
          </div>
        </article>
      ) : (
        <SmartCard icon="camera" title="Фото ожидается" text="Выберите режим и загрузите изображение" />
      )}
      <SmartCard icon="archive" title="Privacy receipt" text="OpenRouter · original saved · no training" />
    </section>
  );
}

function DesignerScreen({ onNotify }: { onNotify: Notify }) {
  const [activeTool, setActiveTool] = useState("Чего не хватает?");
  const tools = [
    ["layers", "Чего не хватает?", "Wardrobe gaps · missing item cards"],
    ["bot", "Собрать с вещью", "Anchors · weather · event"],
    ["search", "Стоит ли покупать?", "Duplicate risk · compatibility"],
    ["camera", "Оценить образ", "Сначала что работает, затем улучшения"],
    ["calendar", "Капсула", "Неделя · поездка · сезон"],
  ] as const;

  return (
    <section className="screen-stack">
      <header className="compact-header">
        <h1>Дизайнер</h1>
      </header>
      <div className="designer-list">
        {tools.map(([icon, title, text]) => (
          <SmartCard
            active={activeTool === title}
            icon={icon}
            title={title}
            text={text}
            key={title}
            onClick={() => {
              setActiveTool(title);
              onNotify(`${title}: запрос подготовлен.`, "success");
            }}
          />
        ))}
      </div>
      <article className="style-dna">
        <span className="eyebrow">Style DNA</span>
        <h2>casual · minimal · neutral</h2>
        <p>{activeTool} · следующий API-вызов будет выполняться через workers.</p>
        <div className="dna-bars">
          <span style={{ width: "76%" }} />
          <span style={{ width: "58%" }} />
          <span style={{ width: "42%" }} />
        </div>
      </article>
    </section>
  );
}

function FavoritesScreen({ onNotify }: { onNotify: Notify }) {
  const tabs = ["Луки", "Аутфиты", "Wishlist", "Moodboard"];
  const [activeFavoriteTab, setActiveFavoriteTab] = useState(tabs[0]);
  const [favorite, setFavorite] = useState(true);

  return (
    <section className="screen-stack">
      <header className="compact-header">
        <h1>Избранное</h1>
        <button
          className={favorite ? "round-button active" : "round-button"}
          type="button"
          aria-label="Избранное"
          onClick={() => {
            setFavorite((value) => !value);
            onNotify(favorite ? "Убрала из избранного." : "Вернула в избранное.", "success");
          }}
        >
          <Heart size={20} />
        </button>
      </header>
      <div className="tabs">
        {tabs.map((tab) => (
          <button
            className={activeFavoriteTab === tab ? "active" : ""}
            type="button"
            key={tab}
            onClick={() => setActiveFavoriteTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>
      <article className="favorite-look">
        <div className="look-collage">
          {garments.map((item) => (
            <span className={item.imageClass} key={item.title} />
          ))}
        </div>
        <div>
          <span className="eyebrow">{activeFavoriteTab}</span>
          <h2>{todayOutfit.title}</h2>
          <p>{todayOutfit.reason}</p>
        </div>
        <div className="action-row two">
          <button className="primary" type="button" onClick={() => onNotify("Генерирую похожий образ.", "success")}>
            Похожий
          </button>
          <button type="button" onClick={() => onNotify(todayOutfit.reason)}>
            Почему работает
          </button>
        </div>
      </article>
    </section>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("today");
  const [toast, setToast] = useState<{ message: string; tone: string } | null>(null);
  const webApp = useMemo(() => getTelegramWebApp(), []);

  const notify = useMemo<Notify>(
    () => (message, tone = "info") => {
      setToast({ message, tone });
      if (tone === "success") {
        webApp?.HapticFeedback?.notificationOccurred("success");
      } else if (tone === "error") {
        webApp?.HapticFeedback?.notificationOccurred("error");
      } else {
        webApp?.HapticFeedback?.impactOccurred("light");
      }
      window.setTimeout(() => setToast(null), 2800);
    },
    [webApp],
  );

  useEffect(() => {
    webApp?.ready();
    webApp?.expand();
  }, [webApp]);

  useEffect(() => {
    webApp?.HapticFeedback?.impactOccurred("light");
    if (activeTab === "add") {
      webApp?.MainButton?.setText("Выбрать фото");
      webApp?.MainButton?.show();
    } else {
      webApp?.MainButton?.hide();
    }
  }, [activeTab, webApp]);

  const screens: Record<TabKey, ReactNode> = {
    today: <TodayScreen onNotify={notify} />,
    wardrobe: <WardrobeScreen onNotify={notify} />,
    add: <AddScreen onNotify={notify} />,
    designer: <DesignerScreen onNotify={notify} />,
    favorites: <FavoritesScreen onNotify={notify} />,
  };

  return (
    <main className="app-shell">
      {screens[activeTab]}
      {toast ? <div className={`toast ${toast.tone}`}>{toast.message}</div> : null}
      <BottomNav active={activeTab} onChange={setActiveTab} />
    </main>
  );
}
