"""Central configuration, read from environment variables (see .env.example)."""
import os

try:  # optional: load a .env file if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


DB_BACKEND = os.getenv("ATTENDIQ_DB", "sqlite").lower()
SQLITE_PATH = os.getenv("ATTENDIQ_SQLITE_PATH", "attendiq.db")

MYSQL = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "attendance_tracker"),
}

THRESHOLD = _f("ATTENDIQ_THRESHOLD", 75)        # minimum required attendance %
WARNING_BAND = _f("ATTENDIQ_WARNING_BAND", 80)  # below this (but >= threshold) = Warning

SECRET = os.getenv("ATTENDIQ_SECRET", "dev-secret-change-me")
TOKEN_HOURS = 12

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("ATTENDIQ_MODEL", "claude-sonnet-5-5")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SMTP = {
    "host": os.getenv("SMTP_HOST", ""),
    "port": int(os.getenv("SMTP_PORT", "587")),
    "user": os.getenv("SMTP_USER", ""),
    "password": os.getenv("SMTP_PASSWORD", ""),
    "from": os.getenv("SMTP_FROM", ""),
}

# Password hashing cost (iterations). Lower only in tests.
PBKDF2_ITERATIONS = int(os.getenv("ATTENDIQ_PBKDF2_ITER", "200000"))
