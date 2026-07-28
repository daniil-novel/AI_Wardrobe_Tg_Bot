# UX/UI audit

Дата прохода: 2026-07-28.  
Среда: реальный Chromium, responsive viewport `390×844`, локальная Mini App без Telegram initData.

## Итог

Все шесть вкладок открываются, нижняя навигация полностью видна, critical overflow после исправлений отсутствует. Интерфейс пригоден для product demo. Авторизованные happy paths и реальные AI outputs в этом браузерном проходе не подтверждены, потому что обычный Chromium не имеет Telegram initData.

## Матрица экранов

| Экран | Что проверено | Результат | Остаточный риск |
|---|---|---|---|
| Сегодня | hero, weather/state messaging, primary actions, nav | Читаемо, визуальная иерархия ясна | Offline/slow skeleton не проверен с network throttling |
| Гардероб | filters, cards/empty preview, horizontal chips, nav | Scrollbar убран, контент не обрезается | Большой гардероб и реальные thumbnail failures требуют E2E |
| Добавить | file picker, proposed selection, pointer drag, keyboard move/resize, whole photo, undo/redo/reset, preview | На synthetic fitting-room photo область сужена до человека, background rack/mannequins исключены | Нет semantic person segmentation, brush/lasso и zoom/pan |
| Дизайнер | scenario chips, chat surface, action hierarchy | Chips больше не показывают системный scrollbar | Нужен длинный диалог, IME/keyboard и slow-response test |
| Избранное | tabs, empty/content structure, nav | Несостыковок не найдено | Нужна проверка большого списка и failed image states |
| AI Studio | current access, stacked plans, promo, consent form, measurements, avatar/try-on cards | Тарифы и promo input исправлены; ограничения объяснены; без auth действия заблокированы | Payment CTA намеренно disabled |

## Editor QA

Fixture: синтетическое фото взрослого человека в примерочной; на фоне рейл и манекены. Фото не является пользовательским и не входит в product assets.

Проверено:

- default central suggestion видима сразу;
- drag пальцем/мышью меняет нормализованный rectangle;
- arrows двигают область; `Shift+arrows` меняют размер; `Alt` уменьшает шаг;
- preview соответствует пикселям, которые будут отправлены;
- undo/redo восстанавливают геометрию;
- «всё фото» и reset работают;
- подтверждённая область кадрируется client-side до multipart upload;
- сервер хранит selection provenance.

Статус: `PARTIAL` относительно Photoshop-like semantic mask. Rectangle решает исходный сценарий «выделить нужный лук», но сложные позы и пересекающиеся люди потребуют segmentation + add/subtract brush.

## Accessibility

Реализовано/проверено по коду и DOM:

- кнопки имеют `type=button`;
- промокод имеет `aria-label`;
- upload progress использует доступное состояние;
- touch controls рассчитаны на mobile;
- locked Studio объясняет причину, а не только меняет цвет;
- haptic feedback вызывается только на поддерживаемой версии Telegram API.
- нижняя навигация сохраняет полные accessible names, а короткие видимые подписи помещаются без ellipsis;
- финальный чистый browser-log проход не содержит `error` или `warning`.

Не доказано:

- keyboard interaction в реальном screen reader/WebView;
- screen reader reading order на реальном iOS/Android;
- axe/WCAG automated run;
- reduced-motion и high-contrast режимы;
- 320 px viewport и landscape.

## Исправленные визуальные дефекты

1. Bottom nav переведён на шесть `minmax(0, 1fr)` колонок; видимые подписи сокращены до «День / Вещи / Новое / AI / Луки / Студия», полные названия сохранены через `aria-label`.
2. Chip/tab/garment scroll areas скрывают системный scrollbar.
3. Тарифы на мобильном складываются в одну колонку.
4. Promo input/button занимают доступную ширину.
5. Static preview limits синхронизированы с сервером.
6. Haptic calls gated по Telegram version, browser console не засоряется ожидаемыми warning.

## Рекомендации

### P0 beta

- Playwright E2E с валидным test initData и изолированной тестовой БД;
- real slow/offline/error states каждого API блока;
- privacy copy review рядом с face/body consent.

### P1

- локальная person segmentation;
- brush add/subtract, zoom/pan и keyboard handles;
- вынести Studio из bottom nav при появлении седьмого раздела;
- добавить quota remaining рядом с generation buttons;
- показывать примерную длительность и возможность покинуть экран во время queued job.

### P2

- dark mode, reduced motion, 320/360/520 px snapshots;
- screen reader lab на VoiceOver/TalkBack;
- визуальные regression snapshots в CI.
