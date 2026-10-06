import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
DB_PATH = os.environ.get("DB_PATH", "app.db")
FIRST_SUPERUSER = os.environ.get("FIRST_SUPERUSER", "admin@example.com")
FIRST_SUPERUSER_PASSWORD = os.environ.get("FIRST_SUPERUSER_PASSWORD", "admin123")
WEBHOOK_TIMEOUT_SECONDS = float(os.environ.get("WEBHOOK_TIMEOUT_SECONDS", "5"))
