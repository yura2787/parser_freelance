# Foreign Freelance Radar

Python-скрипт для поиска зарубежных freelance/project-based заказов и отправки найденных заявок в Telegram.

Скрипт ищет не full-time вакансии, а проектные задачи:

- Telegram bots
- web scraping
- automation
- API integrations
- AI tools
- dashboards / CRM
- React / Next.js / WordPress
- n8n / Zapier / Make
- Chrome extensions
- MVP / web apps

Источники:

- Freelancer.com active projects
- PeoplePerHour freelance projects
- Algora bounties
- Telegram project feeds с Upwork/Freelancer/WebDev задачами

Скрипт только ищет и присылает заявки. Он не отправляет отклики клиентам автоматически.

## Запуск через Docker (рекомендуется)

Проще всего — через Docker, без локального Python и venv:

```bash
cd foreign-freelance-radar

# Собрать образ (нужно один раз и после изменений в коде)
docker compose build

# Посмотреть найденные заявки без отправки (ничего настраивать не нужно)
docker compose run --rm radar --limit 10 --per-source 10 --min-score 35 --dry-run

# Отправить в Telegram (сначала создайте .env, см. ниже)
docker compose run --rm radar --limit 20 --per-source 20 --min-score 35 --telegram
```

Аргументы после `radar` — это флаги скрипта, их можно менять. Папки `output/` и
`sessions/` монтируются на хост, поэтому результаты и Telegram-сессия сохраняются.

## Быстрый старт (локально)

Сначала скачайте проект и установите зависимости.

Вариант с [uv](https://docs.astral.sh/uv/) (быстрее):

```bash
git clone https://github.com/Egor01KKK/foreign-freelance-radar.git
cd foreign-freelance-radar

uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Вариант с обычным venv + pip:

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Потом создайте локальный `.env`:

```bash
cp .env.example .env
```

Откройте `.env` и заполните минимум два поля:

```bash
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```

Остальные поля (`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, ...) нужны только для
режима `--use-telegram-session` — их можно оставить пустыми.

## Самый простой запуск

Проверить, что заявки находятся, но ничего не отправлять:

```bash
python3 foreign_freelance_radar.py --limit 10 --per-source 10 --min-score 35 --dry-run
```

Отправить найденные заявки в Telegram-бота:

```bash
python3 foreign_freelance_radar.py --limit 20 --per-source 20 --min-score 35 --telegram
```

Этого достаточно для базового режима: скрипт читает публичные сайты и публичные Telegram-feed страницы через `https://t.me/s/...`, а найденные заявки отправляет в вашего бота.

## Что нужно заполнить

Минимум:

```bash
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```

Для обычного запуска этого хватает.

Дополнительно, если хотите читать Telegram-каналы через свой аккаунт:

```bash
TELEGRAM_API_ID=YOUR_API_ID
TELEGRAM_API_HASH=YOUR_API_HASH
TELEGRAM_PHONE=+10000000000
TELEGRAM_SESSION_PATH=sessions/freelance_user
```

`TELEGRAM_API_ID` и `TELEGRAM_API_HASH` нужны только для режима `--use-telegram-session`.

## Как создать Telegram-бота

