import type { LucideIcon } from "lucide-react";

export type TabKey = "today" | "wardrobe" | "add" | "designer" | "favorites";

export type NavItem = {
  key: TabKey;
  label: string;
  icon: LucideIcon;
};

export type GarmentCard = {
  id: string;
  title: string;
  imageClass: string;
  imageUrl?: string;
  season: string;
  role: string;
  temperature: string;
  color?: string;
  brand?: string;
  modelName?: string;
  visualIdentifiers?: string[];
  searchText?: string;
  confidence?: number;
  status?: string;
  provenance: "user_processed" | "external_product_photo" | "generated_reference" | "placeholder";
};

export type OutfitCard = {
  id: string;
  title: string;
  context: string;
  score: number;
  comfort: number;
  items: string[];
  reason: string;
  favorite?: boolean;
};

export type UploadStatus = {
  id: string;
  status: "queued" | "processing" | "completed" | "failed" | string;
  task_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  filename?: string | null;
  upload_type?: string | null;
  progress: number;
  result_title?: string | null;
};

export type WeatherDay = {
  temperature_min_c: number;
  temperature_max_c: number;
  precipitation_probability: number;
  condition: string;
  summary: string;
};

export type WeatherSummary = {
  temperature_c: number;
  feels_like_c: number;
  temperature_min_c: number;
  temperature_max_c: number;
  precipitation_probability: number;
  wind_speed_ms: number;
  condition: string;
  summary: string;
  tomorrow?: WeatherDay | null;
};

export type DesignerToolKey = "gaps" | "anchor" | "purchase" | "rate" | "capsule";

export type DesignerResult = {
  title: string;
  summary: string;
  bullets: string[];
};

export type WardrobeHealth = {
  score: number;
  coverage_by_season: Record<string, unknown>;
  coverage_by_event: Record<string, unknown>;
  missing_roles: string[];
  duplicate_groups: string[];
  orphan_items: string[];
};

export type DesignerChatReply = {
  reply: string;
  outfit_id?: string | null;
  outfit_title?: string | null;
  outfit_explanation?: string | null;
  outfit_score?: number | null;
  outfit_item_ids?: string[];
  item_count: number;
};
