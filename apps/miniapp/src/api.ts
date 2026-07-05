import type {
  DesignerChatReply,
  DesignerResult,
  DesignerToolKey,
  GarmentCard,
  OutfitCard,
  UploadStatus,
  WardrobeHealth,
  WeatherSummary,
} from "./types";

type ImportMetaWithEnv = ImportMeta & {
  env?: {
    VITE_API_URL?: string;
  };
};

function defaultApiUrl(): string {
  const explicitUrl = (import.meta as ImportMetaWithEnv).env?.VITE_API_URL;
  if (explicitUrl) {
    return explicitUrl.replace(/\/$/, "");
  }
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    return "http://localhost:8000";
  }
  return window.location.origin;
}

export const apiBaseUrl = defaultApiUrl();

type TokenPair = {
  access_token: string;
  refresh_token?: string | null;
  token_type: string;
};

type ApiGarmentItem = {
  id: string;
  title: string;
  category: string;
  season: string[];
  main_color?: string | null;
  confidence: string | number;
  status: string;
  availability_status: string;
  designer_attributes: Record<string, unknown>;
};

type DesignerAttributes = {
  brand?: unknown;
  model_name?: unknown;
  visual_identifiers?: unknown;
};

type ApiOutfit = {
  id: string;
  title: string;
  score: string | number;
  comfort_score?: string | number | null;
  explanation?: string | null;
  designer_reasoning: Record<string, unknown>;
  is_favorite: boolean;
};

type OutfitRequestPayload = {
  prompt?: string;
  event_type?: string;
  weather?: Record<string, unknown>;
  variants_count?: number;
  anchor_item_ids?: string[];
};

const accessTokenKey = "aiw_access_token";
const refreshTokenKey = "aiw_refresh_token";

function saveTokens(tokens: TokenPair): void {
  window.localStorage.setItem(accessTokenKey, tokens.access_token);
  if (tokens.refresh_token) {
    window.localStorage.setItem(refreshTokenKey, tokens.refresh_token);
  }
}

export function hasAccessToken(): boolean {
  return Boolean(window.localStorage.getItem(accessTokenKey));
}

export async function authenticateWithTelegram(initData: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/auth/telegram`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData }),
  });
  saveTokens(await readJson<TokenPair>(response));
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = window.localStorage.getItem(refreshTokenKey);
  if (!refreshToken) {
    return false;
  }
  const response = await fetch(`${apiBaseUrl}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    window.localStorage.removeItem(accessTokenKey);
    window.localStorage.removeItem(refreshTokenKey);
    return false;
  }
  saveTokens(await response.json());
  return true;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
    throw new Error(body.detail ?? response.statusText);
  }
  return (await response.json()) as T;
}

async function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}, retried = false): Promise<Response> {
  const token = window.localStorage.getItem(accessTokenKey);
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401 && !retried && (await refreshAccessToken())) {
    return authenticatedFetch(input, init, true);
  }
  return response;
}

export async function uploadPhoto(file: File, uploadType: string): Promise<UploadStatus> {
  const body = new FormData();
  body.append("file", file);
  const response = await authenticatedFetch(`${apiBaseUrl}/uploads/file?upload_type=${encodeURIComponent(uploadType)}`, {
    method: "POST",
    body,
  });
  return readJson<UploadStatus>(response);
}

export async function getUploadStatus(uploadId: string): Promise<UploadStatus> {
  const response = await authenticatedFetch(`${apiBaseUrl}/uploads/${uploadId}`);
  return readJson<UploadStatus>(response);
}

export async function retryUpload(uploadId: string): Promise<UploadStatus> {
  const response = await authenticatedFetch(`${apiBaseUrl}/uploads/${uploadId}/retry`, {
    method: "POST",
  });
  return readJson<UploadStatus>(response);
}

export async function deleteUpload(uploadId: string): Promise<void> {
  const response = await authenticatedFetch(`${apiBaseUrl}/uploads/${uploadId}`, {
    method: "DELETE",
  });
  await readJson<{ id: string; status: string }>(response);
}

const categoryLabels: Record<string, string> = {
  top: "верх",
  bottom: "низ",
  outerwear: "верхний слой",
  shoes: "обувь",
  accessory: "аксессуар",
  dress: "платье",
  other: "вещь",
  unknown: "вещь",
};

const seasonLabels: Record<string, string> = {
  winter: "зима",
  spring: "весна",
  summer: "лето",
  autumn: "осень",
  all_season: "всесезон",
};

const availabilityLabels: Record<string, string> = {
  available: "доступно",
  unavailable: "не доступно",
  laundry: "в стирке",
  repair: "в ремонте",
  unknown: "статус уточнить",
};

