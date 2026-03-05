# Just-Tag-All Telegram Bot

Телеграм-бот на aiogram: тег всех участников (/all), судьба/Апокриф (/random), приветствие (/hello).

## Запуск

Скопируй `env.example` в `.env` и заполни переменные:

```bash
cp env.example .env
# отредактируй .env: TOKEN, при необходимости OPENROUTER_API_KEY
```

```bash
python3 -m venv .venv
source .venv\Scripts\activate   # Windows: .venv\Scripts\activate  .venv/bin/activate
pip install -e .

python src/start.py
```

## Docker

```bash
docker compose up --build
```

Токен задать в окружении (env в docker-compose или `-e TOKEN=...`).
