import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DEV_AUTH_BYPASS", "true")
os.environ.setdefault("STORAGE_BACKEND", "local")