const titleDictionary: Record<string, string> = {
  black: "чёрный",
  white: "белый",
  blue: "синий",
  navy: "тёмно-синий",
  gray: "серый",
  grey: "серый",
  beige: "бежевый",
  brown: "коричневый",
  green: "зелёный",
  red: "красный",
  tuxedo: "смокинг",
  suit: "костюм",
  herringbone: "в ёлочку",
  "double-breasted": "двубортный",
  shirt: "рубашка",
  coat: "пальто",
  jacket: "жакет",
  trousers: "брюки",
  pants: "брюки",
  sneakers: "кроссовки",
  boots: "ботинки",
};

function localizeToken(value: string, dictionary: Record<string, string>): string {
  return dictionary[value] ?? value.replace(/_/g, " ");
}

function localizeTitle(title: string): string {
  const normalized = title.trim();
  if (!normalized) {
    return "Вещь без названия";
  }
  if (/[А-Яа-яЁё]/.test(normalized)) {
    return normalized;
  }
  const lower = normalized.toLowerCase();
  if (lower.includes("double-breasted") && lower.includes("herringbone") && lower.includes("suit")) {
    return "Двубортный костюм в ёлочку";
  }
  if (lower.includes("black") && lower.includes("tuxedo") && lower.includes("suit")) {
    return "Чёрный смокинг";
  }
  const translated = lower
    .split(/\s+/)
    .map((word) => localizeToken(word.replace(/[.,]/g, ""), titleDictionary))
    .join(" ");
  return translated.charAt(0).toUpperCase() + translated.slice(1);
}

function imageClassFor(item: ApiGarmentItem): string {
  const color = String(item.main_color ?? "").toLowerCase();
  if (color.includes("бел") || color.includes("white")) {
    return "swatch-white";
  }
  if (color.includes("корич") || color.includes("brown") || color.includes("beige") || color.includes("беж")) {
    return "swatch-brown";
  }
  if (color.includes("black") || color.includes("чёр") || color.includes("чер") || item.category === "outerwear") {
    return "swatch-black";
  }
  return "swatch-denim";
}

