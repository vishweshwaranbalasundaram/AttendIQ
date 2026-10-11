"""Abstract Agent: every agent inherits this and overrides run().

execute() is a Template Method: it wraps run() with audit logging and error handling, so no
agent can act without leaving a row in AgentLog.
"""
from abc import ABC, abstractmethod

from attendiq.dao import AgentLogDAO
from attendiq.service.attendance_service import AttendanceService
from attendiq.service.calculator import AttendanceCalculator


class Agent(ABC):
    name = "Agent"
    purpose = "Abstract agent"

    def __init__(self, calculator: AttendanceCalculator = None):
        self.calc = calculator or AttendanceCalculator()
        self.service = AttendanceService(self.calc)
        self._log = AgentLogDAO()

    def describe(self) -> str:
        return f"{self.name}: {self.purpose}"

    @abstractmethod
    def run(self, context: dict) -> dict:
        """Do the agent's work. May read/extend `context`; must return a small summary dict."""

    def execute(self, context: dict) -> dict:
        scope = context.get("student_ids")
        try:
            result = self.run(context)
            self._log.add(self.name, "run", f"scope={'all' if scope is None else scope}", result)
            return result
        except Exception as exc:  # an agent failure must never break attendance marking
            self._log.add(self.name, "error", f"scope={scope}", repr(exc))
            return {"error": repr(exc)}
