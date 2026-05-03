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
