# VitalTrack — Runbook

## 0. Prerequisites

* A Telegram bot token from `@BotFather`.
* A public HTTPS URL pointing at the API container (`api`) on port 8080.
  In production: terminate TLS with the bundled `nginx` service (mount your
  certs into `nginx/certs/`), or front the stack with Caddy / Cloudflare.
* Docker 24+, Docker Compose v2+.

## 1. First boot

```bash
cp .env.example .env
$EDITOR .env       # set BOT_TOKEN, WEBHOOK_BASE_URL, WEBHOOK_SECRET, DOCTOR_BOOTSTRAP_IDS, POSTGRES_PASSWORD

mkdir -p nginx/certs            # drop fullchain.pem + privkey.pem here
docker compose build
docker compose up -d
docker compose logs -f api      # watch for "Webhook set" + "Scheduler started"
```

Migrations run automatically on `api` start (`alembic upgrade head`).

Verify:

```bash
curl -fsS https://your-host/healthz
```

Send `/start` to the bot. Telegram IDs in `DOCTOR_BOOTSTRAP_IDS` get the
`doctor` role on first contact.

## 2. Daily operations

| Task | Command |
|------|---------|
| Tail API logs | `docker compose logs -f api` |
| Restart API only | `docker compose restart api` |
| Apply new migration | `docker compose exec api alembic revision --autogenerate -m "<msg>" && docker compose exec api alembic upgrade head` |
| Open `psql` | `docker compose exec db psql -U $POSTGRES_USER $POSTGRES_DB` |
| Force webhook re-registration | `docker compose restart api` |
| Trigger missed-med watchdog | `docker compose exec api python -c "import asyncio; from app.scheduler.jobs import run_missed_med_watchdog; asyncio.run(run_missed_med_watchdog())"` |

## 3. Backups

The Postgres data lives in the `postgres-data` Docker volume.

```bash
# Dump
docker compose exec -T db pg_dump -U $POSTGRES_USER -Fc $POSTGRES_DB > vt-$(date +%F).dump
# Restore (into an empty DB)
docker compose exec -T db pg_restore -U $POSTGRES_USER -d $POSTGRES_DB < vt-2026-04-16.dump
```

Keep at least 7 daily, 4 weekly, 12 monthly off-host copies.

## 4. Troubleshooting

**Webhook 401 / Telegram says secret_token mismatch** → re-check `WEBHOOK_SECRET`
in `.env`, restart `api`. Telegram cached the old secret if you changed it
without `set_webhook`.

**Reminders fired twice** → the SQLAlchemy jobstore couldn't find the job,
APScheduler created a duplicate. Stop the API, run
`docker compose exec db psql -c 'DELETE FROM apscheduler_jobs;'`, restart;
`sync_all()` will rebuild from `medications`.

**No Cyrillic in PDF** → install DejaVu fonts on the host or rebuild image
(the Dockerfile leaves the registration to runtime; `app/reports/pdf.py` falls
back to Helvetica if missing).

**Database connection refused on first boot** → the api container starts
before db is healthy. The compose file has a healthcheck but the start
command also gracefully retries via the alembic step; if it still fails, just
`docker compose restart api`.

**`Bind for 0.0.0.0:8080 failed: port is already allocated`** → Docker Desktop
holds host port 8080 on macOS. The compose file maps the api to
`127.0.0.1:8090:8080`; if you changed it, free port 8080 (`lsof -i :8080`) or
pick another host port and update your reverse proxy / ngrok target.

**`DuplicateObjectError: type "user_role" already exists` during alembic
upgrade** → fixed in `alembic/versions/0001_init.py` (enum types are created
explicitly with `checkfirst=True` and column references use
`postgresql.ENUM(create_type=False)`). If you author new migrations that
reference the same enums, mirror that pattern.

**`AmbiguousForeignKeysError` on `User.alerts`** → `Alert` has two FKs to
`users.id` (`user_id`, `acknowledged_by_id`); the relationship is declared
with `foreign_keys="Alert.user_id"`. Apply the same pattern to any new
multi-FK relationship.

**Reset everything** (development only):

```bash
docker compose down -v
docker compose up -d --build
```

## 5. Security checklist

- [ ] `.env` is **not** committed.
- [ ] HTTPS terminates either at nginx (with valid cert) or at an upstream
      reverse proxy.
- [ ] `WEBHOOK_SECRET` is at least 32 random chars.
- [ ] DB password is non-default.
- [ ] Backups are encrypted at rest.
- [ ] Doctor onboarding is gated by `DOCTOR_BOOTSTRAP_IDS` — never expose a
      self-service doctor flow on production.
- [ ] `/forget_me` is documented to patients and tested every release.
