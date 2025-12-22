# Telegram Cobalt Bot

Telegram бот для автоматической загрузки видео из Instagram Reels и X (Twitter) через cobalt-tools API.

## Возможности

- Автоматическое распознавание ссылок на Instagram Reels и видео из X/Twitter
- Работа в групповых чатах и личных сообщениях
- Загрузка видео через cobalt-tools API
- Отправка видео обратно в чат

## Установка

1. Клонируйте этот или ваш репозиторий, если вы отводили свою ветку:
```bash
git clone https://github.com/MustDie-green/tg-chat-cobalt-bot.git
cd tg-chat-cobalt-bot
```

2. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

3. Отредактируйте `.env` и укажите токен вашего Telegram бота:
```
TELEGRAM_TOKEN=your_telegram_bot_token_here
```

4. Запустите проект:
```bash
docker compose up -d
```

## Получение токена Telegram бота

1. Найдите [@BotFather](https://t.me/botfather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания бота
4. Скопируйте полученный токен в файл `.env`

## Использование

Просто отправьте ссылку на Instagram Reel или видео из X/Twitter в групповой чат или личное сообщение. Бот автоматически распознает ссылку, загрузит видео через cobalt-tools API и отправит его обратно.

Поддерживаемые форматы ссылок:
- Instagram Reels: `https://www.instagram.com/reel/...`
- Instagram Posts: `https://www.instagram.com/p/...`
- Twitter/X: `https://twitter.com/.../status/...` или `https://x.com/.../status/...`

## Разработка

Для локальной разработки без Docker:

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Убедитесь, что cobalt-tools запущен (например, через docker compose только для cobalt)

3. Запустите бота:
```bash
python bot.py
```

## Структура проекта

- `bot.py` - основной код бота
- `docker-compose.yml` - конфигурация Docker Compose для cobalt и бота
- `Dockerfile` - образ для бота
- `requirements.txt` - зависимости Python
- `.env.example` - пример файла с переменными окружения

