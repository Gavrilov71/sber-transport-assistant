# Архитектура

## Основной поток

```text
Browser
  ↓
FastAPI /api/chat
  ↓
AgentAssistantService
  ↓
GigaChat-3-Ultra ── function calling ──┐
  ↑                                     │
  └──────── verified tool results ──────┘
                 │
                 ├─ search_official_sources → OfficialTextSearch
                 ├─ get_source_details      → OfficialTextSearch
                 ├─ resolve_route           → RouteResolver
                 ├─ resolve_responsibility  → ResponsibilityRouter
                 └─ get_emergency_guidance  → verified local data
```

Языковая модель отвечает за понимание естественного языка, выбор задачи и формулировку ответа. Фактические решения, которые нельзя доверять свободной генерации, вынесены в локальные детерминированные инструменты.

## Компоненты

### `agent_service.py`

Единый production-путь `/api/chat`. Каждое пользовательское сообщение сначала попадает в GigaChat. Старого regex-intent gate перед моделью нет.

Контракт финального ответа модели — JSON со статусом, пользовательским `answer`, task mode, issue type, severity, patch состояния и IDs использованных источников.

Финализация защищена несколькими слоями:

- tool/function content никогда не становится пользовательским ответом;
- обязательный непустой `answer` для финального ответа;
- максимум одна repair-попытка при нарушении формата;
- допустимо безопасно восстановить только полный JSON-объект с 1–2 лишними закрывающими `}` после него;
- второй JSON, обычный текст после объекта или tool markup отклоняются;
- конкретные числа/сроки/суммы/телефоны проверяются `fact_guard.py` по реально использованным данным.

### `conversation.py`

Хранит состояние диалога в памяти процесса. Важные слоты: муниципалитет, маршрут, тип карты, scope маршрута, оператор, `is_trip_ongoing` и др.

Приоритет обновления состояния: явное исправление пользователя → проверенный tool fact → валидный model patch → предыдущее состояние. `null` не стирает подтверждённый слот.

Текущее хранилище in-memory: после перезапуска процесса история очищается. Для хакатонного single-instance deployment это допустимо; для горизонтального масштабирования потребуется Redis/БД.

### `responsibility.py`

Детерминированно выбирает орган для формальной жалобы/эскалации по issue type, территории и route scope. Модель не может назначить ведомство только потому, что его название встретилось в найденном тексте.

### `route_resolver.py`

Работает по `app/data/routes.json`. Нормализует номер маршрута, но не подменяет похожие номера: например, `39` и `39А` считаются разными.

### `text_search.py`

Локальный поиск по `chunks.json` с BM25/fuzzy scoring. Перед поиском применяется source applicability: региональный, муниципальный, операторский или route-specific scope. Источник, не соответствующий известному контексту, отбрасывается до передачи модели.

### Safety invariant

`unsafe_driver`, `vehicle_defect_hazard`, `accident` не могут считаться обычной (`normal`) проблемой. Но `immediate_danger` разрешён только при явно подтверждённом `is_trip_ongoing=true`.

`get_emergency_guidance` блокируется до выполнения, если текущая поездка не подтверждена. Фраза «водитель пьяный» сама по себе не означает, что пользователь прямо сейчас находится в автобусе.

## Frontend

`app/static/` — готовый HTML/CSS/JS интерфейс. FastAPI монтирует его на `/static` и отдаёт `index.html` с `/`. Отдельного frontend build step нет; Node.js не используется.

## Что было удалено из старого проекта

В clean repository сознательно не включены:

- вложенная старая копия `sber-main/sber-main/`;
- `.venv`, `.venv-new`, `.git`, `.pytest_cache`, `__pycache__`;
- реальный `.env`;
- старые runtime-модули `service.py`, `rag.py`, `retrieval.py`;
- старый RAG/embeddings build script;
- Product Design source/reference pack, уже не используемый runtime;
- raw HTML/PDF cache и source snapshots;
- QA screenshots/live traces.

Production assets, которые реально ссылаются из HTML/CSS, сохранены в `app/static/assets/`.
