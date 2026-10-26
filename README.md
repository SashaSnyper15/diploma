# B2B SaaS Moderation Prototype

Прототип продукта из ВКР: API-first система модерации контента для нишевых маркетплейсов и интернет-магазинов.

Без ML-моделей: все проверки rule-based.

## Что реализовано

- Python backend (`FastAPI + SQLite`) с мультипроектностью.
- React admin-панель для управления проверками.
- Sync и async сценарии проверки контента.
- Проектные правила и пороги чувствительности.
- Ручной разбор кейсов (`approve/reject/escalate`).
- История версий проверки и аудит действий.
- Базовая аналитика причин отклонений.

## Структура

- `backend` - API и rule-engine.
- `frontend` - административная панель.

## Быстрый запуск (сервер + админка одной кнопкой)

- **VS Code:** `F5` (конфигурация «Сервер + админка») или `Cmd+Shift+B`.
- **Терминал:** `./dev.sh`

При первом запуске скрипт сам создаст venv и поставит зависимости.
API — `http://localhost:8000/docs`, админка — `http://localhost:5173`. `Ctrl+C` останавливает оба.

## Сброс к первоначальному виду

`./reset.sh` (или `./reset.sh -y` без подтверждения) — удаляет все данные из БД, заново создаёт demo-проект и чистит кэши.
В VS Code: `Cmd+Shift+P` → «Run Task» → «Сбросить БД».

## Запуск backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

После старта создается demo-проект:

- `name`: `Demo Marketplace`
- `api_key`: `demo-api-key-123`

Swagger: `http://localhost:8000/docs`

## Запуск frontend

```bash
cd frontend
npm install
npm run dev
```

UI: `http://localhost:5173`

По умолчанию frontend ходит в `http://localhost:8000`.
При необходимости:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Пример интеграции API (контур интегратора)

```bash
curl -X POST "http://localhost:8000/api/v1/moderation/checks" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-api-key-123" \
  -H "X-Role: integrator" \
  -d '{
    "content_type": "product_card",
    "mode": "sync",
    "external_content_id": "SKU-001",
    "title": "Косметика без документов",
    "description": "Гарантированный результат, 100% эффект",
    "category": "косметика",
    "attributes": {
      "brand": "DemoBrand",
      "price": "1200",
      "country_of_origin": "RU"
    },
    "image_urls": ["https://cdn.example.com/item.jpg"]
  }'
```

