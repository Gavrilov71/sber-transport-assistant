# Дизайн-система

Production frontend находится в `app/static/`. Отдельный source/reference pack в репозитории не нужен: все реально используемые изображения, SVG и шрифт уже лежат в `app/static/assets/`.

## Основные принципы

- светлая гражданская интерфейсная тема с красным акцентом;
- локальный Manrope Variable (`app/static/assets/fonts/Manrope-Variable.ttf`), далее Arial/system-ui;
- базовый размер текста 18 px;
- интерактивные области не меньше 48 px;
- видимый keyboard focus и skip-link;
- поддержка `prefers-reduced-motion`;
- адаптация от мобильной ширины до широкого desktop;
- frontend не принимает фактических решений: он отображает `answer`, `status`, `sources`, `authority`, `route_resolution` и состояние диалога, полученные от backend.

## Production assets

HTML/CSS используют только файлы из:

```text
app/static/assets/fonts/
app/static/assets/handoff-v3/
```

Исходные Product Design PNG и старые handoff/reference-папки исключены из clean repository как dev-only материалы.
