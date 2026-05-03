import type { LucideIcon } from "lucide-react";

export type TabKey = "today" | "wardrobe" | "add" | "designer" | "favorites";

export type NavItem = {
  key: TabKey;
  label: string;
  icon: LucideIcon;
};

export type GarmentCard = {
  title: string;
  imageClass: string;
  season: string;
  role: string;
  temperature: string;
  confidence?: number;
  provenance: "user_processed" | "external_product_photo" | "generated_reference" | "placeholder";
};

export type OutfitCard = {
  title: string;
  context: string;
  score: number;
  comfort: number;
  items: string[];
  reason: string;
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
