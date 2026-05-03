import type { GarmentCard, OutfitCard } from "./types";

export const todayOutfit: OutfitCard = {
  title: "Город + метро + офис",
  context: "+8…+13°C · дождь после 17:00",
  score: 92,
  comfort: 86,
  items: ["Куртка", "Футболка", "Джинсы", "Ботинки"],
  reason:
    "Нейтральная база, фактура денима и удобная обувь. Верхний слой можно снять в метро.",
};

export const garments: GarmentCard[] = [
  {
    title: "Джинсовая куртка",
    imageClass: "swatch-denim",
    season: "Демисезон",
    role: "База",
    temperature: "+8…+20°C",
    confidence: 0.87,
    provenance: "user_processed",
  },
  {
    title: "Белая футболка",
    imageClass: "swatch-white",
    season: "Лето",
    role: "База",
    temperature: "+16…+28°C",
    confidence: 0.94,
    provenance: "external_product_photo",
  },
  {
    title: "Прямые джинсы",
    imageClass: "swatch-black",
    season: "Все сезоны",
    role: "Опора",
    temperature: "+5…+22°C",
    confidence: 0.78,
    provenance: "user_processed",
  },
  {
    title: "Кожаные ботинки",
    imageClass: "swatch-brown",
    season: "Осень",
    role: "Практичность",
    temperature: "+3…+16°C",
    confidence: 0.66,
    provenance: "generated_reference",
  },
];

export const quickScenarios = [
  ["Много метро", "слои + компактность"],
  ["Много ходить", "обувь и свобода"],
  ["Долго сидеть", "не мнётся, удобно"],
  ["Музей вечером", "smart casual"],
];
