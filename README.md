# Just-Tag-All Telegram Bot

Телеграм-бот на aiogram: тег всех участников (/all), судьба/Апокриф (/random), приветствие (/hello).

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

export TOKEN=your_bot_token
python src/start.py
```

## Docker

```bash
docker compose up --build
```

Токен задать в окружении (env в docker-compose или `-e TOKEN=...`).
