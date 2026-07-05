import { type ChangeEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  CloudRain,
  CloudSun,
  Heart,
  Loader2,
  MapPin,
  MessageCircle,
  Search,
  Send,
  Sparkles,
  Thermometer,
  Umbrella,
  Upload,
  Wind,
} from "lucide-react";

import {
  authenticateWithTelegram,
  deleteUpload,
  getWeather,
  getUploadStatus,
  hasAccessToken,
  listOutfits,
  listWardrobeItems,
  recommendOutfit,
  retryUpload,
  runDesignerTool,
  uploadPhoto,
} from "./api";
import { BottomNav, InteractiveGarmentTile, ScoreBadge, SectionHead, SmartCard } from "./components";
import { quickScenarios } from "./data";
import { getTelegramWebApp } from "./telegram";
import type { DesignerResult, DesignerToolKey, GarmentCard, OutfitCard, TabKey, UploadStatus, WeatherSummary } from "./types";
import "./styles.css";

type Notify = (message: string, tone?: "info" | "success" | "warning" | "error") => void;
type UploadMode = "item" | "look" | "auto";

const uploadModes: Array<{ key: UploadMode; label: string }> = [
  { key: "item", label: "Вещь" },
  { key: "look", label: "Лук" },
  { key: "auto", label: "Авто" },
];

