import os

# Ensure Settings can construct without a real .env present in the test env.
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("WEBHOOK_BASE_URL", "https://example.com")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("POSTGRES_DB", "vt")
os.environ.setdefault("POSTGRES_USER", "vt")
os.environ.setdefault("POSTGRES_PASSWORD", "vt")