function textAttribute(attributes: DesignerAttributes, key: "brand" | "model_name"): string | undefined {
  const value = attributes[key];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function listAttribute(attributes: DesignerAttributes, key: "visual_identifiers"): string[] {
  const value = attributes[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function displayTitle(item: ApiGarmentItem): string {
  const attributes = item.designer_attributes as DesignerAttributes;
  const title = localizeTitle(item.title);
  const brand = textAttribute(attributes, "brand");
  const modelName = textAttribute(attributes, "model_name");
  if (brand && modelName && !title.toLowerCase().includes(brand.toLowerCase())) {
    return `${item.category === "shoes" ? "Кроссовки" : title} ${brand} ${modelName}`;
  }
  if (brand && !title.toLowerCase().includes(brand.toLowerCase())) {
    return `${title} ${brand}`;
  }
  return title;
}

export async function listWardrobeItems(): Promise<GarmentCard[]> {
  const response = await authenticatedFetch(`${apiBaseUrl}/items`);
  const items = await readJson<ApiGarmentItem[]>(response);
  return items.map((item) => {
    const attributes = item.designer_attributes as DesignerAttributes;
    const brand = textAttribute(attributes, "brand");
    const modelName = textAttribute(attributes, "model_name");
    const title = displayTitle(item);
    return {
      id: item.id,
      title,
      imageClass: imageClassFor(item),
      season: item.season.map((season) => localizeToken(String(season), seasonLabels)).join(" · ") || "сезон уточнить",
      role: localizeToken(item.category, categoryLabels),
      temperature: localizeToken(item.availability_status, availabilityLabels),
      color: item.main_color ?? undefined,
      brand,
      modelName,
      visualIdentifiers: listAttribute(attributes, "visual_identifiers"),
      searchText: [item.title, title, brand, modelName, item.category, item.main_color, item.availability_status]
        .filter(Boolean)
        .join(" ")
        .toLowerCase(),
      confidence: Number(item.confidence),
      provenance: "user_processed" as const,
    };
  });
}

export async function getWardrobeItemImageObjectUrl(itemId: string): Promise<string | undefined> {
  const response = await authenticatedFetch(`${apiBaseUrl}/items/${itemId}/image`);
  if (response.status === 404) {
    return undefined;
  }
  if (!response.ok) {
    return undefined;
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function getWardrobeHealth(): Promise<WardrobeHealth> {
  const response = await authenticatedFetch(`${apiBaseUrl}/wardrobe/health`);
  const payload = await readJson<WardrobeHealth>(response);
  return {
    ...payload,
    score: Number(payload.score),
    missing_roles: payload.missing_roles ?? [],
    duplicate_groups: payload.duplicate_groups ?? [],
    orphan_items: payload.orphan_items ?? [],
  };
}

export async function listOutfits(): Promise<OutfitCard[]> {
  const response = await authenticatedFetch(`${apiBaseUrl}/outfits`);
  const outfits = await readJson<ApiOutfit[]>(response);
  return outfits.map((outfit) => ({
    id: outfit.id,
    title: outfit.title,
    context: String(outfit.designer_reasoning.source ?? "Гардероб"),
    score: Number(outfit.score),
    comfort: Number(outfit.comfort_score ?? outfit.score),
    items: [],
    reason: outfit.explanation ?? "",
  }));
}

export async function getWeather(latitude: number, longitude: number): Promise<WeatherSummary> {
  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
  });
  const response = await authenticatedFetch(`${apiBaseUrl}/weather?${params.toString()}`);
  return readJson<WeatherSummary>(response);
}

export async function recommendOutfit(payload: OutfitRequestPayload): Promise<OutfitCard[]> {
  const response = await authenticatedFetch(`${apiBaseUrl}/outfits/from-prompt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      variants_count: 3,
      anchor_item_ids: [],
      weather: {},
      ...payload,
    }),
  });
  const outfits = await readJson<ApiOutfit[]>(response);
  return outfits.map((outfit) => ({
    id: outfit.id,
    title: localizeTitle(outfit.title),
    context: String(outfit.designer_reasoning.source ?? "гардероб"),
    score: Number(outfit.score),
    comfort: Number(outfit.comfort_score ?? outfit.score),
    items: [],
    reason: outfit.explanation ?? "Собрано из вещей вашего гардероба.",
  }));
}

export async function runDesignerTool(tool: DesignerToolKey): Promise<DesignerResult> {
  if (tool === "gaps") {
    const response = await authenticatedFetch(`${apiBaseUrl}/designer/wardrobe-gaps`, { method: "POST" });
    const payload = await readJson<{ missing_items: Array<{ title: string; reason?: string; priority?: string }> }>(
      response,
    );
    const bullets = payload.missing_items.map((item) =>
      [localizeTitle(item.title), item.reason, item.priority].filter(Boolean).join(" · "),
    );
    return {
      title: "Чего не хватает",
      summary: bullets.length ? "Нашла пробелы, которые сильнее всего ограничивают образы." : "Явных пробелов нет.",
      bullets: bullets.length ? bullets : ["Добавьте больше вещей, чтобы расчёт стал точнее."],
    };
  }

  if (tool === "rate") {
    const response = await authenticatedFetch(`${apiBaseUrl}/designer/rate-look`, { method: "POST" });
    const payload = await readJson<{ safety_note?: string }>(response);
    return {
      title: "Оценка образа",
      summary: "Можно разобрать фото образа безопасно: только одежда, сочетания и уместность.",
      bullets: [payload.safety_note ?? "Лицо, тело и личность не оцениваются."],
    };
  }

  const localCopy: Record<DesignerToolKey, DesignerResult> = {
    gaps: {
      title: "Чего не хватает",
      summary: "Проверяю сезонность, события и роли вещей.",
      bullets: ["Нужны данные гардероба."],
    },
    anchor: {
      title: "Собрать с вещью",
      summary: "Выберите вещь в гардеробе, затем задайте погоду и событие.",
      bullets: ["Будет использован endpoint рекомендаций с anchor_item_ids."],
    },
    purchase: {
      title: "Стоит ли покупать",
      summary: "Покупку стоит проверять по дублям, сценариям носки и совместимости.",
      bullets: ["Для точного расчёта добавьте ссылку или описание вещи."],
    },
    rate: {
      title: "Оценка образа",
      summary: "Разбор работает только по одежде и сочетаниям.",
      bullets: ["Лицо, тело и личность не оцениваются."],
    },
    capsule: {
      title: "Капсула",
      summary: "Капсула собирается из сценария, погоды, длительности и ограничений багажа.",
      bullets: ["Для поездки укажите город, даты и дресс-код."],
    },
  };
  return localCopy[tool];
}

export async function sendDesignerChat(payload: {
  message: string;
  scenario?: string;
  preferences?: string;
  weather_context?: string;
}): Promise<DesignerChatReply> {
  const response = await authenticatedFetch(`${apiBaseUrl}/designer/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<DesignerChatReply>(response);
}
