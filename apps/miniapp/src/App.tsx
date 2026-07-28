import {
  type ChangeEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Bot,
  Check,
  CloudRain,
  CloudSun,
  Crop,
  Crown,
  Heart,
  Loader2,
  MapPin,
  MessageCircle,
  Redo2,
  RotateCcw,
  Ruler,
  ScanLine,
  Search,
  Send,
  Shirt,
  Sparkles,
  Ticket,
  Thermometer,
  Trash2,
  Undo2,
  Umbrella,
  Upload,
  Wind,
} from "lucide-react";

import {
  authenticateWithTelegram,
  createTryOn,
  deleteOutfit,
  deleteUpload,
  deleteWardrobeItem,
  evictItemImage,
  favoriteOutfit,
  generateAvatar,
  getAvatarImageObjectUrl,
  getAvatarProfile,
  getBillingAccess,
  getTryOn,
  getTryOnImageObjectUrl,
  getWardrobeHealth,
  getWardrobeItemImageObjectUrl,
  getWeather,
  getUploadStatus,
  hasAccessToken,
  listBillingPlans,
  listOutfits,
  listWardrobeItems,
  mapWithConcurrency,
  recommendOutfit,
  recommendWithAnchors,
  redeemPromoCode,
  retryUpload,
  revokeAvatarProfile,
  runDesignerTool,
  selectOutfit,
  sendDesignerChat,
  saveAvatarProfile,
  uploadPhoto,
} from "./api";
import { BottomNav, InteractiveGarmentTile, ScoreBadge, SectionHead, SmartCard } from "./components";
import { quickScenarios } from "./data";
import { confirmDialog, getHapticFeedback, getTelegramWebApp } from "./telegram";
import type {
  AvatarMeasurement,
  AvatarProfile,
  BillingAccess,
  BillingPlan,
  DesignerResult,
  DesignerToolKey,
  GarmentCard,
  ImageSelection,
  OutfitCard,
  TabKey,
  TryOnJob,
  UploadStatus,
  WardrobeHealth,
  WeatherSummary,
} from "./types";
import "./styles.css";

type Notify = (message: string, tone?: "info" | "success" | "warning" | "error") => void;
type UploadMode = "item" | "look" | "auto";

const uploadModes: Array<{ key: UploadMode; label: string }> = [
  { key: "item", label: "Вещь" },
  { key: "look", label: "Лук" },
  { key: "auto", label: "Авто" },
];

const MOSCOW = { latitude: 55.7558, longitude: 37.6173 };
const SUBSCRIPTIONS_UI_ENABLED = import.meta.env.VITE_SUBSCRIPTIONS_ENABLED !== "false";
const DEFAULT_PERSON_SELECTION: ImageSelection = {
  kind: "rectangle",
  source: "default",
  x: 0.18,
  y: 0.06,
  width: 0.64,
  height: 0.9,
};

function clampUnit(value: number): number {
  return Math.max(0, Math.min(1, value));
}

async function cropImageFile(file: File, selection: ImageSelection): Promise<File> {
  if (selection.kind === "full") {
    return file;
  }
  const imageUrl = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error("Не удалось прочитать изображение."));
      element.src = imageUrl;
    });
    const sourceX = Math.round(image.naturalWidth * selection.x);
    const sourceY = Math.round(image.naturalHeight * selection.y);
    const sourceWidth = Math.max(1, Math.round(image.naturalWidth * selection.width));
    const sourceHeight = Math.max(1, Math.round(image.naturalHeight * selection.height));
    const canvas = document.createElement("canvas");
    canvas.width = sourceWidth;
    canvas.height = sourceHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Редактор изображения недоступен в этом WebView.");
    }
    context.drawImage(image, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, sourceWidth, sourceHeight);
    const outputType = file.type === "image/png" || file.type === "image/webp" ? file.type : "image/jpeg";
    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (result) => (result ? resolve(result) : reject(new Error("Не удалось подготовить выделенную область."))),
        outputType,
        0.92,
      );
    });
    return new File([blob], `selection-${file.name}`, { type: outputType, lastModified: Date.now() });
  } finally {
    URL.revokeObjectURL(imageUrl);
  }
}

