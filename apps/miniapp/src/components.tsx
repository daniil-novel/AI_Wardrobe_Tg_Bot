import {
  Archive,
  Bot,
  CalendarDays,
  Camera,
  Check,
  ChevronRight,
  Heart,
  Home,
  Layers3,
  Plus,
  Search,
  Shirt,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";

import type { GarmentCard, NavItem, TabKey } from "./types";

export const navItems: NavItem[] = [
  { key: "today", label: "Сегодня", icon: Home },
  { key: "wardrobe", label: "Гардероб", icon: Shirt },
  { key: "add", label: "Добавить", icon: Plus },
  { key: "designer", label: "Дизайнер", icon: Sparkles },
  { key: "favorites", label: "Избранное", icon: Heart },
];

export function BottomNav({
  active,
  onChange,
}: {
  active: TabKey;
  onChange: (tab: TabKey) => void;
}) {
  return (
    <nav className="bottom-nav" aria-label="Главная навигация">
      {navItems.map((item) => {
        const Icon = item.icon;
        return (
          <button
            className={active === item.key ? "nav-item active" : "nav-item"}
            key={item.key}
            onClick={() => onChange(item.key)}
            type="button"
          >
            <Icon size={18} strokeWidth={2.2} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

export function ScoreBadge({ score, label = "оценка" }: { score: number; label?: string }) {
  return (
    <span className="score-badge">
      {score}% <small>{label}</small>
    </span>
  );
}

export function ConfidenceBadge({ value }: { value?: number }) {
  if (value === undefined || value >= 0.85) {
    return <span className="badge success">Готово</span>;
  }
  if (value >= 0.65) {
    return <span className="badge warning">Проверьте</span>;
  }
  if (value >= 0.45) {
    return <span className="badge orange">Не уверен</span>;
  }
  return <span className="badge danger">Нужна помощь</span>;
}

export function ProvenanceBadge({ type }: { type: GarmentCard["provenance"] }) {
  const labels = {
    user_processed: "Ваше фото",
    external_product_photo: "Похожее фото",
    generated_reference: "AI-референс",
    placeholder: "Временно",
  };
  return <span className="provenance">{labels[type]}</span>;
}

export function GarmentTile({ item, selectable = false }: { item: GarmentCard; selectable?: boolean }) {
  return <InteractiveGarmentTile item={item} selectable={selectable} />;
}

export function InteractiveGarmentTile({
  item,
  selectable = false,
  selected = false,
  onClick,
  onDelete,
}: {
  item: GarmentCard;
  selectable?: boolean;
  selected?: boolean;
  onClick?: () => void;
  onDelete?: () => void;
}) {
  return (
    <article
      className={`garment-card${selectable ? " selectable" : ""}${selected ? " selected" : ""}`}
      onClick={onClick}
      onKeyDown={(event) => {
        if (onClick && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onClick();
        }
      }}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className={item.imageUrl ? "garment-image product-photo" : `garment-image ${item.imageClass}`}>
        {item.imageUrl ? (
          <img src={item.imageUrl} alt={item.title} loading="lazy" />
        ) : (
          <>
            <Shirt className="garment-icon" size={36} strokeWidth={1.8} />
            <span>{item.role}</span>
          </>
        )}
        {selectable || selected ? <Check className="select-check" size={18} /> : null}
        {onDelete ? (
          <button
            className="delete-check"
            type="button"
            aria-label={`Удалить «${item.title}»`}
            onClick={(event) => {
              event.stopPropagation();
              onDelete();
            }}
          >
            <Trash2 size={16} />
          </button>
        ) : null}
      </div>
      <div className="garment-meta">
        <div>
          <h3>{item.title}</h3>
          {item.brand || item.modelName ? (
            <strong className="item-model">
              {[item.brand, item.modelName].filter(Boolean).join(" · ")}
            </strong>
          ) : null}
          <p>
            {item.season} · {item.role}
          </p>
          <span>
            {item.temperature}
            {item.color ? ` · ${item.color}` : ""}
          </span>
        </div>
        <ConfidenceBadge value={item.confidence} />
      </div>
      <ProvenanceBadge type={item.provenance} />
    </article>
  );
}

export function SectionHead({ title, action }: { title: string; action?: string }) {
  return (
    <div className="section-head">
      <h2>{title}</h2>
      {action ? <button type="button">{action}</button> : null}
    </div>
  );
}

export function SmartCard({
  icon,
  title,
  text,
  active = false,
  onClick,
}: {
  icon: "upload" | "bot" | "archive" | "calendar" | "layers" | "camera" | "search";
  title: string;
  text: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const icons = {
    upload: Upload,
    bot: Bot,
    archive: Archive,
    calendar: CalendarDays,
    layers: Layers3,
    camera: Camera,
    search: Search,
  };
  const Icon = icons[icon];
  return (
    <article
      className={active ? "smart-card active" : "smart-card"}
      onClick={onClick}
      onKeyDown={(event) => {
        if (onClick && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onClick();
        }
      }}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <Icon size={20} />
      <div>
        <h3>{title}</h3>
        <p>{text}</p>
      </div>
      <ChevronRight size={18} />
    </article>
  );
}
