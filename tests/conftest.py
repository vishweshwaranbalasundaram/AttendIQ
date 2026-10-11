"""Tests run on in-memory SQLite by default.
Run them against a real MySQL/MariaDB server with:  ATTENDIQ_TEST_DB=mysql pytest   (uses the MYSQL_* env vars)
"""
import os

BACKEND = os.environ.get("ATTENDIQ_TEST_DB", "sqlite")
os.environ["ATTENDIQ_DB"] = BACKEND
os.environ["ATTENDIQ_SQLITE_PATH"] = ":memory:"
os.environ["ATTENDIQ_PBKDF2_ITER"] = "1000"
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest

from attendiq import config
from attendiq.seed import seed
from attendiq.util.db import DBConnection

TABLES = ["QRToken", "AgentLog", "RecoveryPlan", "RiskPrediction", "Notification", "AppUser", "Timetable",
          "Attendance", "ClassSession", "Enrollment", "Subject", "Faculty", "Student"]


@pytest.fixture(autouse=True)
def fresh_db():
    """Every test gets a brand-new database with the demo data."""
    config.ANTHROPIC_API_KEY = ""
    db = DBConnection.reset(BACKEND, ":memory:" if BACKEND == "sqlite" else None)
    if BACKEND == "mysql":
        db.execute("SET FOREIGN_KEY_CHECKS = 0")
        for t in TABLES:
            db.execute(f"DROP TABLE IF EXISTS {t}")
        db.execute("SET FOREIGN_KEY_CHECKS = 1")
    db.init_schema()
    seed(verbose=False)
    yield
