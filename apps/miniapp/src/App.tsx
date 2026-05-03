import { useEffect, useMemo, useState } from "react";
import { CloudRain, Heart, Search, Sparkles, Upload } from "lucide-react";

import { BottomNav, GarmentTile, ScoreBadge, SectionHead, SmartCard } from "./components";
import { garments, quickScenarios, todayOutfit } from "./data";
import { getTelegramWebApp } from "./telegram";
import type { TabKey } from "./types";
import "./styles.css";

function TodayScreen() {
  return (
    <section className="screen-stack">
      <header className="topline">
        <div>
          <span className="eyebrow">AI Wardrobe</span>
          <h1>Привет, что наденем?</h1>
        </div>
        <button className="round-button" type="button" aria-label="AI">
          <Sparkles size={22} />
        </button>
      </header>

      <article className="weather-card">
        <CloudRain size={22} />
        <div>
          <strong>{todayOutfit.context}</strong>
          <span>Погодный коридор на весь день</span>
        </div>
      </article>

      <article className="hero-outfit">
        <div className="hero-head">
          <div>
            <span className="eyebrow">Лучший вариант</span>
            <h2>{todayOutfit.title}</h2>
          </div>
          <ScoreBadge score={todayOutfit.score} />
        </div>
        <div className="mini-grid">
          {garments.map((item) => (
            <div className="mini-item" key={item.title}>
              <div className={item.imageClass} />
            </div>
          ))}
        </div>
        <div className="reasoning">
          <strong>Почему работает</strong>
          <p>{todayOutfit.reason}</p>
        </div>
        <div className="action-row three">
          <button className="primary">Выбрать</button>
          <button>Теплее</button>
          <button>Другой</button>
        </div>
      </article>

      <SectionHead title="Быстрые сценарии" action="контекст дня" />
      <div className="scenario-grid">
        {quickScenarios.map(([title, text]) => (
          <article className="scenario" key={title}>
            <Sparkles size={18} />
            <strong>{title}</strong>
            <span>{text}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

function WardrobeScreen() {
  return (
    <section className="screen-stack">
      <header className="compact-header">
        <h1>Гардероб</h1>
        <button className="round-button" type="button" aria-label="Поиск">
          <Search size={20} />
        </button>
      </header>
      <div className="chip-row">
        {["Верх", "Низ", "Обувь", "Демисезон", "База", "Проверить"].map((chip) => (
          <button type="button" key={chip}>
            {chip}
          </button>
        ))}
      </div>
      <article className="health-card">
        <div>
          <span className="eyebrow">Wardrobe Health</span>
          <h2>62%</h2>
        </div>
        <p>Не хватает дождевой обуви и одного спокойного верхнего слоя.</p>
      </article>
      <div className="garment-grid">
        {garments.map((item) => (
          <GarmentTile item={item} key={item.title} />
        ))}
      </div>
    </section>
  );
}

function AddScreen() {
  return (
    <section className="screen-stack">
      <header className="compact-header">
        <h1>Добавить</h1>
      </header>
      <article className="upload-card">
        <Upload size={30} />
        <h2>Фото вещи или лука</h2>
        <p>Я создам карточки и сохраню лук в избранное</p>
        <button className="primary">Выбрать фото</button>
      </article>
      <div className="mode-grid">
        {["Вещь", "Лук", "Авто"].map((mode) => (
          <button type="button" key={mode}>
            {mode}
          </button>
        ))}
      </div>
      <SectionHead title="Обработка" />
      <SmartCard icon="camera" title="Фото принято" text="AI анализ · research · карточка" />
      <SmartCard icon="archive" title="Privacy receipt" text="OpenRouter · original saved · no training" />
    </section>
  );
}

function DesignerScreen() {
  return (
    <section className="screen-stack">
      <header className="compact-header">
        <h1>Дизайнер</h1>
      </header>
      <div className="designer-list">
        <SmartCard icon="layers" title="Чего не хватает?" text="Wardrobe gaps · missing item cards" />
        <SmartCard icon="bot" title="Собрать с вещью" text="Anchors · weather · event" />
        <SmartCard icon="search" title="Стоит ли покупать?" text="Duplicate risk · compatibility" />
        <SmartCard icon="camera" title="Оценить образ" text="Сначала что работает, затем улучшения" />
        <SmartCard icon="calendar" title="Капсула" text="Неделя · поездка · сезон" />
      </div>
      <article className="style-dna">
        <span className="eyebrow">Style DNA</span>
        <h2>casual · minimal · neutral</h2>
        <div className="dna-bars">
          <span style={{ width: "76%" }} />
          <span style={{ width: "58%" }} />
          <span style={{ width: "42%" }} />
        </div>
      </article>
    </section>
  );
}

function FavoritesScreen() {
  return (
    <section className="screen-stack">
      <header className="compact-header">
        <h1>Избранное</h1>
        <button className="round-button" type="button" aria-label="Избранное">
          <Heart size={20} />
        </button>
      </header>
      <div className="tabs">
        {["Луки", "Аутфиты", "Wishlist", "Moodboard"].map((tab, index) => (
          <button className={index === 0 ? "active" : ""} type="button" key={tab}>
            {tab}
          </button>
        ))}
      </div>
      <article className="favorite-look">
        <div className="look-collage">
          {garments.map((item) => (
            <span className={item.imageClass} key={item.title} />
          ))}
        </div>
        <div>
          <span className="eyebrow">Outfit DNA</span>
          <h2>{todayOutfit.title}</h2>
          <p>{todayOutfit.reason}</p>
        </div>
        <div className="action-row two">
          <button className="primary">Похожий</button>
          <button>Почему работает</button>
        </div>
      </article>
    </section>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("today");
  const webApp = useMemo(() => getTelegramWebApp(), []);

  useEffect(() => {
    webApp?.ready();
    webApp?.expand();
  }, [webApp]);

  useEffect(() => {
    webApp?.HapticFeedback?.impactOccurred("light");
  }, [activeTab, webApp]);

  const screens: Record<TabKey, JSX.Element> = {
    today: <TodayScreen />,
    wardrobe: <WardrobeScreen />,
    add: <AddScreen />,
    designer: <DesignerScreen />,
    favorites: <FavoritesScreen />,
  };

  return (
    <main className="app-shell">
      {screens[activeTab]}
      <BottomNav active={activeTab} onChange={setActiveTab} />
    </main>
  );
}
