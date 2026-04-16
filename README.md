# VitalTrack — Telegram Medical Monitoring Platform

VitalTrack is a production-grade Telegram bot platform for longitudinal patient
monitoring (blood pressure, blood glucose, medications, symptoms, nutrition,
labs) with a built-in **doctor mode** (patient list, internal threads, alerts,
reports).

It is **not** an MVP — the codebase ships with:

* clean modular architecture (domain → services → repositories → handlers)
* PostgreSQL (JSONB, timezone-aware timestamps, proper indexes)
* aiogram 3.x with FSM flows, cancel/back, restorability
* APScheduler with **persistent jobstore** (no duplicate jobs after restart)
* Alembic migrations
* PDF + CSV + text reports
* SCORE2 / BMI / GFR (CKD-EPI 2021) / HOMA-IR calculators (real formulas)
* Configurable alert thresholds (high BP, hypoglycemia, missed meds, no data)
* Webhook-only Telegram delivery (FastAPI), Nginx reverse proxy
* Docker Compose deployment

## Stack

* Python 3.12, FastAPI, aiogram 3.x
* SQLAlchemy 2.x async, Alembic
* PostgreSQL 16, Redis 7
* APScheduler 3.x (SQLAlchemyJobStore on the same Postgres)
* ReportLab for PDFs
* Docker Compose, Nginx

## Project layout

```
vitaltrack/
├── app/
│   ├── main.py              # FastAPI entrypoint (webhook + healthz)
│   ├── config.py            # Pydantic settings
│   ├── db/                  # Engine, session, ORM models, base
│   ├── domain/              # Enums + Pydantic schemas (no IO)
│   ├── repositories/        # Async DB access only
│   ├── services/            # Business logic (calculators, reports, alerts…)
│   ├── bot/
│   │   ├── bot.py           # Bot/Dispatcher wiring
│   │   ├── webhook.py       # FastAPI webhook router
│   │   ├── middlewares/     # DB session + user resolution
│   │   ├── keyboards/       # Inline keyboards (patient/doctor)
│   │   ├── states/          # FSM state groups per flow
│   │   └── handlers/        # Thin orchestration only
│   ├── scheduler/           # APScheduler + idempotent jobs
│   ├── reports/             # PDF / CSV / text renderers
│   └── utils/               # tz helpers, formatting, i18n
├── alembic/                 # Migrations
├── tests/                   # Pytest suite
├── nginx/nginx.conf
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── RUNBOOK.md
```

## Quick start (development)

```bash
cp .env.example .env
# edit BOT_TOKEN, WEBHOOK_BASE_URL, POSTGRES_*, REDIS_URL, DOCTOR_BOOTSTRAP_IDS
docker compose up -d --build
```

Migrations run automatically on `api` startup (`alembic upgrade head` is part
of the container command). The bot registers its webhook with Telegram on
startup (see `app/main.py` + `app/bot/webhook.py`). `WEBHOOK_BASE_URL` must
be a public HTTPS URL.

### Local dev with ngrok

```bash
# 1. Expose api container (host port 8090 → container 8080) over HTTPS
ngrok http 8090
# 2. Copy the https URL into .env as WEBHOOK_BASE_URL
# 3. (re)start the api container so the new webhook is registered
docker compose up -d --build api
# 4. Verify
curl -fsS https://<your-ngrok>.ngrok-free.dev/healthz
```

> **Note on host port 8090.** `docker-compose.yml` maps the api to
> `127.0.0.1:8090:8080` because Docker Desktop on macOS occupies host port
> 8080. Change the left-hand side if you prefer a different host port.

## Architecture summary

* **Handlers** parse callbacks/messages, push state, and call **services**.
* **Services** own all business logic and validation. They depend only on
  **repositories** (DB) and **domain** types.
* **Repositories** are the only place that touches SQLAlchemy.
* **Scheduler** jobs call services, never handlers — the same code path that
  drives the bot drives reminders, daily digests and watchdogs.
* **Reports** are pure renderers fed pre-aggregated data from services.

This keeps Telegram an *adapter*; the rest of the system is independently
testable and could be exposed via an HTTP API later.

## Modules

| Module       | Records                                      | Reminders | Alerts |
|--------------|----------------------------------------------|-----------|--------|
| Pressure     | SBP/DBP/HR sessions (multi-measurement)      | yes       | yes    |
| Glucose      | mmol/L, context (fasting/post-meal/bedtime)  | yes       | yes    |
| Medications  | dose, schedule, intake events, adherence     | yes       | yes    |
| Symptoms     | well-being grade, free symptom tags          | no        | —      |
| Nutrition    | meal type, free tags, time                   | no        | —      |
| Labs         | TC / LDL / HDL / TG / glucose / insulin      | no        | —      |
| Calculators  | SCORE2, BMI, GFR (CKD-EPI 2021), HOMA-IR     | —         | —      |
| Reports      | 7d / 30d / 90d / custom · text / PDF / CSV   | —         | —      |
| Doctor mode  | patient list, in-bot threads, alerts inbox   | —         | —      |

## Doctor mode

Doctors don't message patients in real Telegram chats. Each doctor↔patient
conversation lives in an **in-bot inbox** (`MessageThread` + `Message`).
The bot delivers new messages as Telegram messages to the recipient with an
inline reply button that re-enters the FSM thread — keeping the audit trail
inside Postgres rather than scattered DM history.

Doctors are bootstrapped from `DOCTOR_BOOTSTRAP_IDS` (comma-separated Telegram
IDs) at first `/start`. After that, role is stored in `users.role`.

## Privacy & safety

* All medical wording is descriptive, never diagnostic.
* `/forget_me` purges the patient's data (cascade) and revokes consent.
* Patient consent is captured on first `/start` and gates all data entry.
* `BOT_TOKEN`, DB credentials and `WEBHOOK_SECRET` live only in env.
* RBAC is enforced in services (`require_doctor`, `require_owner_or_doctor`).

See [`RUNBOOK.md`](RUNBOOK.md) for deployment, backups, and troubleshooting.

## Tests

```bash
pytest -q
```

Covers calculators (SCORE2, BMI, GFR, HOMA-IR), report aggregation, and
alert threshold logic.