1. Откройте [@BotFather](https://t.me/BotFather).
2. Отправьте команду `/newbot`.
3. Придумайте название и username бота.
4. BotFather выдаст токен.
5. Вставьте токен в `.env`:

```bash
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
```

## Как узнать `TELEGRAM_CHAT_ID`

1. Напишите любое сообщение своему новому боту.
2. Откройте в браузере:

```text
https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
```

3. Найдите в ответе `"chat":{"id":...}`.
4. Вставьте этот id в `.env`:

```bash
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```

Если бот должен писать в группу, добавьте бота в группу и напишите любое сообщение в этой группе.

## Пользовательская Telegram-сессия

Базовый режим не требует Telegram-сессии. Но если вы хотите читать Telegram-источники как обычный пользовательский аккаунт, включите session mode.

Это полезно, если:

- публичная `t.me/s/...` страница канала недоступна;
- вы хотите читать каналы через свой Telegram-аккаунт;
- позже вы добавите приватные каналы/чаты, куда ваш аккаунт уже вступил.

Для session mode нужно заполнить в `.env`:

```bash
TELEGRAM_API_ID=YOUR_API_ID
TELEGRAM_API_HASH=YOUR_API_HASH
TELEGRAM_PHONE=+10000000000
TELEGRAM_SESSION_PATH=sessions/freelance_user
```

`TELEGRAM_API_ID` и `TELEGRAM_API_HASH` создаются здесь:

```text
https://my.telegram.org/apps
```

Первый запуск попросит код из Telegram. После входа будет создан локальный файл сессии в папке `sessions/`. Этот файл нельзя публиковать.

Важно: Telegram-сессия у каждого человека должна быть своя. Ее нельзя положить в GitHub вместе с проектом, потому что это доступ к аккаунту.

Запуск с Telegram user session:

```bash
python3 foreign_freelance_radar.py --use-telegram-session --limit 20 --per-source 20 --min-score 35 --telegram
```

Только Telegram через user session:

```bash
python3 foreign_freelance_radar.py --use-telegram-session --telegram-only --limit 20 --per-source 20 --min-score 35 --dry-run
```

## Команды

```bash
# Проверить без отправки в Telegram
python3 foreign_freelance_radar.py --limit 10 --per-source 10 --min-score 35 --dry-run

# Отправить заявки в Telegram
python3 foreign_freelance_radar.py --limit 20 --per-source 20 --min-score 35 --telegram

# Посмотреть источники
python3 foreign_freelance_radar.py --audit-sources

# Только Telegram-источники
python3 foreign_freelance_radar.py --telegram-only --limit 20 --per-source 20 --min-score 35 --dry-run
```

### Полезные флаги

- `--min-budget 300` — отбросить заявки, где распознанный бюджет меньше указанной суммы (в USD).
- `--all` — показать в том числе заявки, которые уже присылались в прошлых запусках.
- `--forget` — очистить память «уже показанного» и выйти.
- `--workers 8` — сколько источников загружать параллельно (по умолчанию 8).

### Память между запусками

Скрипт запоминает уже показанные заявки в `output/seen.json`, поэтому при повторных
запусках приходят **только новые** заявки. Это удобно для запуска по расписанию.
Чтобы снова увидеть всё — используйте `--all`. Чтобы сбросить память — `--forget`.

### Форматирование в Telegram

Заявки приходят с HTML-разметкой: кликабельный заголовок-ссылка, индикатор качества
(🟢 / 🟡 / 🟠 по score), бюджет и «как зайти». Если одно сообщение не отправилось,
остальные всё равно уходят.

## Если что-то не работает

### `Telegram env not found`

Не заполнены `TELEGRAM_BOT_TOKEN` или `TELEGRAM_CHAT_ID` в `.env`.

Решение: откройте `.env` и впишите оба значения (см. разделы про создание бота и chat_id ниже).

### `TELEGRAM_API_ID and TELEGRAM_API_HASH are required`

Вы запустили `--use-telegram-session`, но не заполнили данные приложения Telegram.

Создайте их здесь и впишите в `.env`:

```text
https://my.telegram.org/apps
```

### При первом запуске Telegram просит код

Это нормально. Код придет в Telegram. После входа появится локальный session-файл в папке `sessions/`, и дальше код обычно больше не нужен.

### Почему в GitHub нет настоящего `.env`

Потому что `.env` содержит токены и личные данные. Каждый создаёт свой `.env` локально из `.env.example`.

## Настройка источников

Источники находятся в файле `foreign_freelance_radar.py`, переменная `SOURCES`.

Пример источника:

```python
Source(
    "tg_upwork_webdev",
    "Telegram - Upwork WebDev Projects",
    "telegram_web",
    "https://t.me/s/upworkwd",
    note="Web-dev Upwork project feed",
)
```

Чтобы отключить источник, добавьте:

```python
enabled=False
```

## Настройка фильтров

Фильтры находятся в `foreign_freelance_radar.py`:

- `RELEVANT_TERMS` — слова, которые повышают score.
- `CORE_TERMS` — слова, которые делают пост похожим на нужный заказ.
- `PROJECT_TERMS` — признаки проектной/freelance задачи.
- `HARD_REJECT` — явный мусор.
- `LOW_VALUE_TERMS` — слабые сигналы.

Проекты на `$100-$500` не выкидываются. Это нормальные быстрые фриланс-заказы.

## Где результат

После запуска создается папка `output/`:

- `output/deal_radar_latest.md` — заявки последнего запуска в Markdown
- `output/deal_radar_latest.json` — то же в JSON
- `output/seen.json` — память «уже показанного» (чтобы не слать дубликаты)

## Безопасность

Не публикуйте:

- `.env`
- реальные токены Telegram-бота
- личные Telegram session-файлы
- папку `sessions/`
- приватные результаты из `output/`