function TodayScreen({ onNotify, authReady }: { onNotify: Notify; authReady: boolean }) {
  const [outfit, setOutfit] = useState<OutfitCard | null>(null);
  const [wardrobeItems, setWardrobeItems] = useState<GarmentCard[]>([]);
  const [selectedScenario, setSelectedScenario] = useState("Много метро");
  const [scenarioText, setScenarioText] = useState("Много метро, вечером короткая встреча, хочу не замёрзнуть.");
  const [weatherPreference, setWeatherPreference] = useState("мерзну, лучше теплее");
  const [weather, setWeather] = useState<WeatherSummary | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [chatBusy, setChatBusy] = useState(false);
  const [chatReply, setChatReply] = useState<string | null>(null);
  const [tomorrowOutfit, setTomorrowOutfit] = useState<OutfitCard | null>(null);
  const [itemImages, setItemImages] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!authReady) {
      return;
    }
    void Promise.all([listOutfits(), listWardrobeItems()])
      .then(([outfits, items]) => {
        setOutfit(outfits[0] ?? null);
        setWardrobeItems(items);
        loadWeatherByLocation(true);
      })
      .catch((error: unknown) => {
        onNotify(error instanceof Error ? error.message : "Не удалось загрузить состояние.", "error");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authReady, onNotify]);

  const heroItemIds = (outfit?.items?.length ? outfit.items : wardrobeItems.map((item) => item.id)).slice(0, 4);

  useEffect(() => {
    if (!authReady) {
      return;
    }
    const missing = heroItemIds.filter((id) => !itemImages[id]);
    if (missing.length === 0) {
      return;
    }
    void Promise.all(
      missing.map(async (id) => [id, await getWardrobeItemImageObjectUrl(id)] as const),
    ).then((pairs) => {
      setItemImages((current) => {
        const next = { ...current };
        for (const [id, url] of pairs) {
          if (url) {
            next[id] = url;
          }
        }
        return next;
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authReady, heroItemIds.join(",")]);

  useEffect(() => {
    if (!weather?.tomorrow || !authReady) {
      return;
    }
    void recommendOutfit({
      prompt: `Предложи образ на завтра: ${weather.tomorrow.summary}. ${scenarioText}.`,
      event_type: "Завтра",
      weather: {
        summary: weather.tomorrow.summary,
        precipitation_probability: weather.tomorrow.precipitation_probability,
        user_preference: weatherPreference,
      },
      variants_count: 1,
    })
      .then((outfits) => setTomorrowOutfit(outfits[0] ?? null))
      .catch(() => setTomorrowOutfit(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authReady, weather]);

  function applyChatResult(reply: {
    reply: string;
    outfit_id?: string | null;
    outfit_title?: string | null;
    outfit_explanation?: string | null;
    outfit_score?: number | null;
    outfit_item_ids?: string[];
  }) {
    setChatReply(reply.reply);
    if (reply.outfit_id) {
      setOutfit({
        id: reply.outfit_id,
        title: reply.outfit_title ?? "Образ дня",
        context: "AI-дизайнер",
        score: Math.round(reply.outfit_score ?? 75),
        comfort: Math.round(reply.outfit_score ?? 75),
        items: reply.outfit_item_ids ?? [],
        reason: reply.outfit_explanation || reply.reply,
      });
    }
  }

  async function askDesigner(message: string, successNote: string) {
    if (!authReady) {
      onNotify("Откройте Mini App внутри Telegram, чтобы дизайнер видел ваш гардероб.", "warning");
      return;
    }
    setChatBusy(true);
    try {
      const response = await sendDesignerChat({
        message,
        scenario: selectedScenario,
        preferences: weatherPreference,
        weather_context: weather?.summary,
      });
      applyChatResult(response);
      onNotify(response.outfit_id ? successNote : "Дизайнер ответил — смотрите комментарий ниже.", "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "AI-дизайнер сейчас недоступен.", "error");
    } finally {
      setChatBusy(false);
    }
  }

  async function chooseOutfit() {
    if (!outfit) {
      return;
    }
    try {
      await selectOutfit(outfit.id);
      onNotify("Образ выбран и записан в историю носки.", "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось сохранить выбор образа.", "error");
    }
  }

  function makeWarmer() {
    void askDesigner(
      `Сделай образ теплее: ${outfit ? `текущий образ «${outfit.title}»` : "собери образ"}. Я мерзну сильнее обычного.`,
      "Собрала более тёплый вариант.",
    );
  }

  function anotherOutfit() {
    void askDesigner(
      `Собери другой вариант образа под сценарий: ${scenarioText || selectedScenario}. Предыдущий вариант не подошёл.`,
      "Собрала другой вариант.",
    );
  }

  function loadWeatherByLocation(silent = false) {
    if (!hasAccessToken()) {
      onNotify("Для точной погоды откройте Mini App внутри Telegram и войдите.", "warning");
      return;
    }
    const fallbackToMoscow = () => {
      void getWeather(MOSCOW.latitude, MOSCOW.longitude)
        .then((summary) => {
          setWeather(summary);
          onNotify("Гео недоступно — показываю погоду для Москвы. Нажмите «Гео», чтобы уточнить.", "warning");
        })
        .catch(() => {
          if (!silent) {
            onNotify("Не удалось получить погоду.", "error");
          }
        })
        .finally(() => setWeatherLoading(false));
    };
    if (!navigator.geolocation) {
      setWeatherLoading(true);
      fallbackToMoscow();
      return;
    }
    setWeatherLoading(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        void getWeather(position.coords.latitude, position.coords.longitude)
          .then((summary) => {
            setWeather(summary);
            if (!silent) {
              onNotify("Погода обновлена по текущей геолокации.", "success");
            }
          })
          .catch((error: unknown) => {
            onNotify(error instanceof Error ? error.message : "Не удалось получить погоду.", "error");
          })
          .finally(() => setWeatherLoading(false));
      },
      fallbackToMoscow,
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 900000 },
    );
  }

  async function submitScenario() {
    const prompt = scenarioText.trim();
    if (!prompt) {
      onNotify("Опишите сценарий дня: куда идёте, сколько ходить и насколько тепло хочется.", "warning");
      return;
    }
    await askDesigner(prompt, "Собрала рекомендацию под ваш день.");
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
        <button type="button" onClick={() => loadWeatherByLocation(false)} disabled={weatherLoading}>
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

      <article className="tomorrow-card">
        <span className="eyebrow">Завтра</span>
        <strong>{tomorrowOutfit?.title ?? "Автопредложение на завтра"}</strong>
        <p>
          {tomorrowOutfit?.reason ||
            weather?.tomorrow?.summary ||
            "Появится автоматически после входа и определения вашей геолокации."}
        </p>
      </article>

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
        {chatReply ? (
          <div className="chat-reply">
            <Bot size={16} />
            <p>{chatReply}</p>
          </div>
        ) : null}
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
            {heroItemIds.map((itemId) => (
              <div className="mini-item" key={itemId}>
                {itemImages[itemId] ? (
                  <img src={itemImages[itemId]} alt="Вещь образа" loading="lazy" />
                ) : (
                  <div className="swatch-denim" />
                )}
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

function WardrobeScreen({ onNotify, authReady }: { onNotify: Notify; authReady: boolean }) {
  const [activeChip, setActiveChip] = useState("Все");
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [remoteGarments, setRemoteGarments] = useState<GarmentCard[]>([]);
  const [health, setHealth] = useState<WardrobeHealth | null>(null);
  const [composeBusy, setComposeBusy] = useState(false);
  const chips = ["Все", "Верх", "Низ", "Обувь", "Верхний слой", "Платье", "Аксессуар", "Проверить"];

  useEffect(() => {
    if (!authReady) {
      return;
    }
    void Promise.all([listWardrobeItems(), getWardrobeHealth()])
      .then(([items, nextHealth]) => {
        setRemoteGarments(items);
        setHealth(nextHealth);
        // Max 3 image fetches at once: a full-grid burst starves other
        // requests (deletes included) behind the browser connection limit.
        return mapWithConcurrency(items, 3, async (item) => ({
          ...item,
          imageUrl: await getWardrobeItemImageObjectUrl(item.id),
        }));
      })
      .then(setRemoteGarments)
      .catch((error: unknown) => {
        onNotify(error instanceof Error ? error.message : "Не удалось загрузить гардероб.", "error");
      });
  }, [authReady, onNotify]);

  const visibleGarments = remoteGarments.filter((item) => {
    const normalizedChip = activeChip.toLowerCase();
    const needsReview = (item.confidence ?? 1) < 0.85 || item.status === "needs_confirmation";
    const byChip =
      activeChip === "Все" ||
      (activeChip === "Проверить"
        ? needsReview
        : item.role.toLowerCase().includes(normalizedChip) ||
          item.season.toLowerCase().includes(normalizedChip) ||
          item.title.toLowerCase().includes(normalizedChip));
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

  function requestDeleteItem(item: GarmentCard) {
    const proceed = (confirmed: boolean) => {
      if (!confirmed) {
        return;
      }
      // Optimistic removal: the card disappears at once and comes back on failure.
      setRemoteGarments((current) => current.filter((existing) => existing.id !== item.id));
      setSelectedItems((current) => {
        const next = new Set(current);
        next.delete(item.id);
        return next;
      });
      void deleteWardrobeItem(item.id)
        .then(() => {
          evictItemImage(item.id);
          onNotify(`«${item.title}» удалена из гардероба.`, "success");
        })
        .catch((error: unknown) => {
          setRemoteGarments((current) => [item, ...current]);
          onNotify(error instanceof Error ? error.message : "Не удалось удалить вещь.", "error");
        });
    };
    confirmDialog(`Удалить «${item.title}» из гардероба?`, proceed);
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
          <h2>{Math.round(health?.score ?? 0)}%</h2>
        </div>
        <p>{health?.missing_roles?.[0] ?? "Добавьте вещи, чтобы увидеть реальное покрытие гардероба."}</p>
        {health?.missing_roles?.length ? (
          <ul className="health-list">
            {health.missing_roles.slice(1, 4).map((role) => (
              <li key={role}>{role}</li>
            ))}
          </ul>
        ) : null}
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
              onDelete={() => requestDeleteItem(item)}
            />
          ))}
        </div>
      ) : (
        <SmartCard icon="archive" title="Гардероб пуст" text="Загруженные вещи появятся здесь" />
      )}
      <button
        className="wide-primary"
        type="button"
        disabled={selectedItems.size === 0 || composeBusy}
        onClick={() => {
          setComposeBusy(true);
          void recommendWithAnchors(Array.from(selectedItems))
            .then((outfits) => {
              const created = outfits[0];
              if (created) {
                onNotify(`Образ «${created.title}» создан — он на вкладках «Сегодня» и «Избранное».`, "success");
                setSelectedItems(new Set());
              } else {
                onNotify("Не удалось собрать образ из выбранных вещей.", "warning");
              }
            })
            .catch((error: unknown) => {
              onNotify(error instanceof Error ? error.message : "Не удалось собрать образ.", "error");
            })
            .finally(() => setComposeBusy(false));
        }}
      >
        {composeBusy ? "Собираю..." : "Собрать с выбранными"}
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

function AddScreen({
  onNotify,
  upload,
  onUploadChange,
}: {
  onNotify: Notify;
  upload: UploadStatus | null;
  onUploadChange: (upload: UploadStatus | null) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const selectionStageRef = useRef<HTMLDivElement | null>(null);
  const dragStartRef = useRef<{ x: number; y: number; before: ImageSelection } | null>(null);
  const [mode, setMode] = useState<UploadMode>("auto");
  const setUpload = onUploadChange;
  const [busy, setBusy] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectionMode, setSelectionMode] = useState<"region" | "full">("region");
  const [selection, setSelection] = useState<ImageSelection>(DEFAULT_PERSON_SELECTION);
  const [selectionHistory, setSelectionHistory] = useState<ImageSelection[]>([DEFAULT_PERSON_SELECTION]);
  const [selectionHistoryIndex, setSelectionHistoryIndex] = useState(0);

  useEffect(
    () => () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    },
    [previewUrl],
  );

  function resetEditor(file: File) {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setSelectionMode("region");
    setSelection(DEFAULT_PERSON_SELECTION);
    setSelectionHistory([DEFAULT_PERSON_SELECTION]);
    setSelectionHistoryIndex(0);
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    resetEditor(file);
    event.target.value = "";
    onNotify("Предложила область человека. Проверьте её перед распознаванием.", "info");
  }

  function pointFromPointer(event: ReactPointerEvent<HTMLDivElement>): { x: number; y: number } {
    const rect = selectionStageRef.current?.getBoundingClientRect();
    if (!rect) {
      return { x: 0, y: 0 };
    }
    return {
      x: clampUnit((event.clientX - rect.left) / rect.width),
      y: clampUnit((event.clientY - rect.top) / rect.height),
    };
  }

  function handleSelectionStart(event: ReactPointerEvent<HTMLDivElement>) {
    if (selectionMode !== "region") {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = pointFromPointer(event);
    dragStartRef.current = { ...point, before: selection };
    setSelection({
      kind: "rectangle",
      source: "user",
      x: point.x,
      y: point.y,
      width: 0.01,
      height: 0.01,
    });
  }

  function handleSelectionMove(event: ReactPointerEvent<HTMLDivElement>) {
    const start = dragStartRef.current;
    if (!start || selectionMode !== "region") {
      return;
    }
    const point = pointFromPointer(event);
    const x = Math.min(start.x, point.x);
    const y = Math.min(start.y, point.y);
    setSelection({
      kind: "rectangle",
      source: "user",
      x,
      y,
      width: Math.max(0.01, Math.abs(point.x - start.x)),
      height: Math.max(0.01, Math.abs(point.y - start.y)),
    });
  }

  function handleSelectionEnd() {
    if (!dragStartRef.current) {
      return;
    }
    dragStartRef.current = null;
    setSelectionHistory((current) => {
      const next = [...current.slice(0, selectionHistoryIndex + 1), selection];
      setSelectionHistoryIndex(next.length - 1);
      return next;
    });
  }

  function undoSelection() {
    const nextIndex = Math.max(0, selectionHistoryIndex - 1);
    setSelectionHistoryIndex(nextIndex);
    setSelection(selectionHistory[nextIndex]);
  }

  function redoSelection() {
    const nextIndex = Math.min(selectionHistory.length - 1, selectionHistoryIndex + 1);
    setSelectionHistoryIndex(nextIndex);
    setSelection(selectionHistory[nextIndex]);
  }

  function resetSelection() {
    setSelection(DEFAULT_PERSON_SELECTION);
    setSelectionHistory([DEFAULT_PERSON_SELECTION]);
    setSelectionHistoryIndex(0);
    onNotify("Вернула предложенную область человека.", "info");
  }

  function handleSelectionKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (selectionMode !== "region" || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      return;
    }
    event.preventDefault();
    const step = event.altKey ? 0.002 : 0.01;
    const next = { ...selection, source: "user" as const };
    if (event.shiftKey) {
      if (event.key === "ArrowLeft") {
        next.width = Math.max(0.01, next.width - step);
      } else if (event.key === "ArrowRight") {
        next.width = Math.min(1 - next.x, next.width + step);
      } else if (event.key === "ArrowUp") {
        next.height = Math.max(0.01, next.height - step);
      } else {
        next.height = Math.min(1 - next.y, next.height + step);
      }
    } else if (event.key === "ArrowLeft") {
      next.x = Math.max(0, next.x - step);
    } else if (event.key === "ArrowRight") {
      next.x = Math.min(1 - next.width, next.x + step);
    } else if (event.key === "ArrowUp") {
      next.y = Math.max(0, next.y - step);
    } else {
      next.y = Math.min(1 - next.height, next.y + step);
    }
    setSelection(next);
    setSelectionHistory((current) => {
      const history = [...current.slice(0, selectionHistoryIndex + 1), next];
      setSelectionHistoryIndex(history.length - 1);
      return history;
    });
  }

  async function submitPhoto() {
    if (!selectedFile) {
      return;
    }
    setBusy(true);
    try {
      const confirmedSelection: ImageSelection =
        selectionMode === "full"
          ? { kind: "full", source: "user", x: 0, y: 0, width: 1, height: 1 }
          : selection;
      const uploadFile = await cropImageFile(selectedFile, confirmedSelection);
      const nextUpload = await uploadPhoto(uploadFile, mode, confirmedSelection);
      setUpload(nextUpload);
      setSelectedFile(null);
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        setPreviewUrl(null);
      }
      onNotify("Фото принято. Обработка идёт в фоне — можно переключать вкладки.", "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось загрузить фото.", "error");
    } finally {
      setBusy(false);
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
      <input ref={inputRef} className="file-input" type="file" accept="image/*" onChange={handleFileChange} />
      {selectedFile && previewUrl ? (
        <article className="selection-editor">
          <div className="selection-head">
            <div>
              <span className="eyebrow">Контроль распознавания</span>
              <h2>Что добавить в гардероб?</h2>
            </div>
            <ScanLine size={24} />
          </div>
          <p className="selection-copy">
            Я предложила область человека. Обведите пальцем только нужный лук, чтобы вещи на фоне не попали в анализ.
          </p>
          <div className="selection-mode" role="group" aria-label="Область распознавания">
            <button
              className={selectionMode === "region" ? "active" : ""}
              type="button"
              onClick={() => setSelectionMode("region")}
            >
              <Crop size={16} /> Только область
            </button>
            <button
              className={selectionMode === "full" ? "active" : ""}
              type="button"
              onClick={() => setSelectionMode("full")}
            >
              <Check size={16} /> Всё фото
            </button>
          </div>
          <div
            ref={selectionStageRef}
            className={`selection-stage${selectionMode === "full" ? " full" : ""}`}
            onPointerDown={handleSelectionStart}
            onPointerMove={handleSelectionMove}
            onPointerUp={handleSelectionEnd}
            onPointerCancel={handleSelectionEnd}
            onKeyDown={handleSelectionKeyDown}
            role="group"
            tabIndex={selectionMode === "region" ? 0 : -1}
            aria-label={
              selectionMode === "region"
                ? "Интерактивное фото с выделенной областью. Проведите пальцем или мышью; стрелки двигают область, Shift и стрелки меняют размер."
                : "В распознавание попадёт всё фото."
            }
          >
            <img src={previewUrl} alt="" draggable={false} />
            {selectionMode === "region" ? (
              <span
                className="selection-box"
                style={{
                  left: `${selection.x * 100}%`,
                  top: `${selection.y * 100}%`,
                  width: `${selection.width * 100}%`,
                  height: `${selection.height * 100}%`,
                }}
              >
                <span>Распознать здесь</span>
              </span>
            ) : null}
          </div>
          <div className="editor-toolbar" aria-label="История выделения">
            <button type="button" onClick={undoSelection} disabled={selectionHistoryIndex === 0}>
              <Undo2 size={17} /> Назад
            </button>
            <button
              type="button"
              onClick={redoSelection}
              disabled={selectionHistoryIndex >= selectionHistory.length - 1}
            >
              <Redo2 size={17} /> Вперёд
            </button>
            <button type="button" onClick={resetSelection}>
              <RotateCcw size={17} /> Сброс
            </button>
          </div>
          <button className="wide-primary" type="button" disabled={busy} onClick={submitPhoto}>
            {busy ? <Loader2 className="spin" size={18} /> : <ScanLine size={18} />}
            {selectionMode === "region" ? "Распознать выделенное" : "Распознать всё фото"}
          </button>
          <button className="change-photo" type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
            Выбрать другое фото
          </button>
        </article>
      ) : (
        <article className="upload-card">
          {busy ? <Loader2 className="spin" size={30} /> : <Upload size={30} />}
          <h2>Фото вещи или лука</h2>
          <p>Перед анализом вы сможете исключить манекены, вешалки и людей на фоне</p>
          <button className="primary" type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
            {busy ? "Загружаю..." : "Выбрать фото"}
          </button>
        </article>
      )}
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
          <div
            className="progress-track"
            role="progressbar"
            aria-label="Статус обработки"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.max(0, Math.min(upload.progress, 100))}
          >
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
      <SmartCard icon="archive" title="Приватность" text="AI-анализ · оригинал сохранён · без обучения" />
    </section>
  );
}

const designerQuickPrompts: Array<{ label: string; message: string; tool?: "gaps" }> = [
  { label: "Чего не хватает?", tool: "gaps", message: "Каких вещей не хватает моему гардеробу?" },
  { label: "Собрать образ", message: "Собери образ из моего гардероба на сегодня. Если нужно что-то уточнить — спроси меня." },
  {
    label: "Стоит ли покупать?",
    message: "Я думаю о покупке новой вещи. Задай мне уточняющие вопросы и помоги решить, стоит ли покупать.",
  },
  {
    label: "Оценить образ",
    message: "Оцени образ, который я опишу: что уже работает и что можно улучшить. Оценивай только одежду.",
  },
  { label: "Капсула на неделю", message: "Собери капсулу на неделю из моего гардероба: сочетания на каждый день." },
];

function DesignerScreen({ onNotify }: { onNotify: Notify }) {
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const chatLogRef = useRef<HTMLDivElement | null>(null);
  const [chatMessages, setChatMessages] = useState<Array<{ role: "user" | "assistant"; text: string }>>([
    {
      role: "assistant",
      text: "Я ваш AI-стилист и помню ваш гардероб. Спросите про образ, покупку или конкретную вещь — детали вроде погоды не обязательны, если нужно, я уточню сама.",
    },
  ]);

  useEffect(() => {
    chatLogRef.current?.scrollTo({ top: chatLogRef.current.scrollHeight });
  }, [chatMessages, chatBusy]);

  function pushMessage(role: "user" | "assistant", text: string) {
    setChatMessages((current) => [...current, { role, text }]);
  }

  async function submitToDesigner(shownText: string, message: string, tool?: "gaps") {
    if (chatBusy) {
      return;
    }
    if (!hasAccessToken()) {
      onNotify("Откройте Mini App внутри Telegram, чтобы дизайнер видел ваш гардероб.", "warning");
      return;
    }
    pushMessage("user", shownText);
    setChatBusy(true);
    try {
      if (tool === "gaps") {
        const result = await runDesignerTool("gaps");
        pushMessage("assistant", [result.summary, ...result.bullets.map((bullet) => `• ${bullet}`)].join("\n"));
      } else {
        const response = await sendDesignerChat({ message });
        const outfitNote = response.outfit_id
          ? `\n\nОбраз «${response.outfit_title}» сохранён — он на вкладках «Сегодня» и «Избранное».`
          : "";
        pushMessage("assistant", response.reply + outfitNote);
      }
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Дизайнер сейчас недоступен.", "error");
      pushMessage("assistant", "Не получилось получить ответ. Попробуйте ещё раз чуть позже.");
    } finally {
      setChatBusy(false);
    }
  }

  async function sendChatMessage() {
    const message = chatInput.trim();
    if (!message) {
      onNotify("Напишите вопрос дизайнеру.", "warning");
      return;
    }
    setChatInput("");
    await submitToDesigner(message, message);
  }

  return (
    <section className="screen-stack designer-screen">
      <header className="compact-header">
        <h1>Дизайнер</h1>
      </header>
      <article className="designer-chat-panel tall">
        <div className="chat-head">
          <Bot size={20} />
          <div>
            <strong>AI-стилист</strong>
            <span>Помнит ваш гардероб · уточнит детали сам, если нужно</span>
          </div>
        </div>
        <div className="chat-log" ref={chatLogRef}>
          {chatMessages.map((message, index) => (
            <p className={message.role} key={`${message.role}-${index}`}>
              {message.text}
            </p>
          ))}
          {chatBusy ? <p className="assistant thinking">Думаю…</p> : null}
        </div>
        <div className="chip-row designer-chips">
          {designerQuickPrompts.map((prompt) => (
            <button
              type="button"
              key={prompt.label}
              disabled={chatBusy}
              onClick={() => void submitToDesigner(prompt.label, prompt.message, prompt.tool)}
            >
              {prompt.label}
            </button>
          ))}
        </div>
        <textarea
          value={chatInput}
          onChange={(event) => setChatInput(event.target.value)}
          rows={2}
          placeholder="Спросите как в обычном чате: образ, покупка, конкретная вещь…"
        />
        <button className="chat-submit" type="button" disabled={chatBusy} onClick={() => void sendChatMessage()}>
          {chatBusy ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
          Отправить
        </button>
      </article>
    </section>
  );
}

function FavoritesScreen({ onNotify, authReady }: { onNotify: Notify; authReady: boolean }) {
  const tabs = ["Все образы", "Избранные"];
  const [activeFavoriteTab, setActiveFavoriteTab] = useState(tabs[0]);
  const [outfits, setOutfits] = useState<OutfitCard[]>([]);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());
  const [itemImages, setItemImages] = useState<Record<string, string>>({});
  const [similarBusy, setSimilarBusy] = useState(false);

  useEffect(() => {
    if (!authReady) {
      return;
    }
    void listOutfits()
      .then((items) => {
        setOutfits(items);
        setFavoriteIds(new Set(items.filter((item) => item.favorite).map((item) => item.id)));
      })
      .catch((error: unknown) => {
        onNotify(error instanceof Error ? error.message : "Не удалось загрузить избранное.", "error");
      });
  }, [authReady, onNotify]);

  useEffect(() => {
    if (!authReady || outfits.length === 0) {
      return;
    }
    const itemIds = Array.from(new Set(outfits.flatMap((outfit) => outfit.items))).filter(
      (itemId) => !itemImages[itemId],
    );
    if (itemIds.length === 0) {
      return;
    }
    let cancelled = false;
    void mapWithConcurrency(itemIds, 3, async (itemId) => {
      try {
        return [itemId, await getWardrobeItemImageObjectUrl(itemId)] as const;
      } catch {
        return [itemId, undefined] as const;
      }
    }).then((entries) => {
      if (!cancelled) {
        setItemImages((current) => ({
          ...current,
          ...Object.fromEntries(entries.filter((entry): entry is readonly [string, string] => Boolean(entry[1]))),
        }));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [authReady, itemImages, outfits]);

  const visibleOutfits = (
    activeFavoriteTab === "Избранные" ? outfits.filter((outfit) => favoriteIds.has(outfit.id)) : outfits
  ).slice(0, 10);

  async function toggleFavorite(outfit: OutfitCard) {
    try {
      await favoriteOutfit(outfit.id);
      setFavoriteIds((current) => new Set(current).add(outfit.id));
      onNotify(`«${outfit.title}» в избранном.`, "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось сохранить в избранное.", "error");
    }
  }

  function requestDeleteOutfit(outfit: OutfitCard) {
    const proceed = (confirmed: boolean) => {
      if (!confirmed) {
        return;
      }
      void deleteOutfit(outfit.id)
        .then(() => {
          setOutfits((current) => current.filter((existing) => existing.id !== outfit.id));
          setFavoriteIds((current) => {
            const next = new Set(current);
            next.delete(outfit.id);
            return next;
          });
          onNotify(`Образ «${outfit.title}» удалён.`, "success");
        })
        .catch((error: unknown) => {
          onNotify(error instanceof Error ? error.message : "Не удалось удалить образ.", "error");
        });
    };
    confirmDialog(`Удалить образ «${outfit.title}»?`, proceed);
  }

  async function similarOutfit(outfit: OutfitCard) {
    setSimilarBusy(true);
    try {
      const response = await sendDesignerChat({
        message: `Собери похожий образ на «${outfit.title}», но с другими акцентами. Обоснование прежнего: ${outfit.reason}`,
      });
      onNotify(response.outfit_id ? `Готово: «${response.outfit_title}».` : response.reply, "success");
      if (response.outfit_id) {
        const refreshed = await listOutfits();
        setOutfits(refreshed);
      }
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось собрать похожий образ.", "error");
    } finally {
      setSimilarBusy(false);
    }
  }

  return (
    <section className="screen-stack">
      <header className="compact-header">
        <h1>Избранное</h1>
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
      {visibleOutfits.length > 0 ? (
        visibleOutfits.map((outfit) => (
          <article className="favorite-look" key={outfit.id}>
            <div>
              <div className="favorite-head">
                <h2>{outfit.title}</h2>
                <div className="favorite-actions">
                  <button
                    className={favoriteIds.has(outfit.id) ? "round-button active" : "round-button"}
                    type="button"
                    aria-label="В избранное"
                    onClick={() => void toggleFavorite(outfit)}
                  >
                    <Heart size={18} />
                  </button>
                  <button
                    className="round-button"
                    type="button"
                    aria-label={`Удалить образ «${outfit.title}»`}
                    onClick={() => requestDeleteOutfit(outfit)}
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
              <p>{outfit.reason}</p>
            </div>
            {outfit.items.length > 0 ? (
              <div
                className={`look-collage items-${Math.min(outfit.items.length, 4)}`}
                aria-label={`Вещи образа «${outfit.title}»`}
              >
                {outfit.items.slice(0, 4).map((itemId) => (
                  <span key={itemId}>
                    {itemImages[itemId] ? (
                      <img src={itemImages[itemId]} alt="" loading="lazy" />
                    ) : (
                      <Shirt aria-hidden="true" size={26} strokeWidth={1.6} />
                    )}
                  </span>
                ))}
              </div>
            ) : null}
            <div className="action-row two">
              <button
                className="primary"
                type="button"
                disabled={similarBusy}
                onClick={() => void similarOutfit(outfit)}
              >
                {similarBusy ? "Собираю..." : "Похожий"}
              </button>
              <button type="button" onClick={() => onNotify(outfit.reason)}>
                Почему работает
              </button>
            </div>
          </article>
        ))
      ) : (
        <SmartCard
          icon="archive"
          title={activeFavoriteTab === "Избранные" ? "Избранных пока нет" : "Образов пока нет"}
          text="Соберите образ на вкладке «Сегодня» и отметьте сердечком"
        />
      )}
    </section>
  );
}

const featureLabels: Record<string, string> = {
  selection_editor: "Редактор области",
  basic_outfits: "Базовые образы",
  basic_weather: "Погода",
  limited_research: "Ограниченный AI-анализ",
  avatar_try_on: "Персональный аватар и примерка",
  full_research: "Полный AI-анализ",
  look_analysis: "Разбор луков",
  unlimited_favorites: "Избранное без лимита",
  wardrobe_analytics: "Аналитика гардероба",
  priority_queue: "Приоритетная обработка",
  multi_wardrobe: "Несколько гардеробов",
  export: "Экспорт",
  capsules: "Капсулы",
  trip_packing: "Сборы в поездку",
  stylist_mode: "Режим стилиста",
};

const pricingStatusLabels: Record<string, string> = {
  proposed: "Предварительная цена",
  validated: "Цена подтверждена",
};

const previewBillingPlans: BillingPlan[] = [
  {
    code: "free",
    title: "Free",
    monthly_price: 0,
    currency: "RUB",
    item_limit: 20,
    ai_analysis_limit: 5,
    avatar_generation_limit: 0,
    try_on_limit: 0,
    features: ["selection_editor", "basic_outfits", "basic_weather", "limited_research"],
    pricing_status: "предварительная цена",
  },
  {
    code: "premium",
    title: "Premium",
    monthly_price: 699,
    currency: "RUB",
    item_limit: 500,
    ai_analysis_limit: 100,
    avatar_generation_limit: 2,
    try_on_limit: 6,
    features: [
      "avatar_try_on",
      "full_research",
      "look_analysis",
      "unlimited_favorites",
      "wardrobe_analytics",
      "priority_queue",
    ],
    pricing_status: "предварительная цена",
  },
  {
    code: "pro",
    title: "Pro",
    monthly_price: 1490,
    currency: "RUB",
    item_limit: null,
    ai_analysis_limit: null,
    avatar_generation_limit: 5,
    try_on_limit: 15,
    features: ["avatar_try_on", "multi_wardrobe", "export", "capsules", "trip_packing", "stylist_mode"],
    pricing_status: "предварительная цена",
  },
];

function StudioScreen({
  onNotify,
  authReady,
  lastUploadId,
}: {
  onNotify: Notify;
  authReady: boolean;
  lastUploadId?: string;
}) {
  const [plans, setPlans] = useState<BillingPlan[]>(previewBillingPlans);
  const [access, setAccess] = useState<BillingAccess | null>(null);
  const [profile, setProfile] = useState<AvatarProfile | null>(null);
  const [garments, setGarments] = useState<GarmentCard[]>([]);
  const [selectedGarments, setSelectedGarments] = useState<Set<string>>(new Set());
  const [description, setDescription] = useState("");
  const [height, setHeight] = useState("");
  const [waist, setWaist] = useState("");
  const [hips, setHips] = useState("");
  const [consent, setConsent] = useState(false);
  const [promoCode, setPromoCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [tryOn, setTryOn] = useState<TryOnJob | null>(null);
  const [avatarImage, setAvatarImage] = useState<string | undefined>();
  const [tryOnImage, setTryOnImage] = useState<string | undefined>();

  useEffect(() => {
    if (!SUBSCRIPTIONS_UI_ENABLED) {
      return;
    }
    void listBillingPlans()
      .then(setPlans)
      .catch(() => {
        // The public catalog remains useful in a visual preview while the API is unavailable.
      });
  }, []);

  useEffect(() => {
    if (!authReady) {
      return;
    }
    void Promise.all([getBillingAccess(), getAvatarProfile(), listWardrobeItems()])
      .then(([nextAccess, nextProfile, nextGarments]) => {
        setAccess(nextAccess);
        setProfile(nextProfile);
        setGarments(nextGarments);
        if (nextProfile) {
          setDescription(nextProfile.description ?? "");
          setConsent(Boolean(nextProfile.consented_at && !nextProfile.revoked_at));
          const values = Object.fromEntries(
            nextProfile.measurements.map((measurement) => [measurement.code, String(measurement.value)]),
          );
          setHeight(values.height ?? "");
          setWaist(values.waist ?? "");
          setHips(values.hips ?? "");
        }
      })
      .catch((error: unknown) => {
        onNotify(error instanceof Error ? error.message : "Не удалось загрузить AI-студию.", "error");
      });
  }, [authReady, onNotify]);

  useEffect(() => {
    if (!profile || !["queued", "processing"].includes(profile.status)) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void getAvatarProfile().then((nextProfile) => {
        if (nextProfile) {
          setProfile(nextProfile);
        }
      });
    }, 2500);
    return () => window.clearInterval(timer);
  }, [profile]);

  useEffect(() => {
    if (!profile?.generated_image_id || profile.status !== "completed") {
      return;
    }
    void getAvatarImageObjectUrl().then(setAvatarImage);
  }, [profile?.generated_image_id, profile?.status]);

  useEffect(
    () => () => {
      if (avatarImage) {
        URL.revokeObjectURL(avatarImage);
      }
    },
    [avatarImage],
  );

  useEffect(() => {
    if (!tryOn || !["queued", "processing"].includes(tryOn.status)) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void getTryOn(tryOn.id).then(setTryOn);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [tryOn]);

  useEffect(() => {
    if (!tryOn?.output_image_id || tryOn.status !== "completed") {
      return;
    }
    void getTryOnImageObjectUrl(tryOn.id).then(setTryOnImage);
  }, [tryOn?.id, tryOn?.output_image_id, tryOn?.status]);

  useEffect(
    () => () => {
      if (tryOnImage) {
        URL.revokeObjectURL(tryOnImage);
      }
    },
    [tryOnImage],
  );

  function measurement(code: AvatarMeasurement["code"], rawValue: string): AvatarMeasurement | null {
    const value = Number(rawValue);
    return Number.isFinite(value) && value > 0 ? { code, value, unit: "cm" } : null;
  }

  async function saveProfile() {
    if (!consent) {
      onNotify("Подтвердите согласие на создание и хранение аватара.", "warning");
      return;
    }
    setBusy(true);
    try {
      const measurements = [
        measurement("height", height),
        measurement("waist", waist),
        measurement("hips", hips),
      ].filter((value): value is AvatarMeasurement => value !== null);
      const nextProfile = await saveAvatarProfile({
        consent: true,
        description: description.trim() || undefined,
        reference_upload_id: lastUploadId,
        measurements,
      });
      setProfile(nextProfile);
      onNotify(
        lastUploadId || nextProfile.reference_image_id
          ? "Профиль и согласие сохранены."
          : "Профиль сохранён. Загрузите фото, чтобы создать аватар.",
        "success",
      );
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось сохранить профиль.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function startAvatarGeneration() {
    setBusy(true);
    try {
      const nextProfile = await generateAvatar();
      setProfile(nextProfile);
      if (nextProfile.generation_error === "provider_not_configured") {
        onNotify("Провайдер генерации не настроен. Профиль сохранён, фальшивый результат не создан.", "warning");
      } else {
        onNotify("Создание аватара запущено.", "success");
      }
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось запустить создание аватара.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function activatePromo() {
    if (!promoCode.trim()) {
      onNotify("Введите промокод.", "warning");
      return;
    }
    setBusy(true);
    try {
      const redemption = await redeemPromoCode(promoCode);
      setAccess(await getBillingAccess());
      setPromoCode("");
      onNotify(`Premium открыт до ${new Date(redemption.expires_at).toLocaleString("ru-RU")}.`, "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Промокод не активирован.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function startTryOn() {
    if (selectedGarments.size === 0) {
      onNotify("Выберите хотя бы одну вещь.", "warning");
      return;
    }
    setBusy(true);
    try {
      const nextJob = await createTryOn([...selectedGarments]);
      setTryOn(nextJob);
      if (nextJob.error_code === "provider_not_configured") {
        onNotify("Провайдер примерки не настроен; задача сохранена как недоступная, без mock-картинки.", "warning");
      } else {
        onNotify("Виртуальная примерка запущена.", "success");
      }
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось запустить примерку.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function revokeProfile() {
    const confirmed = await new Promise<boolean>((resolve) =>
      confirmDialog("Отозвать согласие и удалить связи с фото и аватаром?", resolve),
    );
    if (!confirmed) {
      return;
    }
    setBusy(true);
    try {
      await revokeAvatarProfile();
      setProfile(null);
      setConsent(false);
      setAvatarImage(undefined);
      setTryOn(null);
      setTryOnImage(undefined);
      onNotify("Согласие отозвано, ссылки на лицо и аватар удалены.", "success");
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Не удалось отозвать согласие.", "error");
    } finally {
      setBusy(false);
    }
  }

  const hasAvatarAccess =
    authReady && (!SUBSCRIPTIONS_UI_ENABLED || !access?.enabled || access.features.includes("avatar_try_on"));

  return (
    <section className="screen-stack studio-screen">
      <header className="compact-header">
        <div>
          <span className="eyebrow">AI-студия</span>
          <h1>Аватар и примерка</h1>
        </div>
        <Crown size={24} />
      </header>

      {SUBSCRIPTIONS_UI_ENABLED ? (
        <>
          {access ? (
            <article className="access-card">
              <div>
                <span className="eyebrow">Ваш доступ</span>
                <h2>{access.plan === "free" ? "Free" : access.plan === "premium" ? "Premium" : "Pro"}</h2>
                <p>
                  {access.source === "promo" && access.expires_at
                    ? `Промодоступ до ${new Date(access.expires_at).toLocaleString("ru-RU")}`
                    : access.source === "subscription"
                      ? "Активная подписка"
                      : "Базовый тариф"}
                </p>
              </div>
              <Crown size={28} />
            </article>
          ) : (
            <SmartCard
              icon="layers"
              title="Войдите через Telegram"
              text="Тарифы можно сравнить сейчас. Активация промокода и AI-студия откроются после безопасной авторизации."
            />
          )}
          <div className="plan-grid">
            {plans.map((plan) => (
              <article className={`plan-card${plan.code === "premium" ? " featured" : ""}`} key={plan.code}>
                <span className="eyebrow">
                  {plan.code === "premium"
                    ? "Рекомендуем"
                    : (pricingStatusLabels[plan.pricing_status] ?? plan.pricing_status)}
                </span>
                <h3>{plan.title}</h3>
                <strong>
                  {plan.monthly_price === 0 ? "Бесплатно" : `${plan.monthly_price.toLocaleString("ru-RU")} ₽/мес`}
                </strong>
                <p className="plan-limits">
                  {plan.ai_analysis_limit === null ? "AI-анализ без лимита" : `${plan.ai_analysis_limit} AI-анализов`}
                  {plan.try_on_limit > 0 ? ` · ${plan.try_on_limit} примерок` : ""}
                  {plan.avatar_generation_limit > 0 ? ` · ${plan.avatar_generation_limit} аватара` : ""}
                </p>
                <ul>
                  {plan.features.slice(0, 5).map((feature) => (
                    <li key={feature}>
                      <Check size={14} /> {featureLabels[feature] ?? feature}
                    </li>
                  ))}
                </ul>
                <button type="button" disabled={!access?.payments_enabled || plan.code === access?.plan}>
                  {plan.code === access?.plan ? "Текущий" : access?.payments_enabled ? "Выбрать" : "Оплата скоро"}
                </button>
              </article>
            ))}
          </div>
          <article className="promo-card">
            <Ticket size={22} />
            <div>
              <strong>Есть промокод?</strong>
              <span>Активация и срок проверяются на сервере</span>
            </div>
            <input
              value={promoCode}
              onChange={(event) => setPromoCode(event.target.value)}
              placeholder="AW-…"
              autoCapitalize="characters"
              aria-label="Промокод"
              disabled={!authReady}
            />
            <button type="button" disabled={busy || !authReady} onClick={activatePromo}>
              Активировать
            </button>
          </article>
        </>
      ) : (
        <SmartCard
          icon="layers"
          title="Открытый режим"
          text="Paywall отключён сборкой; AI-студия доступна без подписочного интерфейса."
        />
      )}

      <article className={`avatar-card${hasAvatarAccess ? "" : " locked"}`}>
        <div className="selection-head">
          <div>
            <span className="eyebrow">Персональный манекен</span>
            <h2>Ваши пропорции — без «улучшения»</h2>
          </div>
          <Ruler size={24} />
        </div>
        {avatarImage ? (
          <img className="avatar-preview" src={avatarImage} alt="Сгенерированный персональный аватар" />
        ) : (
          <div className="avatar-placeholder">
            <Sparkles size={34} />
            <strong>{profile?.status === "queued" || profile?.status === "processing" ? "Создаю аватар…" : "Аватар ещё не создан"}</strong>
            <span>Нейтральный фон · закрытый серый лонгслив · легинсы по фигуре</span>
          </div>
        )}
        {!hasAvatarAccess ? (
          <p className="premium-note">
            {authReady ? "Функция доступна в Premium или по промокоду." : "Откройте приложение в Telegram, чтобы продолжить."}
          </p>
        ) : (
          <>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Нейтральное описание внешности и особенностей, которые важно сохранить"
              rows={3}
            />
            <div className="measurement-grid">
              {[
                ["Рост", height, setHeight],
                ["Талия", waist, setWaist],
                ["Бёдра", hips, setHips],
              ].map(([label, value, setter]) => (
                <label key={String(label)}>
                  <span>{String(label)}, см</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    min="1"
                    max="300"
                    value={String(value)}
                    onChange={(event) => (setter as (nextValue: string) => void)(event.target.value)}
                  />
                </label>
              ))}
            </div>
            <label className="consent-row">
              <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
              <span>
                Я согласен(на) на обработку пропорций и использование последнего загруженного фото как приватного
                референса. Согласие можно отозвать.
              </span>
            </label>
            <p className="privacy-hint">
              {lastUploadId
                ? "Будет использовано последнее загруженное фото."
                : profile?.reference_image_id
                  ? "Приватный референс уже сохранён."
                  : "Сначала загрузите подходящее фото во вкладке «Добавить»."}
            </p>
            <div className="action-row two">
              <button type="button" disabled={busy} onClick={saveProfile}>
                Сохранить профиль
              </button>
              <button
                className="primary"
                type="button"
                disabled={busy || !profile?.reference_image_id || !consent}
                onClick={startAvatarGeneration}
              >
                Создать аватар
              </button>
            </div>
            {profile ? (
              <button className="danger-link" type="button" disabled={busy} onClick={revokeProfile}>
                Отозвать согласие и удалить аватар
              </button>
            ) : null}
          </>
        )}
      </article>

      <article className={`try-on-card${hasAvatarAccess ? "" : " locked"}`}>
        <div className="selection-head">
          <div>
              <span className="eyebrow">Виртуальная примерка</span>
            <h2>Примерить вещи</h2>
          </div>
          <Sparkles size={24} />
        </div>
        {tryOnImage ? (
          <img className="avatar-preview" src={tryOnImage} alt="Результат виртуальной примерки" />
        ) : (
          <p className="selection-copy">
            Выберите вещи. Генерация сохраняет лицо и пропорции, но не гарантирует физическую посадку и размер.
          </p>
        )}
        <div className="studio-garments">
          {garments.slice(0, 12).map((garment) => (
            <button
              className={selectedGarments.has(garment.id) ? "active" : ""}
              type="button"
              key={garment.id}
              disabled={!hasAvatarAccess}
              onClick={() =>
                setSelectedGarments((current) => {
                  const next = new Set(current);
                  if (next.has(garment.id)) {
                    next.delete(garment.id);
                  } else if (next.size < 8) {
                    next.add(garment.id);
                  }
                  return next;
                })
              }
            >
              <Check size={14} /> {garment.title}
            </button>
          ))}
        </div>
        <button
          className="wide-primary"
          type="button"
          disabled={busy || !hasAvatarAccess || profile?.status !== "completed" || selectedGarments.size === 0}
          onClick={startTryOn}
        >
          {busy || ["queued", "processing"].includes(tryOn?.status ?? "") ? (
            <Loader2 className="spin" size={18} />
          ) : (
            <Sparkles size={18} />
          )}
          Сгенерировать примерку
        </button>
        {tryOn?.error_code ? <p className="error-copy">Генерация недоступна: {tryOn.error_code}</p> : null}
      </article>
    </section>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("today");
  const [toast, setToast] = useState<{ message: string; tone: string } | null>(null);
  const [authReady, setAuthReady] = useState(hasAccessToken());
  const [upload, setUpload] = useState<UploadStatus | null>(null);
  const webApp = useMemo(() => getTelegramWebApp(), []);
  const hapticFeedback = useMemo(() => getHapticFeedback(webApp), [webApp]);

  const notify = useMemo<Notify>(
    () => (message, tone = "info") => {
      setToast({ message, tone });
      if (tone === "success") {
        hapticFeedback?.notificationOccurred("success");
      } else if (tone === "error") {
        hapticFeedback?.notificationOccurred("error");
      } else {
        hapticFeedback?.impactOccurred("light");
      }
      window.setTimeout(() => setToast(null), 2800);
    },
    [hapticFeedback],
  );

  useEffect(() => {
    webApp?.ready();
    webApp?.expand();
  }, [webApp]);

  // The poll lives at App level so switching tabs never interrupts an upload.
  useEffect(() => {
    if (!upload || upload.status === "completed" || upload.status === "failed") {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void getUploadStatus(upload.id)
        .then((nextUpload) => {
          setUpload(nextUpload);
          if (nextUpload.status === "completed") {
            notify("Фото обработано, карточки готовы — смотрите «Гардероб».", "success");
          } else if (nextUpload.status === "failed") {
            notify("Обработка фото не удалась. Откройте «Добавить», чтобы повторить.", "error");
          }
        })
        .catch(() => {
          // Transient poll errors are fine; the next tick retries.
        });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [notify, upload]);

  useEffect(() => {
    if (hasAccessToken()) {
      return;
    }
    if (!webApp?.initData) {
      notify("Откройте Mini App внутри Telegram для входа.", "warning");
      return;
    }
    void authenticateWithTelegram(webApp.initData)
      .then(() => setAuthReady(true))
      .catch((error: unknown) => {
        notify(error instanceof Error ? error.message : "Не удалось выполнить вход через Telegram.", "error");
      });
  }, [notify, webApp]);

  useEffect(() => {
    hapticFeedback?.impactOccurred("light");
    if (activeTab === "add") {
      webApp?.MainButton?.setText("Выбрать фото");
      webApp?.MainButton?.show();
    } else {
      webApp?.MainButton?.hide();
    }
  }, [activeTab, hapticFeedback, webApp]);

  const screens: Record<TabKey, ReactNode> = {
    today: <TodayScreen onNotify={notify} authReady={authReady} />,
    wardrobe: <WardrobeScreen onNotify={notify} authReady={authReady} />,
    add: <AddScreen onNotify={notify} upload={upload} onUploadChange={setUpload} />,
    designer: <DesignerScreen onNotify={notify} />,
    favorites: <FavoritesScreen onNotify={notify} authReady={authReady} />,
    studio: <StudioScreen onNotify={notify} authReady={authReady} lastUploadId={upload?.id} />,
  };

  return (
    <main className="app-shell">
      {screens[activeTab]}
      {toast ? <div className={`toast ${toast.tone}`}>{toast.message}</div> : null}
      <BottomNav active={activeTab} onChange={setActiveTab} />
    </main>
  );
}