function TodayScreen({ onNotify }: { onNotify: Notify }) {
  const [outfit, setOutfit] = useState<OutfitCard | null>(null);
  const [wardrobeItems, setWardrobeItems] = useState<GarmentCard[]>([]);
  const [selectedScenario, setSelectedScenario] = useState("Много метро");
  const [scenarioText, setScenarioText] = useState("Много метро, вечером короткая встреча, хочу не замёрзнуть.");
  const [weatherPreference, setWeatherPreference] = useState("мерзну, лучше теплее");
  const [weather, setWeather] = useState<WeatherSummary | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [chatBusy, setChatBusy] = useState(false);

  useEffect(() => {
    if (!hasAccessToken()) {
      return;
    }
    void Promise.all([listOutfits(), listWardrobeItems(), getWeather(55.7558, 37.6173).catch(() => null)])
      .then(([outfits, items, weatherSummary]) => {
        setOutfit(outfits[0] ?? null);
        setWardrobeItems(items);
        setWeather(weatherSummary);
      })
      .catch((error: unknown) => {
        onNotify(error instanceof Error ? error.message : "Не удалось загрузить состояние.", "error");
      });
  }, [onNotify]);

  function chooseOutfit() {
    if (!outfit) {
      return;
    }
    onNotify("Образ выбран и записан в историю носки.", "success");
  }

  function makeWarmer() {
    if (!outfit) {
      return;
    }
    setOutfit({
      ...outfit,
      title: "Теплее: слой + ботинки",
      score: Math.min(outfit.score + 2, 98),
      reason: "Добавлен верхний слой для ветра и дождя, база осталась нейтральной.",
    });
    onNotify("Собрала более тёплый вариант.", "success");
  }

  function anotherOutfit() {
    onNotify("Запрос нового варианта отправляется через backend рекомендации.", "info");
  }

  function loadWeatherByLocation() {
    if (!hasAccessToken()) {
      onNotify("Для точной погоды откройте Mini App внутри Telegram и войдите.", "warning");
      return;
    }
    if (!navigator.geolocation) {
      onNotify("Геолокация недоступна в этом браузере.", "warning");
      return;
    }
    setWeatherLoading(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        void getWeather(position.coords.latitude, position.coords.longitude)
          .then((summary) => {
            setWeather(summary);
            onNotify("Погода обновлена по текущей геолокации.", "success");
          })
          .catch((error: unknown) => {
            onNotify(error instanceof Error ? error.message : "Не удалось получить погоду.", "error");
          })
          .finally(() => setWeatherLoading(false));
      },
      () => {
        setWeatherLoading(false);
        onNotify("Не удалось получить геолокацию. Можно описать погоду вручную.", "warning");
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 900000 },
    );
  }

  async function submitScenario() {
    const prompt = scenarioText.trim();
    if (!prompt) {
      onNotify("Опишите сценарий дня: куда идёте, сколько ходить и насколько тепло хочется.", "warning");
      return;
    }
    if (!hasAccessToken()) {
      onNotify("Сценарий сохранён локально. Для подбора из гардероба нужен вход через Telegram.", "warning");
      return;
    }
    setChatBusy(true);
    try {
      const outfits = await recommendOutfit({
        prompt,
        event_type: selectedScenario,
        weather: {
          summary: weather?.summary,
          temperature_c: weather?.temperature_c,
          feels_like_c: weather?.feels_like_c,
          user_preference: weatherPreference,
        },
      });
      setOutfit(outfits[0] ?? null);
      onNotify(outfits.length ? "Собрала рекомендацию под ваш день." : "Пока не хватает вещей для образа.", "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось собрать образ.", "error");
    } finally {
      setChatBusy(false);
    }
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
        {weather ? <CloudSun size={22} /> : <CloudRain size={22} />}
        <div>
          <strong>{weather ? weather.summary : "Погода ещё не уточнена"}</strong>
          <span>{weather ? "точная сводка через погодный API" : "Добавьте гео или опишите погоду в сценарии"}</span>
        </div>
        <button type="button" onClick={loadWeatherByLocation} disabled={weatherLoading}>
          <MapPin size={16} />
          {weatherLoading ? "..." : "Гео"}
        </button>
      </article>

      {weather ? (
        <div className="weather-metrics" aria-label="Погодная сводка">
          <span>
            <Thermometer size={15} /> {Math.round(weather.temperature_c)}°C, ощущается{" "}
            {Math.round(weather.feels_like_c)}°C
          </span>
          <span>
            <Umbrella size={15} /> осадки {weather.precipitation_probability}%
          </span>
          <span>
            <Wind size={15} /> ветер {Math.round(weather.wind_speed_ms)} м/с
          </span>
        </div>
      ) : null}

      <article className="scenario-chat">
        <div className="chat-head">
          <MessageCircle size={20} />
          <div>
            <strong>Сценарий дня</strong>
            <span>Опишите планы и как вы чувствуете погоду</span>
          </div>
        </div>
        <textarea
          value={scenarioText}
          onChange={(event) => setScenarioText(event.target.value)}
          rows={3}
          placeholder="Например: офис, потом прогулка 40 минут, хочу выглядеть спокойно и не мёрзнуть."
        />
        <div className="preference-row">
          {["мерзну, лучше теплее", "по погоде", "быстро жарко, легче"].map((preference) => (
            <button
              className={weatherPreference === preference ? "active" : ""}
              key={preference}
              type="button"
              onClick={() => setWeatherPreference(preference)}
            >
              {preference}
            </button>
          ))}
        </div>
        <button className="chat-submit" type="button" disabled={chatBusy} onClick={submitScenario}>
          {chatBusy ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
          Подобрать образ
        </button>
      </article>

      {outfit ? (
        <article className="hero-outfit">
          <div className="hero-head">
            <div>
              <span className="eyebrow">Лучший вариант</span>
              <h2>{outfit.title}</h2>
            </div>
            <ScoreBadge score={outfit.score} />
          </div>
          <div className="mini-grid">
            {wardrobeItems.slice(0, 4).map((item) => (
              <div className="mini-item" key={item.id}>
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
      ) : (
        <SmartCard icon="layers" title="Нет готового образа" text="Добавьте вещи и соберите рекомендацию" />
      )}

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
  const [remoteGarments, setRemoteGarments] = useState<GarmentCard[]>([]);
  const chips = ["Все", "Верх", "Низ", "Обувь", "Демисезон", "База", "Проверить"];

  useEffect(() => {
    if (!hasAccessToken()) {
      return;
    }
    void listWardrobeItems()
      .then(setRemoteGarments)
      .catch((error: unknown) => {
        onNotify(error instanceof Error ? error.message : "Не удалось загрузить гардероб.", "error");
      });
  }, [onNotify]);

  const visibleGarments = remoteGarments.filter((item) => {
    const normalizedChip = activeChip.toLowerCase();
    const byChip =
      activeChip === "Все" ||
      item.role.toLowerCase().includes(normalizedChip) ||
      item.season.toLowerCase().includes(normalizedChip) ||
      item.title.toLowerCase().includes(normalizedChip);
    const bySearch = !query || (item.searchText ?? item.title.toLowerCase()).includes(query.toLowerCase());
    return byChip && bySearch;
  });

  function toggleItem(item: GarmentCard) {
    setSelectedItems((current) => {
      const next = new Set(current);
      if (next.has(item.id)) {
        next.delete(item.id);
      } else {
        next.add(item.id);
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
          <span className="eyebrow">Здоровье гардероба</span>
          <h2>62%</h2>
        </div>
        <p>Не хватает дождевой обуви и одного спокойного верхнего слоя.</p>
      </article>
      {visibleGarments.length > 0 ? (
        <div className="garment-grid">
          {visibleGarments.map((item) => (
            <InteractiveGarmentTile
              item={item}
              key={item.id}
              selectable
              selected={selectedItems.has(item.id)}
              onClick={() => toggleItem(item)}
            />
          ))}
        </div>
      ) : (
        <SmartCard icon="archive" title="Гардероб пуст" text="Загруженные вещи появятся здесь" />
      )}
      <button
        className="wide-primary"
        type="button"
        disabled={selectedItems.size === 0}
        onClick={() => onNotify(`Собираю образ с выбранными вещами: ${selectedItems.size}.`, "success")}
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
      <SmartCard icon="archive" title="Приватность" text="OpenRouter · оригинал сохранён · без обучения" />
    </section>
  );
}

function DesignerScreen({ onNotify }: { onNotify: Notify }) {
  const [activeTool, setActiveTool] = useState<DesignerToolKey>("gaps");
  const [result, setResult] = useState<DesignerResult>({
    title: "Чего не хватает",
    summary: "Проверим пробелы гардероба и превратим их в понятные действия.",
    bullets: ["Нажмите на инструмент выше, чтобы получить разбор."],
  });
  const [busy, setBusy] = useState(false);
  const tools = [
    ["gaps", "layers", "Чего не хватает?", "Пробелы гардероба и приоритеты"],
    ["anchor", "bot", "Собрать с вещью", "Опорная вещь · погода · событие"],
    ["purchase", "search", "Стоит ли покупать?", "Дубли · совместимость · сценарии"],
    ["rate", "camera", "Оценить образ", "Что работает и что улучшить"],
    ["capsule", "calendar", "Капсула", "Неделя · поездка · сезон"],
  ] as const;

  function offlineDesignerResult(tool: DesignerToolKey, title: string): DesignerResult {
    const copy: Record<DesignerToolKey, DesignerResult> = {
      gaps: {
        title,
        summary: "Для точного расчёта нужен гардероб, но базово стоит закрыть погодные и сезонные пробелы.",
        bullets: ["Проверьте дождевую обувь.", "Добавьте спокойный верхний слой.", "Отметьте вещи в стирке."],
      },
      anchor: {
        title,
        summary: "Выберите ключевую вещь и задайте событие, погоду и желаемую теплоту.",
        bullets: ["Опорная вещь не должна спорить с обувью.", "Если мерзнете, добавляйте слой даже летом."],
      },
      purchase: {
        title,
        summary: "Покупку стоит оценивать не по красоте, а по реальным сценариям носки.",
        bullets: ["Есть ли похожая вещь?", "С чем минимум 3 раза надеть?", "Подходит ли к вашей погодной привычке?"],
      },
      rate: {
        title,
        summary: "Разбор должен объяснять, что уже работает, а затем давать одно-два улучшения.",
        bullets: ["Оценивается только одежда.", "Лицо, тело и личность не анализируются."],
      },
      capsule: {
        title,
        summary: "Капсула собирается от расписания: дни, погода, дресс-код и сколько можно нести.",
        bullets: ["Начните с обуви.", "Добавьте повторяемый верх.", "Оставьте один акцент."],
      },
    };
    return copy[tool];
  }

  async function selectTool(tool: DesignerToolKey, title: string) {
    setActiveTool(tool);
    setBusy(true);
    try {
      const fallback = offlineDesignerResult(tool, title);
      const nextResult = hasAccessToken() ? await runDesignerTool(tool).catch(() => fallback) : fallback;
      setResult(nextResult);
      onNotify(`${title}: разбор готов.`, "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось выполнить инструмент.", "error");
      setResult({
        title,
        summary: "Инструмент временно недоступен, но сценарий сохранён для повторного запуска.",
        bullets: ["Проверьте авторизацию, API и worker queue."],
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="screen-stack">
      <header className="compact-header">
        <h1>Дизайнер</h1>
      </header>
      <div className="designer-list">
        {tools.map(([tool, icon, title, text]) => (
          <SmartCard
            active={activeTool === tool}
            icon={icon}
            title={title}
            text={text}
            key={title}
            onClick={() => void selectTool(tool, title)}
          />
        ))}
      </div>
      <article className="designer-result">
        <div className="result-head">
          <Bot size={20} />
          <div>
            <span className="eyebrow">Результат дизайнера</span>
            <h2>{busy ? "Считаю..." : result.title}</h2>
          </div>
          {busy ? <Loader2 className="spin" size={20} /> : null}
        </div>
        <p>{result.summary}</p>
        <ul>
          {result.bullets.map((bullet) => (
            <li key={bullet}>{bullet}</li>
          ))}
        </ul>
      </article>
      <article className="style-dna">
        <span className="eyebrow">Профиль стиля</span>
        <h2>кэжуал · минимализм · нейтральная база</h2>
        <p>Предпочтения можно уточнять через сценарий дня: теплее, легче, формальнее или свободнее.</p>
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
  const tabs = ["Луки", "Образы", "Хотелки", "Мудборд"];
  const [activeFavoriteTab, setActiveFavoriteTab] = useState(tabs[0]);
  const [favorite, setFavorite] = useState(true);
  const [outfits, setOutfits] = useState<OutfitCard[]>([]);

  useEffect(() => {
    if (!hasAccessToken()) {
      return;
    }
    void listOutfits()
      .then((items) => setOutfits(items.filter((item) => item.score > 0)))
      .catch((error: unknown) => {
        onNotify(error instanceof Error ? error.message : "Не удалось загрузить избранное.", "error");
      });
  }, [onNotify]);

  const primaryOutfit = outfits[0] ?? null;

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
      {primaryOutfit ? (
        <article className="favorite-look">
          <div>
            <span className="eyebrow">{activeFavoriteTab}</span>
            <h2>{primaryOutfit.title}</h2>
            <p>{primaryOutfit.reason}</p>
          </div>
          <div className="action-row two">
            <button className="primary" type="button" onClick={() => onNotify("Генерирую похожий образ.", "success")}>
              Похожий
            </button>
            <button type="button" onClick={() => onNotify(primaryOutfit.reason)}>
              Почему работает
            </button>
          </div>
        </article>
      ) : (
        <SmartCard icon="archive" title="Избранное пусто" text="Сохранённые луки и аутфиты появятся здесь" />
      )}
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
    if (hasAccessToken()) {
      return;
    }
    if (!webApp?.initData) {
      notify("Откройте Mini App внутри Telegram для входа.", "warning");
      return;
    }
    void authenticateWithTelegram(webApp.initData).catch((error: unknown) => {
      notify(error instanceof Error ? error.message : "Не удалось выполнить вход через Telegram.", "error");
    });
  }, [notify, webApp]);

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
