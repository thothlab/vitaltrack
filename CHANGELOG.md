# Changelog

## [Unreleased]

### Added
- **Flexible datetime input for pressure readings.** The time part now accepts
  `,` `;` and `.` as separators in addition to `:`, so mobile typos like
  `14,30` or `вчера 23;45` or `15.04 14.30` are parsed correctly.
  Date tokens such as `15.04.2025` are unaffected.
  (`app/utils/time.py` — `_normalize_time_token()`)
- **Per-day pressure breakdown in reports.** The text report now includes a
  "По дням" section showing per-day mean ± max/min pressure (and HR when
  available) when readings span two or more days. Computed from the same
  records already fetched for the summary, grouped by the user's local timezone.
  (`app/services/reports.py` — `PressureDailyRow`, `pressure_daily` field;
  `app/reports/text.py`)

### Added (previous)
- **Patient profile wizard** (`app/bot/handlers/profile.py`,
  `app/bot/states/profile.py`). Settings → Profile opens a summary with
  per-field edits (sex, DOB, height, weight, smoker, diabetes) and a
  "Fill from scratch" 6-step wizard. Backed by
  `UserService.update_profile()` which whitelists writable columns.
- Calculators read profile context: BMI pre-fills height/weight from the
  profile, age-gates the result (<18 → referral to pediatric BMI-for-age;
  ≥65 → sarcopenia caveat). Calc menu reworded with plain-language labels
  and a short what-is-this intro.
- `callback_data="set:profile"` is owned by the new profile router
  (registered before `settings_handler` in `app/bot/bot.py` so it wins
  the callback).

### Ops
- macOS dev tunnel is now wrapped in a `launchctl` LaunchAgent
  (`com.shaukat.vitaltrack-ngrok`). Documented in RUNBOOK §1.1 together
  with a new troubleshooting entry ("bot silent on `/start`, watchdogs
  still fire" → tunnel down, not API).

### Fixed
- `alembic/versions/0001_init.py`: explicit enum creation with
  `checkfirst=True`; column-level enum references switched to
  `postgresql.ENUM(create_type=False)` so `op.create_table` no longer
  re-issues `CREATE TYPE` and crashes with `DuplicateObjectError`.
- `app/db/models.py`: `User.alerts` relationship now declares
  `foreign_keys="Alert.user_id"` because `Alert` has two FKs back to
  `users.id` (`user_id`, `acknowledged_by_id`). Without it SQLAlchemy
  raised `AmbiguousForeignKeysError` at startup.
- `app/main.py`: removed the `lifespan`/`@app.on_event("startup")` race —
  the bot, dispatcher and webhook router are now wired synchronously inside
  `create_app()`; `lifespan` only handles `set_webhook` + scheduler
  start/stop.
- `docker-compose.yml`: api published on `127.0.0.1:8090:8080` to avoid the
  host-port-8080 conflict with Docker Desktop on macOS.

### Tests
- 19/19 green (`pytest -q`). `test_expected_intakes_interval` adjusted to
  match documented behaviour (8h interval anchored at 08:00 fires at
  `{0, 8, 16}` within a UTC day window).

## [0.1.0] — 2026-04-16

Initial production-ready release.

- Modular architecture: handlers → services → repositories → ORM.
- Postgres 16 (JSONB, TIMESTAMPTZ, indexed FKs), Redis 7 (FSM storage).
- aiogram 3.x webhook-only delivery, FSM groups for every entry flow,
  cancel/back, "Сейчас" / "вчера 21:30" date helpers.
- APScheduler 3.x with persistent SQLAlchemyJobStore on the same Postgres,
  deterministic per-medication job IDs, `sync_all()` reconciliation on
  restart, watchdogs for `no_data` and `missed_med`.
- Real medical calculators: SCORE2 ESC 2021 with regional recalibration,
  CKD-EPI 2021 race-free eGFR, BMI, HOMA-IR.
- Reports: text / PDF (ReportLab + DejaVu fallback) / CSV (zipped),
  periods 7d / 30d / 90d / custom.
- Alerts with idempotent `dedup_key UNIQUE` and configurable thresholds.
- Doctor mode: in-bot `MessageThread` + `Message` instead of real DMs;
  bootstrap via `DOCTOR_BOOTSTRAP_IDS`.
- Privacy: consent-on-/start, `/forget_me` cascade, RBAC in services.
- Docker Compose stack (api + db + redis + nginx) with healthchecks and
  automatic migrations on `api` start.
