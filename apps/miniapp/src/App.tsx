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
  Trash2,
  Umbrella,
  Upload,
  Wind,
} from "lucide-react";

import {
  authenticateWithTelegram,
  deleteOutfit,
  deleteUpload,
  deleteWardrobeItem,
  favoriteOutfit,
  getWardrobeHealth,
  getWardrobeItemImageObjectUrl,
  getWeather,
  getUploadStatus,
  hasAccessToken,
  listOutfits,
  listWardrobeItems,
  recommendOutfit,
  recommendWithAnchors,
  retryUpload,
  runDesignerTool,
  selectOutfit,
  sendDesignerChat,
  uploadPhoto,
} from "./api";
import { BottomNav, InteractiveGarmentTile, ScoreBadge, SectionHead, SmartCard } from "./components";
import { quickScenarios } from "./data";
import { getTelegramWebApp } from "./telegram";
import type {
  DesignerResult,
  DesignerToolKey,
  GarmentCard,
  OutfitCard,
  TabKey,
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
    const objectUrls: string[] = [];
    void Promise.all([listWardrobeItems(), getWardrobeHealth()])
      .then(([items, nextHealth]) => {
        setRemoteGarments(items);
        setHealth(nextHealth);
        return Promise.all(
          items.map(async (item) => {
            const imageUrl = await getWardrobeItemImageObjectUrl(item.id);
            if (imageUrl) {
              objectUrls.push(imageUrl);
            }
            return { ...item, imageUrl };
          }),
        );
      })
      .then(setRemoteGarments)
      .catch((error: unknown) => {
        onNotify(error instanceof Error ? error.message : "Не удалось загрузить гардероб.", "error");
      });
    return () => {
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
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
      void deleteWardrobeItem(item.id)
        .then(() => {
          setRemoteGarments((current) => current.filter((existing) => existing.id !== item.id));
          setSelectedItems((current) => {
            const next = new Set(current);
            next.delete(item.id);
            return next;
          });
          if (item.imageUrl) {
            URL.revokeObjectURL(item.imageUrl);
          }
          onNotify(`«${item.title}» удалена из гардероба.`, "success");
        })
        .catch((error: unknown) => {
          onNotify(error instanceof Error ? error.message : "Не удалось удалить вещь.", "error");
        });
    };
    const message = `Удалить «${item.title}» из гардероба?`;
    const webApp = getTelegramWebApp();
    if (webApp?.showConfirm) {
      webApp.showConfirm(message, proceed);
    } else {
      proceed(window.confirm(message));
    }
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
  const [chatInput, setChatInput] = useState("Что надеть завтра, если я мёрзну сильнее обычного?");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{ role: "user" | "assistant"; text: string }>>([
    {
      role: "assistant",
      text: "Напишите сценарий дня, погоду или ощущение температуры — я отвечу с учётом вашего гардероба.",
    },
  ]);
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

  async function sendChatMessage() {
    const message = chatInput.trim();
    if (!message) {
      onNotify("Напишите вопрос дизайнеру.", "warning");
      return;
    }
    if (!hasAccessToken()) {
      onNotify("Откройте Mini App внутри Telegram, чтобы чат видел ваш гардероб.", "warning");
      return;
    }
    setChatBusy(true);
    setChatMessages((current) => [...current, { role: "user", text: message }]);
    setChatInput("");
    try {
      const response = await sendDesignerChat({
        message,
        scenario: "чат дизайнера",
        preferences: "учитывать личную чувствительность к холоду и жаре",
      });
      setChatMessages((current) => [...current, { role: "assistant", text: response.reply }]);
    } catch (error) {
      onNotify(error instanceof Error ? error.message : "Дизайнер сейчас недоступен.", "error");
      setChatMessages((current) => [
        ...current,
        { role: "assistant", text: "Не смогла получить ответ от AI-дизайнера. Попробуйте ещё раз чуть позже." },
      ]);
    } finally {
      setChatBusy(false);
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
      <article className="designer-chat-panel">
        <div className="chat-head">
          <MessageCircle size={20} />
          <div>
            <strong>Чат с дизайнером</strong>
            <span>Спросите про день, погоду, покупку или конкретную вещь</span>
          </div>
        </div>
        <div className="chat-log">
          {chatMessages.map((message, index) => (
            <p className={message.role} key={`${message.role}-${index}`}>
              {message.text}
            </p>
          ))}
        </div>
        <textarea
          value={chatInput}
          onChange={(event) => setChatInput(event.target.value)}
          rows={3}
          placeholder="Например: завтра офис и дождь, хочу тепло, но не слишком формально."
        />
        <button className="chat-submit" type="button" disabled={chatBusy} onClick={sendChatMessage}>
          {chatBusy ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
          Спросить дизайнера
        </button>
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

function FavoritesScreen({ onNotify, authReady }: { onNotify: Notify; authReady: boolean }) {
  const tabs = ["Все образы", "Избранные"];
  const [activeFavoriteTab, setActiveFavoriteTab] = useState(tabs[0]);
  const [outfits, setOutfits] = useState<OutfitCard[]>([]);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());
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
    const message = `Удалить образ «${outfit.title}»?`;
    const webApp = getTelegramWebApp();
    if (webApp?.showConfirm) {
      webApp.showConfirm(message, proceed);
    } else {
      proceed(window.confirm(message));
    }
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

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("today");
  const [toast, setToast] = useState<{ message: string; tone: string } | null>(null);
  const [authReady, setAuthReady] = useState(hasAccessToken());
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
    void authenticateWithTelegram(webApp.initData)
      .then(() => setAuthReady(true))
      .catch((error: unknown) => {
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
    today: <TodayScreen onNotify={notify} authReady={authReady} />,
    wardrobe: <WardrobeScreen onNotify={notify} authReady={authReady} />,
    add: <AddScreen onNotify={notify} />,
    designer: <DesignerScreen onNotify={notify} />,
    favorites: <FavoritesScreen onNotify={notify} authReady={authReady} />,
  };

  return (
    <main className="app-shell">
      {screens[activeTab]}
      {toast ? <div className={`toast ${toast.tone}`}>{toast.message}</div> : null}
      <BottomNav active={activeTab} onChange={setActiveTab} />
    </main>
  );
}
