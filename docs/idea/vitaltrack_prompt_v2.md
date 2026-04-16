# VitalTrack Bot — Prompt v2 (Claude Code Optimized)

## IMPORTANT META-INSTRUCTIONS

You are a senior principal engineer.

You MUST:
- produce production-ready code
- avoid simplifications to MVP
- avoid placeholder logic
- avoid partial implementations

---

## CRITICAL GUARDRAILS (ANTI-AI-FAILURES)

1. Do not use SQLite anywhere.
2. Use PostgreSQL-specific features (JSONB, proper indexes, timezone-aware timestamps).
3. Do not mix sync and async DB logic.
4. Do not use long polling — webhook only.
5. Do not store business logic inside Telegram handlers.
6. Do not skip migrations.
7. Do not skip Docker setup.
8. Do not skip scheduler reliability (no duplicate jobs).
9. Do not generate fake or stub calculators.
10. Do not omit doctor mode.

---

## STACK (STRICT)

- Python 3.12
- FastAPI
- aiogram 3.x
- PostgreSQL
- Redis
- SQLAlchemy 2.x (async)
- Alembic
- APScheduler
- Docker Compose
- Nginx/Caddy

---

## ARCHITECTURE RULES

- Clean modular structure
- Domain layer separated
- Services contain logic
- Handlers only orchestrate
- DB access via repositories

---

## DATABASE RULES

- Use TIMESTAMP WITH TIME ZONE
- Use JSONB where flexible schema is needed
- Add indexes for frequent queries
- Use transactions properly
- Avoid N+1 queries

---

## TELEGRAM RULES

- Use FSM for flows
- Provide cancel/back in all flows
- Restore interrupted flows if possible
- Use inline keyboards primarily
- Avoid free-text when structured input possible

---

## SCHEDULER RULES

- Jobs must be idempotent
- No duplicate reminders after restart
- Persist schedule state
- Handle timezone correctly

---

## DOCTOR MODE RULES

- Implement inbox inside bot (NOT real Telegram chats)
- Support unread indicators
- Support patient threads
- Route messages via chat_id mapping

---

## REPORTING RULES

- Support:
  - 7 days
  - 1 month
  - 3 months
  - custom
- Include aggregation logic
- Include adherence metrics

---

## ALERTS RULES

- Configurable thresholds
- Safe wording (no diagnosis)
- Store alert history
- Allow acknowledgement

---

## DEPLOYMENT RULES

- Provide docker-compose
- Use single PostgreSQL instance
- Separate DB per bot
- Provide .env.example
- Provide runbook

---

## OUTPUT REQUIREMENTS

You must generate:

1. Architecture summary
2. Project tree
3. Full codebase
4. DB models + migrations
5. Telegram flows
6. Services
7. Scheduler
8. Reports (including PDF)
9. Docker setup
10. README + runbook
11. Tests

Do not stop early.
Do not skip steps.
