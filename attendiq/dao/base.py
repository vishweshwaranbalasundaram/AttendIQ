"""Base DAO: every DAO talks to the database only through DBConnection."""
from attendiq.util.db import DBConnection


class BaseDAO:
    @property
    def db(self) -> DBConnection:
        # looked up on every call so DBConnection.reset() (tests, seeding) is respected
        return DBConnection.get_instance()
