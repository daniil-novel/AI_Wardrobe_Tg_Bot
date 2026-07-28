import { getTelegramWebApp } from "./telegram";
import type {
  AvatarMeasurement,
  AvatarProfile,
  BillingAccess,
  BillingPlan,
  DesignerChatReply,
  DesignerResult,
  DesignerToolKey,
  GarmentCard,
  ImageSelection,
  OutfitCard,
  TryOnJob,
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
  item_ids?: string[];
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

function clearTokens(): void {
  window.localStorage.removeItem(accessTokenKey);
  window.localStorage.removeItem(refreshTokenKey);
}

async function reauthenticateWithTelegram(): Promise<boolean> {
  const initData = getTelegramWebApp()?.initData;
  if (!initData) {
    clearTokens();
    return false;
  }
  try {
    await authenticateWithTelegram(initData);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

async function doRefreshAccessToken(): Promise<boolean> {
  const refreshToken = window.localStorage.getItem(refreshTokenKey);
  if (!refreshToken) {
    return reauthenticateWithTelegram();
  }
  const response = await fetch(`${apiBaseUrl}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    // The server rotates refresh tokens, so a lost race or expiry lands here:
    // recover with a fresh Telegram initData login instead of going tokenless.
    return reauthenticateWithTelegram();
  }
  saveTokens(await response.json());
  return true;
}

let refreshInFlight: Promise<boolean> | null = null;

function refreshAccessToken(): Promise<boolean> {
  // Single flight: parallel 401s must share one refresh, or the losers would
  // rotate-fail and wipe the tokens the winner just saved.
  refreshInFlight ??= doRefreshAccessToken().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
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

export async function uploadPhoto(
  file: File,
  uploadType: string,
  selection?: ImageSelection,
): Promise<UploadStatus> {
  const body = new FormData();
  body.append("file", file);
  if (selection) {
    body.append("selection_json", JSON.stringify(selection));
  }
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
      status: item.status,
      provenance: "user_processed" as const,
    };
  });
}

export async function deleteWardrobeItem(itemId: string): Promise<void> {
  const response = await authenticatedFetch(`${apiBaseUrl}/items/${itemId}`, {
    method: "DELETE",
  });
  await readJson<{ id: string; status: string }>(response);
}

const itemImageCache = new Map<string, string>();

export async function getWardrobeItemImageObjectUrl(itemId: string): Promise<string | undefined> {
  const cached = itemImageCache.get(itemId);
  if (cached) {
    return cached;
  }
  const response = await authenticatedFetch(`${apiBaseUrl}/items/${itemId}/image`);
  if (!response.ok) {
    return undefined;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  itemImageCache.set(itemId, url);
  return url;
}

export function evictItemImage(itemId: string): void {
  const url = itemImageCache.get(itemId);
  if (url) {
    URL.revokeObjectURL(url);
    itemImageCache.delete(itemId);
  }
}

export async function mapWithConcurrency<T, R>(
  items: T[],
  limit: number,
  task: (item: T) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array<R>(items.length);
  let nextIndex = 0;
  async function workerLoop(): Promise<void> {
    while (nextIndex < items.length) {
      const current = nextIndex++;
      results[current] = await task(items[current]);
    }
  }
  await Promise.all(Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, workerLoop));
  return results;
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

function mapOutfit(outfit: ApiOutfit): OutfitCard {
  return {
    id: outfit.id,
    title: localizeTitle(outfit.title),
    context: String(outfit.designer_reasoning.source ?? "гардероб"),
    score: Number(outfit.score),
    comfort: Number(outfit.comfort_score ?? outfit.score),
    items: outfit.item_ids ?? [],
    reason: outfit.explanation ?? "Собрано из вещей вашего гардероба.",
    favorite: outfit.is_favorite,
  };
}

export async function listOutfits(): Promise<OutfitCard[]> {
  const response = await authenticatedFetch(`${apiBaseUrl}/outfits`);
  const outfits = await readJson<ApiOutfit[]>(response);
  return outfits.map(mapOutfit);
}

export async function selectOutfit(outfitId: string): Promise<void> {
  await authenticatedFetch(`${apiBaseUrl}/outfits/${outfitId}/select`, { method: "POST" });
  await authenticatedFetch(`${apiBaseUrl}/outfits/${outfitId}/wear`, { method: "POST" });
}

export async function favoriteOutfit(outfitId: string): Promise<OutfitCard> {
  const response = await authenticatedFetch(`${apiBaseUrl}/outfits/${outfitId}/favorite`, { method: "POST" });
  return mapOutfit(await readJson<ApiOutfit>(response));
}

export async function deleteOutfit(outfitId: string): Promise<void> {
  const response = await authenticatedFetch(`${apiBaseUrl}/outfits/${outfitId}`, {
    method: "DELETE",
  });
  await readJson<{ id: string; status: string }>(response);
}

export async function recommendWithAnchors(anchorItemIds: string[], prompt?: string): Promise<OutfitCard[]> {
  const response = await authenticatedFetch(`${apiBaseUrl}/outfits/recommend-with-anchors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: prompt ?? "Собери образ вокруг выбранных вещей",
      anchor_item_ids: anchorItemIds,
      weather: {},
      variants_count: 1,
    }),
  });
  const outfits = await readJson<ApiOutfit[]>(response);
  return outfits.map(mapOutfit);
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

export async function listBillingPlans(): Promise<BillingPlan[]> {
  const response = await fetch(`${apiBaseUrl}/billing/plans`);
  return readJson<BillingPlan[]>(response);
}

export async function getBillingAccess(): Promise<BillingAccess> {
  const response = await authenticatedFetch(`${apiBaseUrl}/billing/me`);
  return readJson<BillingAccess>(response);
}

export async function redeemPromoCode(code: string): Promise<{ plan: string; expires_at: string; features: string[] }> {
  const response = await authenticatedFetch(`${apiBaseUrl}/billing/promos/redeem`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  return readJson<{ plan: string; expires_at: string; features: string[] }>(response);
}

export async function getAvatarProfile(): Promise<AvatarProfile | null> {
  const response = await authenticatedFetch(`${apiBaseUrl}/avatar/profile`);
  if (response.status === 404) {
    return null;
  }
  return readJson<AvatarProfile>(response);
}

export async function saveAvatarProfile(payload: {
  consent: boolean;
  description?: string;
  reference_upload_id?: string;
  measurements: AvatarMeasurement[];
}): Promise<AvatarProfile> {
  const response = await authenticatedFetch(`${apiBaseUrl}/avatar/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      consent_version: "2026-07",
      neutral_clothing: "fitted_studio_basics",
    }),
  });
  return readJson<AvatarProfile>(response);
}

export async function revokeAvatarProfile(): Promise<void> {
  const response = await authenticatedFetch(`${apiBaseUrl}/avatar/profile`, { method: "DELETE" });
  if (!response.ok) {
    await readJson<unknown>(response);
  }
}

export async function generateAvatar(): Promise<AvatarProfile> {
  const response = await authenticatedFetch(`${apiBaseUrl}/avatar/generate`, { method: "POST" });
  return readJson<AvatarProfile>(response);
}

export async function createTryOn(garmentItemIds: string[]): Promise<TryOnJob> {
  const response = await authenticatedFetch(`${apiBaseUrl}/avatar/try-ons`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ garment_item_ids: garmentItemIds }),
  });
  return readJson<TryOnJob>(response);
}

export async function getTryOn(jobId: string): Promise<TryOnJob> {
  const response = await authenticatedFetch(`${apiBaseUrl}/avatar/try-ons/${jobId}`);
  return readJson<TryOnJob>(response);
}

async function imageObjectUrl(path: string): Promise<string | undefined> {
  const response = await authenticatedFetch(`${apiBaseUrl}${path}`);
  if (!response.ok) {
    return undefined;
  }
  return URL.createObjectURL(await response.blob());
}

export async function getAvatarImageObjectUrl(): Promise<string | undefined> {
  return imageObjectUrl("/avatar/image");
}

export async function getTryOnImageObjectUrl(jobId: string): Promise<string | undefined> {
  return imageObjectUrl(`/avatar/try-ons/${jobId}/image`);
}
