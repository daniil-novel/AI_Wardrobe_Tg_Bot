import type { LucideIcon } from "lucide-react";

export type TabKey = "today" | "wardrobe" | "add" | "designer" | "favorites" | "studio";

export type NavItem = {
  key: TabKey;
  label: string;
  shortLabel: string;
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

export type ImageSelection = {
  kind: "full" | "rectangle";
  source: "default" | "user";
  x: number;
  y: number;
  width: number;
  height: number;
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

export type BillingPlan = {
  code: string;
  title: string;
  monthly_price: number;
  currency: string;
  item_limit: number | null;
  ai_analysis_limit: number | null;
  avatar_generation_limit: number;
  try_on_limit: number;
  features: string[];
  pricing_status: string;
};

export type BillingAccess = {
  enabled: boolean;
  payments_enabled: boolean;
  plan: string;
  source: string;
  expires_at: string | null;
  features: string[];
};

export type AvatarMeasurement = {
  code: "height" | "shoulders" | "chest" | "waist" | "hips" | "inseam";
  value: number;
  unit: "cm";
  source?: string;
  confidence?: number | null;
};

export type AvatarProfile = {
  id: string;
  status: string;
  description?: string | null;
  neutral_clothing: string;
  reference_image_id?: string | null;
  generated_image_id?: string | null;
  consent_version?: string | null;
  consented_at?: string | null;
  revoked_at?: string | null;
  generation_error?: string | null;
  generated_at?: string | null;
  measurements: AvatarMeasurement[];
};

export type TryOnJob = {
  id: string;
  status: string;
  provider?: string | null;
  output_image_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  garment_item_ids: string[];
  created_at: string;
  completed_at?: string | null;
};
