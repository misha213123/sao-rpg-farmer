# SAO RPG Farmer

Автоматический клиент для собственной Telegram RPG-игры. Работает через Telethon под пользовательским аккаунтом, читает inline-кнопки и нажимает их по правилам.

## Что умеет

- маршрут: `Профиль` → `Замок лорда кобольдов` → `Начать исследование`;
- основной цикл: `Продолжить исследование`;
- бой: `Обычная атака`;
- события: сокровища и `Продолжить поход`;
- при сообщении о низких ресурсах нажимает `Выпить зелье стамины`;
- никогда не нажимает зелье HP;
- управление из «Избранного»: `/on`, `/off`, `/status`, `/click`, `/help`;
- обрабатывает новые и отредактированные сообщения;
- защита от повторного клика по одному состоянию сообщения.

## Важно про хостинг

Vercel не подходит для постоянно подключённого Telethon-процесса. Для 24/7 используйте Railway, Render Background Worker или VPS. Репозиторий содержит `Dockerfile` и `render.yaml`.

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

```env
API_ID=12345678
API_HASH=your_api_hash
STRING_SESSION=your_telethon_string_session
GAME_BOT=@your_game_bot
AUTO_START=false
CLICK_DELAY_MIN=0.7
CLICK_DELAY_MAX=1.4
```

`API_ID` и `API_HASH` создаются на `my.telegram.org`.

## Получение STRING_SESSION

На компьютере:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/create_session.py
```

Введите номер телефона, код Telegram и пароль 2FA, если он включён. Скрипт выведет строку сессии. Никому её не показывайте и не добавляйте в GitHub.

## Локальный запуск

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

После запуска откройте Telegram → «Избранное» и отправьте:

```text
/on
```

## Управление

- `/on` — включить автоматику и обработать последнее сообщение игры;
- `/off` — выключить;
- `/status` — состояние и статистика;
- `/click` — вручную обработать последнее сообщение;
- `/help` — список команд.

## Render

Создайте **Background Worker**, подключите репозиторий и добавьте переменные окружения. Команда запуска уже указана в `render.yaml`:

```text
python -m app.main
```

## Безопасность

- не коммитьте `.env`;
- не публикуйте `STRING_SESSION`, `API_HASH` и коды Telegram;
- при утечке строки сессии завершите неизвестные сеансы в Telegram и создайте новую.
