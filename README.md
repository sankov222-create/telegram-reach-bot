# Reach-бот — охваты Instagram / TikTok / YouTube в Telegram

Бот принимает ссылку на профиль, даёт выбрать период на календаре и присылает
суммарный охват + топ-4 поста по охвату за этот период.

## Как это работает

1. `/start` → бот просит прислать ссылку (можно несколько — по одной на площадку).
2. Жмёте «Готово» → бот показывает календарь, выбираете начальную и конечную дату.
3. Бот парсит данные через Apify и присылает по каждой площадке:
   - количество постов, суммарный и средний охват;
   - топ-4 поста по охвату (дата, просмотры, ссылка).

## Шаг 1. Получить токен Telegram-бота

1. Откройте в Telegram чат **@BotFather**.
2. Отправьте `/newbot`, придумайте имя и username бота (username должен заканчиваться на `bot`).
3. BotFather пришлёт токен вида `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` — сохраните его.

## Шаг 2. Получить токен Apify

1. Зарегистрируйтесь на [apify.com](https://apify.com) (есть бесплатный план с пробным балансом).
2. Зайдите в **Settings → Integrations → API token** и скопируйте токен.
3. Учтите: сбор данных платный по факту использования (обычно доли цента за пост),
   бесплатного пробного баланса Apify хватает на тестирование.

## Шаг 3. Настройка проекта

```bash
cd tgbot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Откройте `.env` и вставьте оба токена:

```
TELEGRAM_BOT_TOKEN=ваш_токен_от_botfather
APIFY_TOKEN=ваш_токен_apify
```

## Шаг 4. Запуск локально (для теста)

```bash
python3 bot.py
```

Бот работает, пока запущен этот процесс и открыт компьютер/терминал.
Найдите бота в Telegram по username и отправьте `/start`.

## Шаг 5. Постоянный хостинг (24/7)

Локальный запуск подходит только для тестов — бот выключится, как только
закроете терминал или компьютер уйдёт в сон. Для постоянной работы есть три варианта:

### Вариант A — бесплатный облачный сервис (проще всего)

Например, **Railway.app** или **Render.com**:

1. Зарегистрируйтесь, создайте новый проект → "Deploy from GitHub repo"
   (сначала загрузите папку `tgbot` в свой репозиторий на GitHub).
2. В настройках проекта добавьте переменные окружения `TELEGRAM_BOT_TOKEN` и `APIFY_TOKEN`.
3. Команда запуска: `python bot.py`.
4. Бесплатного тарифа обычно хватает для одного бота с умеренной нагрузкой.

### Вариант B — свой VPS (недорого, полный контроль)

Любой сервер за 200–400 ₽/мес (Timeweb, Selectel, DigitalOcean и т.п.):

```bash
# на сервере
git clone <ваш репозиторий>
cd tgbot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # и вписать токены
```

Чтобы бот работал постоянно и перезапускался при сбоях — через `systemd`:

```ini
# /etc/systemd/system/reach-bot.service
[Unit]
Description=Reach Telegram Bot
After=network.target

[Service]
WorkingDirectory=/root/tgbot
ExecStart=/root/tgbot/venv/bin/python bot.py
Restart=always
EnvironmentFile=/root/tgbot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now reach-bot
```

### Вариант C — Docker (если сервер уже настроен под Docker)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

```bash
docker build -t reach-bot .
docker run -d --restart=always --env-file .env reach-bot
```

## Ограничения и заметки

- Instagram и YouTube не отдают публично число репостов — в отчёте бота это не считается.
- Для Instagram охват = реальные проигрывания видео (play count), не заниженный публичный
  счётчик просмотров — так же, как в ранее сделанном отчёте.
- Чем шире выбранный период, тем дольше идёт сбор данных (бот дозапрашивает посты у Apify
  порциями, пока не наберёт нужную глубину истории).
- Если профиль очень активный (много постов в день), для очень широких периодов может
  понадобиться увеличить `max_limit`/`max_results` в `scrapers.py`.
